"""
Planning Agent — Stage 4 of the pipeline.

The LLM's job is to REASON, not search. It receives:
1. User request + profile summary
2. Pre-ranked candidate places (15–30 from Candidate Scorer)

It produces a structured day-by-day itinerary choosing from candidates.

Uses Pydantic-based structured output (``with_structured_output``) to guarantee
valid JSON with the required ``days`` key, eliminating manual extraction/repair.
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from ai_engine.llm import invoke_with_fallback
from ai_engine.graph.state import TripState
from ai_engine.schemas.planning_schema import ItineraryPlan

logger = logging.getLogger(__name__)


# System prompt that defines the Planning Agent's role and rules.
# The JSON schema is enforced by Pydantic's structured output — the prompt
# focuses on reasoning rules rather than formatting instructions.
PLANNER_SYSTEM_PROMPT = """
You are the Planning Agent for TourMate AI. Create a structured day-by-day travel itinerary from the provided candidate places.

You receive:
1. User request with trip context (interests, preferences, duration)
2. Candidate attractions & restaurants (pre-ranked, 0–100 score)
   - Hotels are handled elsewhere — ignore them

## Mandatory Constraints (all must be satisfied)

1. **Day count** — Create EXACTLY the number of days specified in "Trip Duration". Not one fewer, not one more. If candidates seem limited, spread them across all days rather than omitting a day.

2. **Stops per day** — 2–5 stops per day. Never exceed 5. Last day can be 2 stops.

3. **Interest coverage** — Every user interest must appear in at least one stop. If 2+ candidates share a sub_category matching an interest, include at least 2 stops from it. If no candidates match an interest, pick the closest semantic match or note the gap in the itinerary.

4. **Candidate honesty** — Use only provided candidates. Copy id/name/lat/lon from candidates exactly. Do not invent places.

