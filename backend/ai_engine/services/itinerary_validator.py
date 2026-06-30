"""
Itinerary Validator — Stage 6 of the pipeline.

Two-layer validation:
1. Programmatic checks delegated to ``ai_engine.evaluation.feasibility_checker``
2. LLM quality check (catches subjective issues)
"""

import json
import re
from ai_engine.graph.state import TripState
from ai_engine.evaluation.feasibility_checker import run_programmatic_checks
from ai_engine.evaluation.itinerary_metrics import compute_all_metrics
from ai_engine.llm import invoke_with_fallback
from langchain_core.messages import SystemMessage, HumanMessage

# ── LLM Prompt Token Budget ──────────────────────────────────────────────────

_MAX_WHY_LENGTH = 150

# ── Field Stripper (saves tokens for LLM prompt) ─────────────────────────────

_FIELDS_STOP_KEEP = {
    "id", "name", "category", "sub_category", "lat", "lon",
    "estimated_duration_minutes", "suggested_time_of_day",
    "travel_time_to_next_minutes", "transport_mode",
    "rating", "cuisine_type",
}

_FIELDS_HOTEL_KEEP = {
    "id", "name", "accommodation_type", "rating",
    "category", "lat", "lon",
}

_FIELDS_DAY_KEEP = {
    "day_number", "theme", "stops", "total_travel_time_minutes",
}

def _strip_unnecessary_fields(itinerary: dict) -> dict:
    """Strip verbose fields from the itinerary before sending to the LLM prompt."""
    if not itinerary:
        return itinerary

    pruned = {}
    for key in ("destination", "duration_days", "destination_city"):
        if key in itinerary:
            pruned[key] = itinerary[key]

    # Strip accommodation suggestions entirely since they are handled
    # in the post-approval hotel selection phase. Keeping them in the
    # prompt wastes tokens and may trigger false-positive validation flags.
    hotels = itinerary.get("accommodation_suggestions", [])
    if hotels:
        pruned["accommodation_suggestions"] = []
        for h in hotels:
            pruned_h = {k: h[k] for k in _FIELDS_HOTEL_KEEP if k in h}
            why = h.get("why_recommended", "")
            if why:
                pruned_h["why_recommended"] = why if len(why) <= _MAX_WHY_LENGTH else why[:_MAX_WHY_LENGTH - 3] + "..."
            pruned["accommodation_suggestions"].append(pruned_h)

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

VALIDATOR_SYSTEM_PROMPT = """
You are the Itinerary Validator for TourMate AI. Your goal is to check the feasibility and quality of a generated travel itinerary.

You will be provided with:
1. Optimized Itinerary: The itinerary generated and optimized by previous agents.
2. User Request: The original user request.
3. Programmatic Check Results: Issues already caught by deterministic checks.
4. Trip Profile: The user's declared travel preferences, which may have been enriched
   by image analysis (e.g. a photo of a beach may have inferred ``travel_style``).

Your task:
- Focus on QUALITY issues that programmatic checks cannot catch:
  - Does the itinerary flow logically (e.g., not jumping across the city)?
  - Are the themes per day coherent?
  - Is the pacing reasonable (not too rushed, not too empty)?
  - Do the recommendations match the user's request?
  - Does the itinerary's stop selection match the user's declared ``travel_style``?
    (e.g. ``"cultural"`` should include museums, landmarks, heritage sites;
    ``"adventure"`` should favour outdoor / active stops;
    ``"relaxation"`` should favour spa, beach, park stops)
  - Does the itinerary's pacing align with the user's declared ``pace``?
    (e.g. ``"relaxed"`` → 2–3 stops/day; ``"moderate"`` → 3–5;
    ``"packed"`` → 5–7)

**IMPORTANT**: Accommodation suggestions are handled in a separate
post-approval phase and are NOT part of the pipeline. Do NOT penalize
the itinerary for missing or having too few accommodation suggestions.
Focus validation only on the day-by-day stops, themes, and routing.

- Rate the itinerary on a scale of 0-100.
- Respond ONLY with a valid JSON object.

JSON schema:
{{
  "is_valid": boolean,
  "score": integer,
  "issue": string,
  "suggestion": string
}}
"""

