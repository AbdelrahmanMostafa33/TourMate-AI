"""
Preference Agent — Stage 1 of the multi-agent pipeline.

With the new per-trip profile architecture, the Conversation Agent collects
all profile fields from the user through natural conversation before the
pipeline runs. The Preference Agent's job is now to:

1. Refine the profile using the user's original message context
2. Derive dimension scores (luxury, culture, adventure, shopping, family)
3. Calculate confidence based on profile completeness
4. Write back the enriched profile
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage
from ai_engine.llm_config import invoke_with_fallback
from ai_engine.graph.state import TripState, TripProfile


REFINEMENT_PROMPT = """
You are the Preference Agent for TourMate AI. You receive a complete
travel profile collected from the user. Your job is to:

1. Verify the profile makes sense given the user's message
2. Suggest any refinements based on nuance in the message

Return a JSON object with ONLY fields you want to override:
{
  "budget_level": "budget" | "moderate" | "luxury" | null,
  "travel_style": "romantic" | "adventure" | "family" | "solo" | "cultural" | "relaxation" | null,
  "pace": "relaxed" | "moderate" | "packed" | null,
  "interests_add": ["new_interest"],
  "interests_remove": ["old_interest"],
  "food_preferences_add": ["new_food"],
  "food_preferences_remove": ["old_food"],
  "accommodation_preferences_add": ["new_accommodation"],
  "accommodation_preferences_remove": ["old_accommodation"],
  "special_focus": string | null
}

Rules:
- Only include fields you want to CHANGE from the existing profile
- Set a field to null or omit it to keep the existing value
- If the profile looks perfect, return an empty object {}
- Respond ONLY with valid JSON, no preamble
"""


def _derive_scores(profile: TripProfile) -> dict:
    """
    Derive dimension scores from the collected profile fields.

    Each score is 0.0 – 1.0, calculated from the categorical profile data.
    These scores are used by downstream agents (ranking, planning) for
    filtering and scoring places.

    Returns a dict with: luxury_score, culture_score, adventure_score,
    shopping_score, family_score.
    """
    scores = {
        "luxury_score": 0.5,
        "culture_score": 0.5,
        "adventure_score": 0.5,
        "shopping_score": 0.3,
        "family_score": 0.3,
    }

    # ── Luxury Score ──────────────────────────────────────────────
    budget_map = {"budget": 0.15, "moderate": 0.5, "luxury": 0.9}
    scores["luxury_score"] = budget_map.get(profile.get("budget_level"), 0.5)

    # Boost if high-end accommodation
    acc = [a.lower() for a in (profile.get("accommodation_preferences") or [])]
    if any(a in ("resort", "boutique hotel", "luxury hotel") for a in acc):
        scores["luxury_score"] = min(1.0, scores["luxury_score"] + 0.15)
    if any(a in ("hostel", "camping") for a in acc):
        scores["luxury_score"] = max(0.0, scores["luxury_score"] - 0.2)

    # ── Culture Score ─────────────────────────────────────────────
    interests_lower = {i.lower() for i in (profile.get("interests") or [])}
    culture_keywords = {"history", "art", "museums", "architecture", "heritage", "culture", "traditions"}
    culture_hits = len(interests_lower & culture_keywords)
    scores["culture_score"] = min(1.0, 0.3 + (culture_hits * 0.15))

    style = (profile.get("travel_style") or "").lower()
    if style == "cultural":
        scores["culture_score"] = min(1.0, scores["culture_score"] + 0.25)

    # ── Adventure Score ───────────────────────────────────────────
    adventure_keywords = {"hiking", "trekking", "adventure", "outdoors", "nature", "diving", "climbing", "safari"}
    adventure_hits = len(interests_lower & adventure_keywords)
    scores["adventure_score"] = min(1.0, 0.2 + (adventure_hits * 0.15))

    if style == "adventure":
        scores["adventure_score"] = min(1.0, scores["adventure_score"] + 0.3)

    pace = (profile.get("pace") or "").lower()
    if pace == "packed":
        scores["adventure_score"] = min(1.0, scores["adventure_score"] + 0.1)
    elif pace == "relaxed":
        scores["adventure_score"] = max(0.0, scores["adventure_score"] - 0.15)

    # ── Shopping Score ────────────────────────────────────────────
    shopping_keywords = {"shopping", "markets", "fashion", "souvenirs", "bazaar"}
    shopping_hits = len(interests_lower & shopping_keywords)
    scores["shopping_score"] = min(1.0, 0.15 + (shopping_hits * 0.2))

    # ── Family Score ──────────────────────────────────────────────
    if style == "family":
        scores["family_score"] = 0.85
    else:
        family_keywords = {"kids", "family", "playground", "zoo", "aquarium"}
        family_hits = len(interests_lower & family_keywords)
        scores["family_score"] = min(1.0, 0.2 + (family_hits * 0.25))

    return scores


def _calculate_confidence(profile: TripProfile) -> float:
    """
    Calculate profile confidence (0.0 – 1.0) based on how many
    fields have been filled by the Conversation Agent.
    """
    fields_checked = [
        profile.get("budget_level"),
        profile.get("travel_style"),
        profile.get("pace"),
        bool(profile.get("interests")),
        bool(profile.get("food_preferences")),
        bool(profile.get("accommodation_preferences")),
    ]
    filled = sum(1 for f in fields_checked if f)
    return round(filled / len(fields_checked), 2)


def _build_profile_context(profile: TripProfile) -> str:
    """Convert trip profile into context text for the LLM."""
    lines = []

    if profile.get("budget_level"):
        lines.append(f"Budget: {profile['budget_level']}")
    if profile.get("travel_style"):
        lines.append(f"Travel style: {profile['travel_style']}")
    if profile.get("pace"):
        lines.append(f"Pace: {profile['pace']}")
    if profile.get("interests"):
        lines.append(f"Interests: {', '.join(profile['interests'])}")
    if profile.get("food_preferences"):
        lines.append(f"Food preferences: {', '.join(profile['food_preferences'])}")
    if profile.get("accommodation_preferences"):
        lines.append(f"Accommodation: {', '.join(profile['accommodation_preferences'])}")

    return "\n".join(lines) if lines else "No profile data available."


async def run_preference_agent(state: TripState) -> TripState:
    """
    Main Preference Agent workflow.

    With a complete profile already collected by the Conversation Agent:
    1. Optionally refine from user message context (LLM)
    2. Derive dimension scores from profile fields
    3. Calculate confidence
    4. Store enriched profile in state for downstream agents
    """
    user_message = state.get("user_message", "")
    profile = state.get("profile") or {}
    destination = state.get("destination_city", "")

    # Step 1: Ask LLM to suggest refinements based on user message
    profile_context = _build_profile_context(profile)
    prompt = f"""User Message: "{user_message}"
