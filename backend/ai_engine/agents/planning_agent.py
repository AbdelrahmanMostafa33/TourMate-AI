"""
Planning Agent — Stage 4 of the multi-agent pipeline.

The LLM's job is to REASON, not search. It receives:
1. User request + profile summary
2. Pre-ranked candidate places (15–30 from Ranking Agent)

It produces a structured day-by-day itinerary choosing from candidates.

Uses Pydantic-based structured output (``with_structured_output``) to guarantee
valid JSON with the required ``days`` key, eliminating manual extraction/repair.
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from ai_engine.llm_config import invoke_with_fallback
from ai_engine.graph.state import TripState
from ai_engine.schemas.planning_schema import ItineraryPlan
from ai_engine.utils.json_utils import repair_missing_commas as _repair_missing_commas

logger = logging.getLogger(__name__)


# System prompt that defines the Planning Agent's role and rules.
# The JSON schema is enforced by Pydantic's structured output — the prompt
# focuses on reasoning rules rather than formatting instructions.
PLANNER_SYSTEM_PROMPT = """
You are the Planning Agent for TourMate AI. Create a structured, multi-day travel itinerary.

You will receive:
1. User request with trip context (preferences, interests, duration)
2. Dimension scores (luxury, culture, adventure) if available
3. Candidate attractions & restaurants (already ranked by relevance) — these go in day stops
4. Candidate hotels (listed separately) — these go in accommodation_suggestions

## Scoring Reference
- Each place has a `score` (0–100). Higher = more relevant to the user.
- A score above 80 is excellent; 60–80 is good; below 60 is a weaker match.
- Prefer higher-scored places when choosing between options for the same time slot.

## Planning Rules

### Stops per day
- **2–5 stops per day**. Last day can be lighter with just 2 morning stops.
- Never create empty days or "departure day" entries with no stops.
- If you have fewer candidates than needed, use fewer stops per day rather than padding with low-score places.

### Meal breaks
- **Insert a lunch break between morning and afternoon stops** (12:00–13:30).
- If a stop is a restaurant, place it at a natural meal time (lunch ~12:00, dinner ~18:00–19:00).
- Do NOT schedule 3 consecutive stops without a food break.
- `estimated_duration_minutes` for restaurants: 60–90 min.

### Restaurant cuisine diversity
- **CRITICAL: Never repeat the same restaurant on multiple days.** Each restaurant meal should be a different establishment.
- **Vary cuisine types across your restaurant picks.** If you used "Fast Food & Street Food" for one meal, pick a different cuisine type (e.g. "Restaurant", "Cafe / Coffee Shop", "Bakery & Desserts") for the next.
- Each restaurant candidate has a `cuisine_type` field — use it to ensure diversity.
- Example of what NOT to do: picking Koshary Abou Tarek for all 3 days. Instead, pick Koshary Abou Tarek (street food) one day, a different Restaurant-type place another, and a Cafe for the third.

### Time-of-day assignment
- **Morning (09:00–12:00)**: Museums, historic sites, walking tours — cooler temperatures, fewer crowds.
- **Afternoon (13:30–17:00)**: Indoor attractions, markets, shopping — avoid midday heat for outdoor sites.
- **Evening (17:00–21:00)**: Restaurants, waterfront walks, cultural shows, rooftop views.
- Avoid scheduling outdoor attractions (parks, pyramids, waterfront) in midday heat (12:00–14:00).

### Category mixing
- Mix categories: don't stack 3 of the same category in a row.
- Alternate indoor and outdoor attractions where possible.
- Use `interest_tags` on each place to verify it matches the user's interests.

### Geographic awareness
- Group nearby stops on the same day to minimize travel time.
- Consecutive stops should ideally be within 5 km of each other.
- Distance heuristic: 0.01° latitude ≈ 1.1 km; 0.01° longitude ≈ 0.9 km at 30°N.
- Place the most important/high-score attraction first in the morning when energy is highest.

### Candidate selection
- For each stop, copy `id`, `name`, `lat`, `lon`, `interest_tags` **exactly** as given — do not invent places.
- Prefer places whose `interest_tags` overlap with the user's interests.
- If a place has no matching `interest_tags`, only include it if the `score` is very high (>85).
- **CRITICAL: Every user interest from the User Profile must appear in at least one stop across the entire itinerary.** Check the user's interests list and verify each one is covered before finalizing. For example, if the user is interested in nightlife, include at least one stop with `sub_category: "nightlife"`. If they want shopping, include at least one `sub_category: "shopping"` stop. Use the `sub_category` field on each candidate to match interests.
  - Interest-to-subcategory mapping: history→"history", nightlife→"nightlife", shopping→"shopping", parks→"parks", museums→"museums", culture→"museums", nature→"nature", religious→"religious", family→"family", family activities→"family", sports→"sports", wellness→"wellness", entertainment→"entertainment", sightseeing→"sightseeing".
  - **Before outputting, scan your itinerary: does every user interest have at least one matching stop? If not, keep selecting until all interests are represented.**

### Hotels
- Hotels are NOT tour stops — they go in `accommodation_suggestions` at the top level.
- Pick 2–3 hotels from the hotel candidates, prioritizing those whose `accommodation_type` matches the user's accommodation preference.
- If multiple hotels match, pick the highest-rated ones covering slightly different vibes (e.g. one near pyramids, one downtown).
- Include `accommodation_type` and `amenities` in accommodation_suggestions.