async def validate_itinerary(state: TripState, on_retry=None) -> TripState:
    """
    Two-layer validation:
    1. Programmatic checks (deterministic)
    2. LLM quality review (subjective)
    """
    optimized = state.get("optimized_itinerary")
    user_message = state.get("user_message", "")

    if not optimized or state.get("error"):
        state["is_valid"] = False
        state["validation"] = {
            "is_valid": False,
            "score": 0,
            "issue": "No itinerary to validate",
            "metrics": compute_all_metrics({}, state.get("profile")),
        }
        state["agent_messages"] = (
            state.get("agent_messages", [])
            + ["[ItineraryValidator] valid=False score=0 (no itinerary)"]
        )
        return state

    # Layer 1: Programmatic checks (delegated to feasibility_checker)
    prog_issues = run_programmatic_checks(optimized)

    critical = [i for i in prog_issues if "exceeds max" in i or "too far" in i]
    if critical:
        state["is_valid"] = False
        state["validation"] = {
            "is_valid": False,
            "score": 30,
            "issue": "; ".join(critical),
            "suggestion": "Regenerate with fewer stops or shorter distances",
            "metrics": compute_all_metrics(optimized, state.get("profile")),
        }
        state["agent_messages"] = (
            state.get("agent_messages", [])
            + [f"[ItineraryValidator] valid=False score=30 "
               f"issues={len(prog_issues)} (critical)"]
        )
        return state

    # Layer 2: LLM quality check
    prog_context = ""
    if prog_issues:
        prog_context = f"\n\nProgrammatic issues found (non-critical):\n" + "\n".join(f"- {i}" for i in prog_issues)

    stripped = _strip_unnecessary_fields(optimized)

    # Build profile context (user's declared preferences including image-inferred ones)
    profile = state.get("profile")
    profile_context = ""
    if profile:
        parts = []
        ts = profile.get("travel_style")
        pc = profile.get("pace")
        bl = profile.get("budget_level")
        interests = profile.get("interests") or []
        food_prefs = profile.get("food_preferences") or []
        if ts:
            parts.append(f"travel_style={ts}")
        if pc:
            parts.append(f"pace={pc}")
        if bl:
            parts.append(f"budget_level={bl}")
        if interests:
            parts.append(f"interests={', '.join(interests)}")
        if food_prefs:
            parts.append(f"food_preferences={', '.join(food_prefs)}")
        if parts:
            profile_context = "\nUser Profile: " + " | ".join(parts)

    prompt = f"""
User Request: {user_message}{profile_context}
Optimized Itinerary:
{json.dumps(stripped, indent=None, ensure_ascii=False)}{prog_context}

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

        # Merge all issues into a single string
        llm_issue = llm_result.get("issue", "")
        all_issue_parts = list(prog_issues)
        if llm_issue:
            all_issue_parts.append(llm_issue)
        merged_issue = "; ".join(all_issue_parts) if all_issue_parts else ""

        llm_suggestion = llm_result.get("suggestion", "")

        if prog_issues:
            llm_result["score"] = max(llm_result.get("score", 50) - len(prog_issues) * 5, 0)

        llm_result["issue"] = merged_issue
        llm_result["suggestion"] = llm_suggestion

        state["is_valid"] = llm_result.get("is_valid", True) and len(critical) == 0
        state["validation"] = llm_result

    except Exception as e:
        state["is_valid"] = len(critical) == 0
        state["validation"] = {
            "is_valid": len(critical) == 0,
            "score": 50 if not prog_issues else 30,
            "issue": ("; ".join(prog_issues) + f"; LLM validation failed: {str(e)}") if prog_issues else f"LLM validation failed: {str(e)}",
            "suggestion": "",
        }

    # Attach quantitative itinerary metrics to the validation result
    state["validation"]["metrics"] = compute_all_metrics(optimized, state.get("profile"))

    val = state.get("validation", {})
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[ItineraryValidator] valid={state.get('is_valid')} "
           f"score={val.get('score', '?')} "
           f"issues={len(val.get('issues', []))}"]
    )
    return state
