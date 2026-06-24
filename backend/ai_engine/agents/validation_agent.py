"""
Validation Agent — Stage 6 of the multi-agent pipeline.

Two-layer validation:
1. Programmatic checks (deterministic, fast, catches real issues)
2. LLM quality check (catches subjective issues)
"""

import json
import re
from ai_engine.graph.state import TripState
from ai_engine.tools.haversine import haversine
from ai_engine.llm_config import invoke_with_fallback
from langchain_core.messages import SystemMessage, HumanMessage


# ── Programmatic Validation Thresholds ───────────────────────────────────────

MAX_DAILY_TRAVEL_MINUTES = 180    # 3 hours of travel per day
MAX_DAILY_STOPS = 8               # No more than 8 stops per day
MIN_DAILY_STOPS = 3               # At least 2 stops per day
MAX_CONSECUTIVE_CATEGORY = 2      # No more than 2 of same category in a row
MIN_TOTAL_DAYS = 1                # At least 1 day planned
MAX_DISTANCE_BETWEEN_STOPS_KM = 40  # Sanity check for consecutive stops

# Max length to truncate why_recommended to before sending to LLM
_MAX_WHY_LENGTH = 150


# ── Field Stripper (saves tokens for LLM prompt) ─────────────────────────────

_FIELDS_STOP_KEEP = {
    "id", "name", "category", "sub_category", "lat", "lon",
    "estimated_duration_minutes", "suggested_time_of_day",
    "travel_time_to_next_minutes", "transport_mode",
    "interest_tags", "rating", "cuisine_type",
}

_FIELDS_HOTEL_KEEP = {
    "id", "name", "accommodation_type", "rating",
    "category", "lat", "lon",
}

_FIELDS_DAY_KEEP = {
    "day_number", "theme", "stops", "total_travel_time_minutes",
}


def _strip_unnecessary_fields(itinerary: dict) -> dict:
    """
    Strip verbose fields (photos, maps_link, address, amenities, etc.)
    from the itinerary before sending it to the LLM prompt.

    Only fields relevant for quality validation are kept:
      - stop names, categories, lat/lon, duration, time-of-day
      - hotel names, type, rating
      - day themes, travel times
    """
    if not itinerary:
        return itinerary

    pruned = {}

    # Carry over top-level keys that matter
    for key in ("destination", "duration_days", "destination_city"):
        if key in itinerary:
            pruned[key] = itinerary[key]

    # ── Prune accommodation_suggestions ─────────────────────────────
    hotels = itinerary.get("accommodation_suggestions", [])
    pruned["accommodation_suggestions"] = []
    for h in hotels:
        pruned_h = {k: h[k] for k in _FIELDS_HOTEL_KEEP if k in h}
        why = h.get("why_recommended", "")
        if why:
            pruned_h["why_recommended"] = why if len(why) <= _MAX_WHY_LENGTH else why[:_MAX_WHY_LENGTH - 3] + "..."
        pruned["accommodation_suggestions"].append(pruned_h)

    # ── Prune days ──────────────────────────────────────────────────
    days = itinerary.get("days", [])
    pruned["days"] = []
    for d in days:
        pruned_d = {k: d[k] for k in _FIELDS_DAY_KEEP if k in d}
        pruned_stops = []
        for s in d.get("stops", []):
            pruned_s = {k: s[k] for k in _FIELDS_STOP_KEEP if k in s}
            why = s.get("why_recommended", "")
            if why:
                pruned_s["why_recommended"] = why if len(why) <= _MAX_WHY_LENGTH else why[:_MAX_WHY_LENGTH - 3] + "..."
            pruned_stops.append(pruned_s)
        pruned_d["stops"] = pruned_stops
        pruned["days"].append(pruned_d)

    return pruned


# ── LLM Validation Prompt ───────────────────────────────────────────────────