Destination: {destination or 'not specified'}

Current Profile:
{profile_context}

Review this profile and suggest any refinements based on the user message.
If the profile looks correct, return an empty object {{}}."""

    messages = [
        SystemMessage(content=REFINEMENT_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = await invoke_with_fallback("preference", messages)
        raw = response.content.strip().strip("```json").strip("```").strip()
        refinements = json.loads(raw)
    except (json.JSONDecodeError, AttributeError, Exception) as e:
        refinements = {}
        print(f"[PreferenceAgent] Refinement LLM failed ({e}), using profile as-is")

    # Step 2: Apply refinements to profile
    enriched = dict(profile)

    # Override categorical fields if LLM provided new values
    for field in ("budget_level", "travel_style", "pace"):
        if refinements.get(field):
            enriched[field] = refinements[field]

    # Handle interest list adjustments
    interests = list(enriched.get("interests") or [])
    for add in (refinements.get("interests_add") or []):
        if add not in interests:
            interests.append(add)
    for remove in (refinements.get("interests_remove") or []):
        if remove in interests:
            interests.remove(remove)
    enriched["interests"] = interests

    # Handle food preference adjustments
    foods = list(enriched.get("food_preferences") or [])
    for add in (refinements.get("food_preferences_add") or []):
        if add not in foods:
            foods.append(add)
    for remove in (refinements.get("food_preferences_remove") or []):
        if remove in foods:
            foods.remove(remove)
    enriched["food_preferences"] = foods

    # Handle accommodation preference adjustments
    accs = list(enriched.get("accommodation_preferences") or [])
    for add in (refinements.get("accommodation_preferences_add") or []):
        if add not in accs:
            accs.append(add)
    for remove in (refinements.get("accommodation_preferences_remove") or []):
        if remove in accs:
            accs.remove(remove)
    enriched["accommodation_preferences"] = accs

    # Step 3: Derive dimension scores
    scores = _derive_scores(enriched)
    enriched["luxury_score"] = scores["luxury_score"]
    enriched["culture_score"] = scores["culture_score"]
    enriched["adventure_score"] = scores["adventure_score"]
    enriched["shopping_score"] = scores["shopping_score"]
    enriched["family_score"] = scores["family_score"]

    # Step 4: Calculate confidence
    enriched["confidence"] = _calculate_confidence(enriched)

    # Step 5: Store in state
    state["profile"] = enriched

    # Also produce extracted_preferences for downstream agents
    state["extracted_preferences"] = {
        "budget_level": enriched.get("budget_level"),
        "travel_style": enriched.get("travel_style"),
        "pace": enriched.get("pace"),
        "food_preferences": enriched.get("food_preferences") or [],
        "accommodation_style": (enriched.get("accommodation_preferences") or [None])[0] if enriched.get("accommodation_preferences") else None,
        "interests_from_conversation": enriched.get("interests") or [],
        "special_focus": refinements.get("special_focus"),
    }

    return state