5. **why_recommended** — Every stop needs 1–2 sentences explaining why it fits this specific user (reference their interests and the place's score).

## Best Practices (apply when constraints allow)

- **Group nearby stops** within ~5 km on the same day
- **Mix categories**: don't stack 3 of same type consecutively
- **Restaurants**: insert lunch between morning/afternoon. Never repeat a restaurant. Vary cuisine types.
- **Time assignment**: morning → museums/historic, afternoon → indoor/markets, evening → restaurants/culture
- **Score awareness**: prefer higher-scored places (80+ excellent, 60–80 good) when choosing between options
- **Restaurants**: use `sub_category` and `cuisine_type` for matching
- **Attractions**: prefer places whose `sub_category` matches user interests; skip if no match unless score >85

## Before Submitting

Quick checklist:
- [ ] `days` array has EXACTLY the right count (Trip Duration value)
- [ ] Each day has 2–5 stops (last day can be 2)
- [ ] No duplicate restaurants
- [ ] Every user interest covered by at least one stop
- [ ] Every stop has a why_recommended
"""


def _build_retry_note(last_error: str) -> str:
    """
    Build a targeted retry note based on the specific validation error.

    Parses the error message to detect missing fields and provide
    focused guidance to the LLM so it can fix the problem on retry.

    Pydantic ``ValidationError`` format::

        1 validation error for ItineraryPlan
        accommodation_suggestions.2.lat
          Field required [type=missing, ...]
              ^-- field path is on the line BEFORE `Field required`
    """
    error_lower = last_error.lower()

    # Extract field names from Pydantic ValidationError format.
    # The field path (e.g. "accommodation_suggestions.2.lat") appears on its own
    # line, followed by an indented line with "Field required".
    def _extract_missing_fields(text: str) -> list[str]:
        """Parse Pydantic error text and extract missing field names."""
        lines = text.split("\n")
        fields: list[str] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "field required" in stripped.lower() and i > 0:
                # The field path is on the line above (may have leading spaces)
                prev = lines[i - 1].strip()
                if prev and "." in prev:
                    # Extract just the field name from paths like
                    # "accommodation_suggestions.2.lat" → "lat"
                    field_name = prev.rsplit(".", 1)[-1]
                    if field_name not in fields:
                        fields.append(field_name)
        return fields

    # Detect missing fields in stops
    if "stop" in error_lower and "field required" in error_lower:
        return (
            f"\n\nIMPORTANT: Your previous itinerary was invalid \u2014 "
            f"stops are missing required fields. "
            f"Error: {last_error}. "
            f"\nEvery stop MUST include ALL required fields: id, name, category, "
            f"sub_category, lat, lon, why_recommended, estimated_duration_minutes, "
            f"suggested_time_of_day. Ensure every stop has lat and lon populated."
        )

    # Detect day-count mismatch (e.g. 1 day for a 2-day trip)
    if "day(s) but trip duration is" in error_lower:
        parts = last_error.split("but Trip Duration is")
        expected = parts[-1].strip().split()[0] if len(parts) > 1 else "?"
        return (
            f"\n\nCRITICAL: Your previous itinerary had the WRONG number of days. "
            f"Error: {last_error}. "
            f"\nYou MUST create EXACTLY {expected} entries in the `days` array. "
            f"Each entry is one full day with stops. Use the candidate places "
            f"provided and spread them across ALL {expected} days. "
            f"Double-check your output before submitting."
        )

    # Detect empty days
    if "empty 'days'" in error_lower or "no day" in error_lower:
        return (
            f"\n\nIMPORTANT: Your previous itinerary was invalid \u2014 "
            f"it had no day-by-day stops. "
            f"Error: {last_error}. "
            f"\nYou MUST create a complete itinerary with actual stops "
            f"for each day. Fill the `days` array with real stops "
            f"using the candidate places provided."
        )

    # Generic fallback - include the actual error
    return (
        f"\n\nIMPORTANT: Your previous itinerary was invalid. "
        f"Error: {last_error}. "
        f"\nYou MUST create a complete itinerary with valid stops "
        f"for each day. Fill the `days` array with real stops "
        f"using the candidate places provided. Ensure all required "
        f"fields are populated for every stop."
    )


def _build_retry_prompt(
    synthesized_request: str,
    duration_days: int,
    city: str,
    attractions_restaurants: list,
    last_error: str,
) -> str:
    """
    Build a retry user prompt with the error feedback baked into the
    primary instruction, replacing the original prompt entirely.

    This is more effective than appending a HumanMessage because LLMs
    in structured-output mode treat the primary user instruction as
    the authoritative schema-filling task, while appended messages are
    weaker corrections that can be deprioritized.
    """
    retry_note = _build_retry_note(last_error)
    return f"""PREVIOUS ATTEMPT REJECTED

{retry_note}

User Request: {synthesized_request}
Trip Duration: {duration_days} days

Candidate Attractions & Restaurants in {city} ({len(attractions_restaurants)}):
{json.dumps(attractions_restaurants, indent=None, ensure_ascii=False)}

Generate the itinerary now. REMEMBER: {duration_days} days exactly!
"""



def _trim_for_prompt(place: dict) -> dict:
    """
    Reduce a place record to only the information needed
    by the LLM for itinerary planning.

    Strips photos, maps_link, address, and other verbose fields
    — consistent with the validator's _strip_unnecessary_fields().
    """
    trimmed = {
        "id": place["id"],
        "name": place["name"],
        "category": place["category"],
        "lat": round(place["lat"], 3),  # 3dp ≈ 111m accuracy — sufficient for proximity grouping
        "lon": round(place["lon"], 3),
        "score": round(place.get("composite_score", place.get("popularity_score", 0))),
    }
    # Keep sub_category for attractions so the LLM can match against
    # user interests. Restaurants use cuisine_type instead of sub_category
    # for matching (e.g. "italian", "local cuisine").
    if place.get("category") == "restaurant":
        sub = place.get("sub_category", "")
        if sub:
            trimmed["sub_category"] = sub
        if place.get("cuisine_type"):
            trimmed["cuisine_type"] = place["cuisine_type"]
    elif place.get("category") != "hotel":
        sub = place.get("sub_category", "")
        if sub:
            trimmed["sub_category"] = sub
    # Hotels are handled by the dedicated Hotel Agent, not the planner.
    # Hotel candidates are excluded from the planner's prompt entirely.
    return trimmed




async def run_planning_agent(state: TripState, on_retry=None) -> TripState:
    """
    Main Planning Agent workflow.

    Now receives pre-ranked candidates from the Candidate Scorer
    instead of doing its own candidate selection.

    Args:
        state:    LangGraph workflow state.
        on_retry: Optional async callback ``(attempt, max, reason)`` for
                  reporting intermediate progress during LLM retries.
    """

    # ── Clear stale state from previous retries ────────────────────────
    # If the pipeline loops back (e.g. after validation failure), leftover
    # values from the first pass can leak through.  Clear them so the
    # downstream nodes (optimizer → validator) start fresh.
    #
    # IMPORTANT: Read and preserve validation feedback BEFORE clearing,
    # so the LLM knows why the previous itinerary was rejected.
    prev_validation = state.get("validation")
    prev_issue = (prev_validation or {}).get("issue", "") if prev_validation else ""
    prev_suggestion = (prev_validation or {}).get("suggestion", "") if prev_validation else ""

    state["draft_itinerary"] = None
    state["optimized_itinerary"] = None
    state["is_valid"] = None
    state["error"] = None

    # Extract trip information from workflow state.
    user_message = state.get("user_message", "")
    profile = state.get("profile")
    city = state.get("destination_city")
    duration_days = state.get("duration_days", 3) or 3

    # ---------------------------------------------------------
    # Read pre-ranked candidates from upstream services.
    # The Place Retriever filtered, the Candidate Scorer scored
    # and diversity-optimized. The planner just reasons over them.
    # ---------------------------------------------------------
    candidates = state.get("candidate_places") or []

    if not candidates:
        state["error"] = "Planning Agent received no candidate places from Candidate Scorer"
        return state

    # Trim place objects to essential planning information.
    trimmed = [_trim_for_prompt(p) for p in candidates]

    # Build a richer user request from profile context.
    # The raw user_message may be terse (e.g. "resort") — synthesize
    # a meaningful request from the profile so the LLM has context.
    interests = profile.get("interests") or [] if profile else []
    style = profile.get("travel_style") or "" if profile else ""
    food = profile.get("food_preferences") or [] if profile else []
    accommodation = profile.get("accommodation_preferences") or [] if profile else []

    synthesized_request = user_message
    if len(user_message.split()) <= 5 and (interests or style or food):
        # Terse request — enrich with profile context
        msg_lower = user_message.lower()
        parts = []
        if style:
            parts.append(f"{style} style")
        if interests:
            parts.append(f"interested in {', '.join(interests)}")
        if food:
            parts.append(f"loves {', '.join(food)}")
        # Only add accommodation if not already mentioned in user message
        if accommodation and accommodation[0].lower() not in msg_lower:
            parts.append(f"prefers {', '.join(accommodation)}")
        if parts:
            synthesized_request = f"{user_message} ({'; '.join(parts)})"

    # Hotels are handled by the dedicated Hotel Agent, so they are excluded
    # from the planner's prompt. Only attractions and restaurants are sent.
    attractions_restaurants = [p for p in trimmed if p.get("category") != "hotel"]

    # ── Validation feedback from previous pipeline run ──────────
    # If the pipeline looped back (validator → planner retry), include
    # the validation issue and suggestion so the planner can fix them.
    validation_feedback = ""
    if prev_issue:
        feedback_parts = [f"Previous itinerary was rejected: {prev_issue}"]
        if prev_suggestion:
            feedback_parts.append(f"Suggestion: {prev_suggestion}")
        validation_feedback = (
            f"\n\n## Feedback from previous attempt\n"
        )
        validation_feedback += "\n".join(f"- {p}" for p in feedback_parts)
        validation_feedback += (
            f"\nPlease address this feedback in your new itinerary."
        )

    # Construct the user prompt
    prompt = f"""User Request: {synthesized_request}
Trip Duration: {duration_days} days

Candidate Attractions & Restaurants in {city} ({len(attractions_restaurants)}):
{json.dumps(attractions_restaurants, indent=None, ensure_ascii=False)}{validation_feedback}

Generate the itinerary now.
"""

    # LangChain message structure.
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    # ── LLM call with structured output + retry ───────────────────
    # Uses Pydantic-based ``.with_structured_output(ItineraryPlan)`` to
    # guarantee valid JSON with all required keys (including ``days``).
    # ``invoke_with_fallback`` handles key rotation and retry on both
    # rate-limit (429) and transient (503) errors internally.
    #
    # IMPORTANT: On retry, we REBUILD the full user prompt with error
    # feedback baked into it (rather than appending a HumanMessage).
    # This is critical for ``with_structured_output`` because appended
    # messages are less effective at correcting the LLM's output schema
    # than rebuilding the primary instruction.  The full prompt rebuild
    # gives the LLM a "fresh start" with stronger, contextual guidance.
    # ----------------------------------------------------------------
    max_planner_attempts = 2
    last_planner_error = None
    itinerary = None

    for attempt in range(1, max_planner_attempts + 1):
        try:
            if attempt > 1 and last_planner_error:
                # Rebuild the user prompt with error feedback baked in,
                # replacing the original prompt entirely.  This gives the
                # LLM a fresh instruction that includes the error context
                # rather than an appended note that may be ignored.
                retry_prompt = _build_retry_prompt(
                    synthesized_request=synthesized_request,
                    duration_days=duration_days,
                    city=city,
                    attractions_restaurants=attractions_restaurants,
                    last_error=last_planner_error,
                )
                attempt_messages = [
                    SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                    HumanMessage(content=retry_prompt),
                ]
            else:
                attempt_messages = list(messages)

            response: ItineraryPlan = await invoke_with_fallback(
                "planner", attempt_messages, structured_output=ItineraryPlan,
                on_retry=on_retry,
            )

            # Convert Pydantic model to plain dict for downstream processing.
            parsed = response.model_dump()

            # Validate that the LLM didn't set duration_days to a wrong value.
            # The schema has duration_days with default=3, which can confuse
            # the LLM into thinking the trip is 1 or 3 days.
            llm_duration = parsed.get("duration_days")
            if llm_duration != duration_days:
                raise ValueError(
                    f"Itinerary has wrong 'duration_days' value: {llm_duration} "
                    f"but Trip Duration is {duration_days} days. "
                    f"You MUST set duration_days={duration_days} in your output."
                )

            # Validate non-empty days.
            if not parsed.get("days"):
                raise ValueError("Itinerary has empty 'days' array")

            # Validate day count matches the requested trip duration.
            # The LLM sometimes sets duration_days correctly but only
            # generates a subset of the requested days. This catches that.
            actual_days = len(parsed.get("days", []))
            if actual_days != duration_days:
                raise ValueError(
                    f"Itinerary has {actual_days} day(s) but Trip Duration is "
                    f"{duration_days} days. You MUST create exactly "
                    f"{duration_days} entries in the `days` array."
                )

            # ── Fix time-of-day ordering within each day ─────────────
            # The LLM sometimes assigns suggested_time_of_day tags in
            # non-chronological order (e.g. Morning → Afternoon → Morning).
            # Sort stops chronologically so downstream agents see a
            # sensible sequence.
            _TIME_ORDER = {"morning": 0, "afternoon": 1, "evening": 2}
            for day in parsed.get("days", []):
                stops = day.get("stops", [])
                stops.sort(key=lambda s: _TIME_ORDER.get(s.get("suggested_time_of_day", ""), 1))
                day["stops"] = stops

            itinerary = parsed
            logger.info(
                "[Planner] Success on attempt %d/%d — %d days, %d stops",
                attempt, max_planner_attempts,
                len(itinerary.get("days", [])),
                sum(len(d.get("stops", [])) for d in itinerary.get("days", [])),
            )
            break  # Success — exit retry loop

        except Exception as e:
            last_planner_error = str(e)
            logger.warning(
                "[Planner] Attempt %d/%d failed: %s",
                attempt, max_planner_attempts, last_planner_error,
            )
            # Report retry via the callback if available
            # (distinct from LLM-level retries handled by invoke_with_fallback)
            if on_retry:
                await on_retry(
                    attempt, max_planner_attempts,
                    f"Adjusting itinerary plan (attempt {attempt}/{max_planner_attempts})"
                )
            if attempt == max_planner_attempts:
                logger.error(
                    "[Planner] All %d attempts exhausted: %s",
                    max_planner_attempts, last_planner_error,
                )
                state["error"] = (
                    f"Planning Agent failed after {max_planner_attempts} "
                    f"attempts: {last_planner_error}"
                )
                return state

    # ---------------------------------------------------------
    # Hydration: reattach full metadata for selected places.
    # ---------------------------------------------------------
    all_available = state.get("filtered_places") or candidates
    place_index = {p["id"]: p for p in all_available}

    # Enrich itinerary stops.
    for day in itinerary.get("days", []):
        for stop in day.get("stops", []):
            full = place_index.get(stop.get("id"))
            if full:
                stop["photos"] = full.get("photos", [])[:1]
                stop["address"] = full.get("address")
                stop["maps_link"] = full.get("maps_link")
                # Reattach cuisine_type if available (the LLM may omit it)
                if full.get("cuisine_type") and not stop.get("cuisine_type"):
                    stop["cuisine_type"] = full["cuisine_type"]
                # Fallback lat/lon from DB if the LLM omitted them
                if not stop.get("lat"):
                    stop["lat"] = full.get("lat", 0.0)
                if not stop.get("lon"):
                    stop["lon"] = full.get("lon", 0.0)



    # Store successful itinerary in workflow state.
    # Hotels are NOT enriched here — that's handled by the Hotel Agent.
    state["draft_itinerary"] = itinerary

    # Track how many planning attempts have been made.
    state["planning_attempts"] = (
        state.get("planning_attempts", 0) + 1
    )

    # Log the planning outcome for pipeline traceability.
    total_stops = sum(
        len(day.get("stops", []))
        for day in itinerary.get("days", [])
    )
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[Planner] {len(candidates)} candidates → "
           f"{len(itinerary.get('days', []))} days, "
           f"{total_stops} stops"]
    )

    return state