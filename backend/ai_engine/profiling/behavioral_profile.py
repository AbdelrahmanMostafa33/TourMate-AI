# ai_engine/profiling/behavioral_profile.py

from typing import Optional
from ai_engine.graph.state import TripProfile


def profile_to_text(profile: TripProfile) -> str:
    """
    Converts a TripProfile into a plain-text summary for the planner agent.

    Args:
        profile: The loaded TripProfile from TripState.

    Returns:
        A formatted string describing the trip's travel preferences.
    """
    lines = []

    if profile.get("budget_level"):
        lines.append(f"Budget: {profile['budget_level']}")

    if profile.get("travel_style"):
        lines.append(f"Style: {profile['travel_style']}")

    if profile.get("pace"):
        lines.append(f"Pace: {profile['pace']}")

    if profile.get("interests"):
        lines.append(f"Interests: {', '.join(profile['interests'])}")

    if profile.get("food_preferences"):
        lines.append(f"Food: {', '.join(profile['food_preferences'])}")

    if profile.get("accommodation_preferences"):
        lines.append(f"Accommodation: {', '.join(profile['accommodation_preferences'])}")

    if profile.get("luxury_score") is not None:
        lines.append(f"Luxury score: {profile['luxury_score']}")
    if profile.get("culture_score") is not None:
        lines.append(f"Culture score: {profile['culture_score']}")
    if profile.get("adventure_score") is not None:
        lines.append(f"Adventure score: {profile['adventure_score']}")

    return "\n".join(lines)


def is_profile_complete(profile: TripProfile) -> bool:
    """
    Returns True if the profile has enough data to personalize planning.

    A profile is considered complete if confidence_score > 0 and
    at least one interest was provided.
    """
    confidence = profile.get("confidence", 0.0) or 0.0
    return confidence > 0 and len(profile.get("interests", [])) > 0