VALIDATOR_SYSTEM_PROMPT = """
You are the Validation Agent for TourMate AI. Your goal is to check the feasibility and quality of a generated travel itinerary.

You will be provided with:
1. Optimized Itinerary: The itinerary generated and optimized by previous agents.
2. User Request: The original user request.
3. Programmatic Check Results: Issues already caught by deterministic checks.

Your task:
- Focus on QUALITY issues that programmatic checks cannot catch:
  - Does the itinerary flow logically (e.g., not jumping across the city)?
  - Are the themes per day coherent?
  - Is the pacing reasonable (not too rushed, not too empty)?
  - Do the recommendations match the user's request?
- Rate the itinerary on a scale of 0-100.
- Respond ONLY with a valid JSON object.

JSON schema:
{{
  "is_valid": boolean,
  "score": integer,
  "issues": list[string],
  "suggestions": list[string]
}}
"""


def _run_programmatic_checks(itinerary: dict) -> list[str]:
    """
    Deterministic checks that catch real feasibility issues.
    Returns a list of issue strings (empty if all checks pass).
    """
    issues = []
    days = itinerary.get("days", [])

    # ── Check 1: Minimum days ──
    if len(days) < MIN_TOTAL_DAYS:
        issues.append(f"Itinerary has only {len(days)} day(s), expected at least {MIN_TOTAL_DAYS}")

    for day in days:
        day_num = day.get("day_number", "?")
        stops = day.get("stops", [])

        # ── Check 2: Stops per day ──
        if len(stops) > MAX_DAILY_STOPS:
            issues.append(f"Day {day_num}: {len(stops)} stops exceeds max of {MAX_DAILY_STOPS}")
        if len(stops) < MIN_DAILY_STOPS:
            issues.append(f"Day {day_num}: only {len(stops)} stop(s), add more activities")

        # ── Check 3: Consecutive same-category stops ──
        consecutive = 1
        for i in range(1, len(stops)):
            prev_cat = stops[i - 1].get("category", "")
            curr_cat = stops[i].get("category", "")
            if prev_cat == curr_cat and prev_cat != "hotel":
                consecutive += 1
                if consecutive > MAX_CONSECUTIVE_CATEGORY:
                    issues.append(
                        f"Day {day_num}: {consecutive} consecutive '{curr_cat}' stops "
                        f"(max {MAX_CONSECUTIVE_CATEGORY})"
                    )
            else:
                consecutive = 1

        # ── Check 4: Total travel time ──
        total_travel = day.get("total_travel_time_minutes", 0)
        if total_travel > MAX_DAILY_TRAVEL_MINUTES:
            issues.append(
                f"Day {day_num}: {total_travel} min travel time "
                f"exceeds {MAX_DAILY_TRAVEL_MINUTES} min limit"
            )

        # ── Check 5: Sanity distance between consecutive stops ──
        for i in range(len(stops) - 1):
            s1, s2 = stops[i], stops[i + 1]
            if s1.get("lat") and s1.get("lon") and s2.get("lat") and s2.get("lon"):
                dist = haversine(s1["lat"], s1["lon"], s2["lat"], s2["lon"])
                if dist > MAX_DISTANCE_BETWEEN_STOPS_KM:
                    issues.append(
                        f"Day {day_num}: Stop '{s1.get('name', '?')}' to "
                        f"'{s2.get('name', '?')}' is {dist:.1f}km — too far"
                    )

    # ── Check 6: Accommodation suggestions ──
    hotels = itinerary.get("accommodation_suggestions", [])
    if len(hotels) == 0:
        issues.append("No accommodation suggestions provided")
    elif len(hotels) > 5:
        issues.append(f"{len(hotels)} hotel suggestions is too many (max 5)")

    # ── Check 7: Time-of-day ordering within each day ──
    _TIME_RANK = {"morning": 0, "afternoon": 1, "evening": 2}
    for day in days:
        day_num = day.get("day_number", "?")
        stops = day.get("stops", [])
        prev_rank = -1
        for i, stop in enumerate(stops):
            slot = stop.get("suggested_time_of_day", "")
            rank = _TIME_RANK.get(slot, -1)
            if rank < prev_rank:
                issues.append(
                    f"Day {day_num}: stop #{i + 1} '{stop.get("name", "?")}' "
                    f"has suggested_time_of_day='{slot}' which is out of order "
                    f"(previous was '{stops[i - 1].get("suggested_time_of_day", "?")}')"
                )
            prev_rank = rank

    return issues


