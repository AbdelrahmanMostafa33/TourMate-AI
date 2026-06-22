
"""
Preference Agent — Stage 1 of the multi-agent pipeline.

The Conversation Agent collects all profile fields from the user before the
pipeline runs. The Preference Agent's job is to:

1. Derive dimension scores (luxury, culture, adventure)
2. Calculate confidence based on profile completeness
3. Build extracted_preferences for downstream agents
4. Write back the enriched profile

Note: The LLM refinement call was removed because it returned redundant
values — the Conversation Agent already captures all preferences.
"""

from ai_engine.graph.state import TripState, TripProfile
from app.models.enums import AccommodationType


# ── Natural Language → AccommodationType Mapping ──────────────────────────

# Maps natural language accommodation phrases to AccommodationType enum values.
# Order matters: more specific phrases first to avoid partial matches.
_ACCOMMODATION_KEYWORDS: list[tuple[str, AccommodationType]] = [
    # Hostel keywords
    ("hostel",         AccommodationType.hostel),
    ("backpacker",     AccommodationType.hostel),
    ("dorm",           AccommodationType.hostel),
    # Resort keywords
    ("resort",         AccommodationType.resort),
    ("beach resort",   AccommodationType.resort),
    ("all-inclusive",  AccommodationType.resort),
    ("spa resort",     AccommodationType.resort),
    # Luxury keywords
    ("luxury",         AccommodationType.luxury),
    ("boutique",       AccommodationType.luxury),
    ("palace",         AccommodationType.luxury),
    ("five star",      AccommodationType.luxury),
    ("5-star",         AccommodationType.luxury),
    ("premium",        AccommodationType.luxury),
    ("high-end",       AccommodationType.luxury),
    ("upscale",        AccommodationType.luxury),
    # Hotel (default) keywords
    ("hotel",          AccommodationType.hotel),
    ("apartment",      AccommodationType.hotel),
    ("airbnb",         AccommodationType.hotel),
    ("motel",          AccommodationType.hotel),
]


def map_accommodation_to_enum(preferences: list[str]) -> str | None:
    """
    Map a list of natural language accommodation preferences to an
    AccommodationType enum value string.

    Checks each preference phrase against keyword mappings.
    Returns the last matching enum value (most recent preference wins),
    or None if no match.
    """
    result = None
    for pref in preferences:
        pref_lower = pref.lower().strip()
        for keyword, acc_type in _ACCOMMODATION_KEYWORDS:
            if keyword in pref_lower:
                result = acc_type.value
                break
    return result





def _derive_scores(profile: TripProfile) -> dict:
    """
    Derive dimension scores from the collected profile fields.

    Each score is 0.0 – 1.0, calculated from the categorical profile data.
    These scores are used by downstream agents (ranking, planning) for
    filtering and scoring places.

    Returns a dict with: luxury_score, culture_score, adventure_score.
    """
    scores = {
        "luxury_score": 0.5,
        "culture_score": 0.5,
        "adventure_score": 0.5,
    }

    # ── Luxury Score ──────────────────────────────────────────────
    budget_map = {
        "budget": 0.15,
        "moderate": 0.5,
        "luxury": 0.9
    }
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





async def run_preference_agent(state: TripState) -> TripState:
    """
    Main Preference Agent workflow.

    With a complete profile already collected by the Conversation Agent:
    1. Derive dimension scores from profile fields
    2. Calculate confidence
    3. Build extracted_preferences for downstream agents
    4. Store enriched profile in state

    Note: The LLM refinement step was removed because it returned redundant
    values — the Conversation Agent already captures all preferences.
    """
    profile = state.get("profile") or {}

    # Step 1: Derive dimension scores
    scores = _derive_scores(profile)
    enriched = dict(profile)
    enriched["luxury_score"] = scores["luxury_score"]
    enriched["culture_score"] = scores["culture_score"]
    enriched["adventure_score"] = scores["adventure_score"]


    # Step 2: Calculate confidence
    enriched["confidence"] = _calculate_confidence(enriched)

    # Step 3: Store enriched profile in state
    state["profile"] = enriched

    # Step 4: Build extracted_preferences for downstream agents
    acc_prefs = enriched.get("accommodation_preferences") or []
    accommodation_type = map_accommodation_to_enum(acc_prefs)

    state["extracted_preferences"] = {
        "budget_level": enriched.get("budget_level"),
        "travel_style": enriched.get("travel_style"),
        "pace": enriched.get("pace"),
        "food_preferences": enriched.get("food_preferences") or [],
        "accommodation_style": acc_prefs[0] if acc_prefs else None,
        "accommodation_type": accommodation_type,
        "interests_from_conversation": enriched.get("interests") or [],
        "special_focus": None,
    }

    return state
