"""
Planning Agent — Stage 4 of the multi-agent pipeline.

The LLM's job is to REASON, not search. It receives:
1. User request + profile summary
2. Pre-ranked candidate places (15–30 from Ranking Agent)

It produces a structured day-by-day itinerary choosing from candidates.
"""

import json
import re
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from ai_engine.llm_config import invoke_with_fallback
from ai_engine.graph.state import TripState
from ai_engine.profiling.behavioral_profile import profile_to_text

logger = logging.getLogger(__name__)


# System prompt that defines the Planning Agent's role, rules,
# and the exact JSON schema expected from the LLM.
PLANNER_SYSTEM_PROMPT = """
You are the Planning Agent for TourMate AI. Create a structured, multi-day travel itinerary.

You will receive:
1. User request (what the user wants)
2. User profile summary (preferences, interests, scores)
3. Pre-filtered candidate places (already ranked by relevance by upstream agents)

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

### Hotels
- Hotels are NOT tour stops — they go in `accommodation_suggestions` at the top level.
- Pick 2–3 hotels from the hotel candidates, prioritizing those whose `accommodation_type` matches the user's accommodation preference.
- If multiple hotels match, pick the highest-rated ones covering slightly different vibes (e.g. one near pyramids, one downtown).
- Include `accommodation_type` and `amenities` in accommodation_suggestions.

### Output
- Output ONLY valid JSON, no preamble, no markdown fences.
- Every stop MUST have a `why_recommended` explaining why it fits this user (1–2 sentences, reference their interests and the place's score).
- Every accommodation suggestion MUST have a `why_recommended` explaining the choice.

JSON schema:
{
  "destination": string,
  "duration_days": integer,
  "accommodation_suggestions": [
    {
      "id": string,
      "name": string,
      "sub_category": string,
      "accommodation_type": string,
      "lat": float,
      "lon": float,
      "why_recommended": string,
      "rating": float,
      "amenities": [string]
    }
  ],
  "days": [
    {
      "day_number": integer,
      "theme": string,
      "stops": [
        {
          "id": string,
          "name": string,
          "category": string,
          "sub_category": string,
          "interest_tags": [string],
          "lat": float,
          "lon": float,
          "why_recommended": string,
          "estimated_duration_minutes": integer,
          "suggested_time_of_day": "morning" | "afternoon" | "evening"
        }
      ]
    }
  ]
}
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
        "rating": place.get("rating", 0),
        "score": round(place.get("popularity_score", 0), 1),
    }
    # Include cuisine_type for restaurants so the LLM can match food preferences
    if place.get("category") == "restaurant" and place.get("cuisine_type"):
        trimmed["cuisine_type"] = place["cuisine_type"]
    # Include accommodation_type and amenities for hotels
    if place.get("category") == "hotel":
        trimmed["accommodation_type"] = place.get("accommodation_type", "")
        trimmed["amenities"] = place.get("amenities", [])
    return trimmed


# ── JSON extraction helpers ─────────────────────────────────────────────────


def _extract_json_from_llm_output(text: str) -> str:
    """Extract a JSON object from LLM output that may contain preamble,
    markdown fences, or trailing commentary.

    Fixes three common LLM output issues:
    1. Preamble text before JSON ("Here is your itinerary: { ... }")
    2. Markdown code fences (```json ... ```)
    3. Trailing commentary after JSON

    Returns the extracted JSON string (still needs json.loads to parse).
    """
    if not text:
        raise ValueError("Empty LLM output")

    # Step 1: Remove markdown code fences if present.
    # Use regex instead of str.strip() to avoid corrupting JSON.
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Step 2: If it already looks like valid JSON, return as-is.
    if text.startswith("{") and text.endswith("}"):
        return text

    # Step 3: Find the first '{' and last '}' to extract the JSON object.
    first_brace = text.find("{")
    last_brace = text.rfind("}")

    if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
        raise ValueError(
            f"No JSON object found in LLM output (first 200 chars: {text[:200]!r})"
        )

    return text[first_brace:last_brace + 1]


def _repair_missing_commas(text: str) -> str:
    """
    Insert missing commas by using json.JSONDecodeError position hints.

    The LLM (especially Gemini) commonly produces JSON with missing commas
    between fields, like:
        {"name": "Museum" "id": "123"}   → missing comma after "Museum"
        {"scores": [1 2 3]}               → missing commas in array
        {"a": 1 {"b": 2}}               → missing comma before nested object

    This function iteratively:
    1. Attempts json.loads()
    2. If it fails with a missing-comma error, inserts a comma at the
       error position and retries (up to 5 iterations).

    Returns the repaired JSON string (which may still be invalid on
    non-comma errors — the caller falls through to _repair_truncated_json).
    """
    repaired = text

    for _ in range(5):
        try:
            json.loads(repaired)
            return repaired  # Valid JSON — done
        except json.JSONDecodeError as e:
            # Only handle missing comma / property name errors here.
            if not ("Expecting '" in e.msg and "delimiter" in e.msg):
                if "Expecting property name" not in e.msg:
                    break  # Non-comma error — let truncation repair handle it
            pos = e.pos
            # Guard: don't insert at end of string
            if pos >= len(repaired):
                break
            if repaired[pos] in (',', '}', ']', ':', ' '):
                break  # Already has comma or structural — different issue

            # If error position points to a key inside a newly-started nested
            # object (e.g. {"a": 1 {"b": 2}}), the comma needs to go BEFORE
            # the opening brace, not before the key string.
            if (pos > 0 and repaired[pos] == '"'
                    and repaired[pos - 1] in ('{', '[')):
                pos = pos - 1

            repaired = repaired[:pos] + ',' + repaired[pos:]
            continue

    return repaired  # Best attempt


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair JSON that was truncated by max_tokens limit.

    Common truncation patterns:
    - Unterminated string: '"name": "Some place' → close the string
    - Missing closing brackets: incomplete days/stops arrays

    Returns the repaired JSON string.
    """
    repaired = text.rstrip()

    # If it's already valid, return as-is.
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        pass

    # Strategy 1: Close an unterminated string at the end.
    # If the last non-whitespace char is not a quote, bracket, or comma,
    # we're likely mid-string or mid-value.
    if repaired and repaired[-1] not in ('"', '}', ']', ',', ':', ' '):
        # Check if we're inside a string (odd number of unescaped quotes)
        in_string = False
        for ch in reversed(repaired):
            if ch == '"':
                in_string = not in_string
        if in_string:
            repaired += '"'

    # Strategy 2: Count unmatched opening brackets and close them.
    open_braces = 0
    open_brackets = 0
    in_str = False
    escape_next = False
    for ch in repaired:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            open_braces += 1
        elif ch == '}':
            open_braces -= 1
        elif ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1

    # Close any unclosed brackets/braces (innermost first)
    closing = ']' * max(open_brackets, 0) + '}' * max(open_braces, 0)
    repaired += closing

    # Validate the repair.
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        # Could not repair — return the best attempt.
        return repaired


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

    # Convert behavioral profile into a text summary for the LLM.
    profile_summary = (
        profile_to_text(profile)
        if profile
        else "No profile available."
    )

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
            parts.append(f"interested in {', '.join(interests[:3])}")
        if food:
            parts.append(f"loves {', '.join(food[:2])}")
        # Only add accommodation if not already mentioned in user message
        if accommodation and accommodation[0].lower() not in msg_lower:
            parts.append(f"prefers {accommodation[0]}")
        if parts:
            synthesized_request = f"{user_message} ({'; '.join(parts)})"

    # Construct the user prompt.
    prompt = f"""
User Request: {synthesized_request}
Trip Duration: {duration_days} days
User Profile:
{profile_summary}

Candidate Places in {city} ({len(trimmed)} pre-filtered and ranked by relevance):
{json.dumps(trimmed, indent=2, ensure_ascii=False)}

Generate the itinerary now.
"""

    # LangChain message structure.
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    # ── LLM call with JSON parse retry ─────────────────────────────
    # Some LLM outputs are malformed (preamble text, truncated JSON,
    # markdown fences).  We retry up to 2 times with increasingly
    # explicit instructions before giving up.
    # ──────────────────────────────────────────────────────────────
    max_attempts = 3
    last_error = None
    itinerary = None

    for attempt in range(1, max_attempts + 1):
        try:
            # On retry, prepend error context so the LLM corrects itself.
            attempt_messages = list(messages)
            if attempt > 1 and last_error:
                retry_note = (
                    f"\n\nIMPORTANT: Your previous output was invalid JSON. "
                    f"Error: {last_error}. "
                    f"Output ONLY the raw JSON object starting with {{ and ending with }}. "
                    f"No preamble, no markdown fences, no trailing text."
                )
                attempt_messages.append(HumanMessage(content=retry_note))

            response = await invoke_with_fallback("planner", attempt_messages)
            raw_text = response.content

            # Robust JSON extraction: handles preamble, markdown fences,
            # and trailing commentary.
            extracted = _extract_json_from_llm_output(raw_text)

            try:
                itinerary = json.loads(extracted)
            except json.JSONDecodeError as parse_err:
                # ── Repair chain ────────────────────────────────────────
                # 1. Try missing comma repair (most common Gemini issue)
                logger.warning(
                    "[Planner] JSON parse failed on attempt %d: %s — attempting comma repair",
                    attempt, parse_err,
                )
                repaired = _repair_missing_commas(extracted)
                try:
                    itinerary = json.loads(repaired)
                    logger.info("[Planner] Comma repair succeeded")
                except json.JSONDecodeError:
                    # 2. Try truncation repair (unclosed brackets, unterminated strings)
                    logger.warning(
                        "[Planner] Comma repair failed — attempting truncation repair",
                    )
                    repaired = _repair_truncated_json(repaired)
                    itinerary = json.loads(repaired)
                    logger.info("[Planner] Truncation repair succeeded")

            # Validate essential structure.
            if not isinstance(itinerary, dict) or "days" not in itinerary:
                raise ValueError(
                    f"LLM output is a valid JSON but missing required 'days' key. "
                    f"Top-level keys: {list(itinerary.keys()) if isinstance(itinerary, dict) else type(itinerary).__name__}"
                )
            if not itinerary.get("days"):
                raise ValueError("Itinerary has empty 'days' array")

            # Success — break out of retry loop.
            break

        except Exception as e:
            last_error = str(e)
            logger.warning(
                "[Planner] Attempt %d/%d failed: %s", attempt, max_attempts, last_error,
            )
            if attempt == max_attempts:
                state["error"] = f"Planning Agent failed after {max_attempts} attempts: {last_error}"
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

    # Enrich accommodation suggestions.
    for hotel in itinerary.get("accommodation_suggestions", []):
        full = place_index.get(hotel.get("id"))
        if full:
            hotel["category"] = full.get("category", "hotel")
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