async def run_validation_agent(state: TripState, on_retry=None) -> TripState:
    """
    Two-layer validation:
    1. Programmatic checks (deterministic)
    2. LLM quality review (subjective)

    Args:
        state:    LangGraph workflow state.
        on_retry: Optional async callback for reporting intermediate LLM retries.
    """
    optimized = state.get("optimized_itinerary")
    user_message = state.get("user_message", "")

    if not optimized or state.get("error"):
        state["is_valid"] = False
        state["validation"] = {"is_valid": False, "score": 0, "issues": ["No itinerary to validate"]}
        state["agent_messages"] = (
            state.get("agent_messages", [])
            + ["[Validator] valid=False score=0 issues=1 (no itinerary)"]
        )
        return state

    # ── Layer 1: Programmatic checks ──
    prog_issues = _run_programmatic_checks(optimized)

    # If critical issues found, skip LLM and fail fast
    critical = [i for i in prog_issues if "exceeds max" in i or "too far" in i]
    if critical:
        state["is_valid"] = False
        state["validation"] = {
            "is_valid": False,
            "score": 30,
            "issues": prog_issues,
            "suggestions": ["Regenerate with fewer stops or shorter distances"],
        }
        state["agent_messages"] = (
            state.get("agent_messages", [])
            + [f"[Validator] valid=False score=30 "
               f"issues={len(prog_issues)} (critical)"]
        )
        return state

    # ── Layer 2: LLM quality check ──
    prog_context = ""
    if prog_issues:
        prog_context = f"\n\nProgrammatic issues found (non-critical):\n" + "\n".join(f"- {i}" for i in prog_issues)

    # Strip heavy fields (photos, maps_link, address, amenities) before
    # sending to the LLM — these are irrelevant for quality validation
    # and cause token limit exceeded errors on Groq free tier.
    stripped = _strip_unnecessary_fields(optimized)

    prompt = f"""
User Request: {user_message}
Optimized Itinerary:
{json.dumps(stripped, indent=2, ensure_ascii=False)}{prog_context}

Validate the itinerary now.
    """

    messages = [
        SystemMessage(content=VALIDATOR_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = await invoke_with_fallback("validator", messages, on_retry=on_retry)
        raw = response.content.strip()
        fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
        if fence:
            raw = fence.group(1).strip()
        brace_start = raw.find("{")
        brace_end = raw.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            raw = raw[brace_start:brace_end + 1]
        llm_result = json.loads(raw)

        # Merge programmatic and LLM issues
        all_issues = prog_issues + llm_result.get("issues", [])
        llm_result["issues"] = all_issues

        # If programmatic issues exist, lower the score
        if prog_issues:
            llm_result["score"] = max(llm_result.get("score", 50) - len(prog_issues) * 5, 0)

        state["is_valid"] = llm_result.get("is_valid", True) and len(critical) == 0
        state["validation"] = llm_result

    except Exception as e:
        # LLM failed — fall back to programmatic result only
        state["is_valid"] = len(critical) == 0
        state["validation"] = {
            "is_valid": len(critical) == 0,
            "score": 50 if not prog_issues else 30,
            "issues": prog_issues + [f"LLM validation failed: {str(e)}"],
            "suggestions": [],
        }

    # Log validation result for pipeline traceability.
    val = state.get("validation", {})
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[Validator] valid={state.get('is_valid')} "
           f"score={val.get('score', '?')} "
           f"issues={len(val.get('issues', []))}"]
    )

    return state
