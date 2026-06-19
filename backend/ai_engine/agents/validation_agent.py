"""
Validation Agent — Stage 6 of the multi-agent pipeline.

Two-layer validation:
1. Programmatic checks (deterministic, fast, catches real issues)
2. LLM quality check (catches subjective issues)
"""

import json
from ai_engine.graph.state import TripState
from ai_engine.tools.haversine import haversine
from ai_engine.llm_config import invoke_with_fallback
from langchain_core.messages import SystemMessage, HumanMessage


# ── Programmatic Validation Thresholds ───────────────────────────────────────

MAX_DAILY_TRAVEL_MINUTES = 180    # 3 hours of travel per day
MAX_DAILY_STOPS = 8               # No more than 8 stops per day
MIN_DAILY_STOPS = 2               # At least 2 stops per day
MAX_CONSECUTIVE_CATEGORY = 2      # No more than 2 of same category in a row
MIN_TOTAL_DAYS = 1                # At least 1 day planned
MAX_DISTANCE_BETWEEN_STOPS_KM = 40  # Sanity check for consecutive stops


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

    return issues


async def run_validation_agent(state: TripState) -> TripState:
    """
    Two-layer validation:
    1. Programmatic checks (deterministic)
    2. LLM quality review (subjective)
    """
    optimized = state.get("optimized_itinerary")
    user_message = state.get("user_message", "")

    if not optimized or state.get("error"):
        state["is_valid"] = False
        state["validation"] = {"is_valid": False, "score": 0, "issues": ["No itinerary to validate"]}
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
        return state

    # ── Layer 2: LLM quality check ──
    prog_context = ""
    if prog_issues:
        prog_context = f"\n\nProgrammatic issues found (non-critical):\n" + "\n".join(f"- {i}" for i in prog_issues)

    prompt = f"""
User Request: {user_message}
Optimized Itinerary:
{json.dumps(optimized, indent=2)}{prog_context}

Validate the itinerary now.
    """

    messages = [
        SystemMessage(content=VALIDATOR_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = await invoke_with_fallback("validator", messages)
        raw_content = response.content.strip().strip("```json").strip("```").strip()
        llm_result = json.loads(raw_content)

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

    return state