### Output
- The output schema is provided automatically — fill all fields.
- Every stop MUST have a `why_recommended` explaining why it fits this user (1–2 sentences, reference their interests and the place's score).
- Every accommodation suggestion MUST have a `why_recommended` explaining the choice.
"""


def _trim_for_prompt(place: dict) -> dict:
    """
    Reduce a place record to only the information needed
    by the LLM for itinerary planning.
    """
    trimmed = {
        "id": place["id"],
        "name": place["name"],
        "category": place["category"],
        "sub_category": place.get("sub_category", ""),
        "interest_tags": place.get("interest_tags", []),
        "lat": place["lat"],
        "lon": place["lon"],
        "score": round(place.get("popularity_score", 0), 1),
    }
    # Include cuisine_type for restaurants so the LLM can match food preferences
    if place.get("category") == "restaurant" and place.get("cuisine_type"):
        trimmed["cuisine_type"] = place["cuisine_type"]
    # Include accommodation_type and top amenities for hotels (trimmed to reduce prompt size)
    if place.get("category") == "hotel":
        trimmed["accommodation_type"] = place.get("accommodation_type", "")
        amenities = place.get("amenities", [])
        trimmed["amenities"] = amenities[:3] if len(amenities) > 3 else amenities
        # Hotels don't need verbose interest_tags — just the category is enough
        trimmed["interest_tags"] = ["hotel"]
    return trimmed




async def run_planning_agent(state: TripState) -> TripState:
    """
    Main Planning Agent workflow.

    Now receives pre-ranked candidates from the Ranking Agent
    instead of doing its own candidate selection.
    """

    # ── Clear stale state from previous retries ────────────────────────
    # If the pipeline loops back (e.g. after validation failure), leftover
    # values from the first pass can leak through.  Clear them so the
    # downstream nodes (optimizer → validator) start fresh.
    state["draft_itinerary"] = None
    state["optimized_itinerary"] = None
    state["is_valid"] = None
    state["error"] = None

    # Extract trip information from workflow state.
    user_message = state.get("user_message", "")
    profile = state.get("profile")
    city = state.get("destination_city")
    duration_days = state.get("duration_days", 3)

    # ---------------------------------------------------------
    # Read pre-ranked candidates from upstream agents.
    # The Retrieval Agent filtered, the Ranking Agent scored
    # and diversity-optimized. The planner just reasons over them.
    # ---------------------------------------------------------
    candidates = state.get("candidate_places") or []

    if not candidates:
        state["error"] = "Planning Agent received no candidate places from Ranking Agent"
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

    # Separate hotels from attractions/restaurants so the LLM isn't confused
    attractions_restaurants = [p for p in trimmed if p.get("category") != "hotel"]
    hotels = [p for p in trimmed if p.get("category") == "hotel"]

    # Extract unique info (dimension scores) that synthesized_request doesn't have
    profile_dimensions = []
    if profile:
        for dim in ["luxury_score", "culture_score", "adventure_score"]:
            val = profile.get(dim)
            if val is not None:
                profile_dimensions.append(f"{dim.replace('_', ' ').capitalize()}: {val}")
    dimension_text = "\n".join(profile_dimensions) if profile_dimensions else ""

    # Construct the user prompt — avoids duplicating info from synthesized_request
    prompt = f"""User Request: {synthesized_request}
Trip Duration: {duration_days} days
{dimension_text}

Candidate Attractions & Restaurants in {city} ({len(attractions_restaurants)}):
{json.dumps(attractions_restaurants, indent=2, ensure_ascii=False)}

Candidate Hotels ({len(hotels)}):
{json.dumps(hotels, indent=2, ensure_ascii=False)}

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
    # If the LLM returns an itinerary with empty days (e.g. under load),
    # we retry up to 2 additional times with error feedback so it can
    # correct itself — this mirrors the old retry logic that was removed
    # during the structured-output refactor.
    # ----------------------------------------------------------------
    max_planner_attempts = 3
    last_planner_error = None
    itinerary = None

    for attempt in range(1, max_planner_attempts + 1):
        try:
            attempt_messages = list(messages)
            if attempt > 1 and last_planner_error:
                retry_note = (
                    f"\n\nIMPORTANT: Your previous itinerary was invalid — "
                    f"it had no day-by-day stops. "
                    f"Error: {last_planner_error}. "
                    f"You MUST create a complete itinerary with actual stops "
                    f"for each day.  Fill the `days` array with real stops "
                    f"using the candidate places provided."
                )
                attempt_messages.append(HumanMessage(content=retry_note))

            response: ItineraryPlan = await invoke_with_fallback(
                "planner", attempt_messages, structured_output=ItineraryPlan,
            )

            # Convert Pydantic model to plain dict for downstream processing.
            parsed = response.model_dump()

            # Validate non-empty days.
            if not parsed.get("days"):
                raise ValueError("Itinerary has empty 'days' array")

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

    # Enrich accommodation suggestions.
    for hotel in itinerary.get("accommodation_suggestions", []):
        full = place_index.get(hotel.get("id"))
        if full:
            hotel["category"] = full.get("category", "hotel")
            hotel["rating"] = full.get("rating", hotel.get("rating", 0))
            hotel["accommodation_type"] = full.get("accommodation_type", "")
            hotel["amenities"] = full.get("amenities", [])
            hotel["photos"] = full.get("photos", [])[:1]
            hotel["address"] = full.get("address")
            hotel["maps_link"] = full.get("maps_link")

    # Store successful itinerary in workflow state.
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
    n_hotels = len(itinerary.get("accommodation_suggestions", []))
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[Planner] {len(candidates)} candidates → "
           f"{len(itinerary.get('days', []))} days, "
           f"{total_stops} stops, {n_hotels} hotels"]
    )

    return state