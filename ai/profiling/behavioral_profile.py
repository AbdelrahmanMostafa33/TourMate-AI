# ai/profiling/behavioral_profile.py

from typing import Optional
from ai.graph.state import BehavioralProfile


def get_slider_label(value: Optional[int], low_label: str, high_label: str, threshold: int = 50) -> str:
    """
    Converts a 0–100 slider value into a human-readable label.

    Args:
        value: The slider integer (0–100), or None if missing.
        low_label: Label for values below threshold.
        high_label: Label for values above or equal to threshold.
        threshold: Cutoff between low and high (default 50).

    Returns:
        A readable string label, or "unknown" if value is None.
    """
    if value is None:
        return "unknown"
    return high_label if value >= threshold else low_label


def get_budget_label(budget_level: Optional[int]) -> str:
    """Returns a budget description string from a 0–100 slider."""
    if budget_level is None:
        return "unknown"
    if budget_level > 66:
        return "luxury"
    elif budget_level > 33:
        return "moderate"
    return "budget-conscious"


def profile_to_text(profile: BehavioralProfile) -> str:
    """
    Converts a BehavioralProfile into a plain-text summary.

    Used by the planner agent to inject profile context into prompts.

    Args:
        profile: The loaded BehavioralProfile from TripState.

    Returns:
        A formatted string describing the user's travel preferences.
    """
    lines = []

    if profile.get("persona_name"):
        lines.append(f"Persona: {profile['persona_name']}")

    if profile.get("persona_bio"):
        lines.append(f"Description: {profile['persona_bio']}")

    lines.append(f"Budget style: {get_budget_label(profile.get('budget_level'))}")

    lines.append(
        f"Activity preference: "
        f"{get_slider_label(profile.get('adventure_relaxing'), 'relaxing', 'adventurous')}"
    )

    lines.append(
        f"Focus: "
        f"{get_slider_label(profile.get('nature_culture'), 'nature-focused', 'culture-focused')}"
    )

    if profile.get("interests"):
        lines.append(f"Interests: {', '.join(profile['interests'])}")

    if profile.get("dining_preferences"):
        lines.append(f"Dining: {', '.join(profile['dining_preferences'])}")

    if profile.get("travel_companion"):
        lines.append(f"Travelling: {profile['travel_companion']}")

    return "\n".join(lines)


def is_profile_complete(profile: BehavioralProfile) -> bool:
    """
    Returns True if the profile has enough data to personalize planning.

    A profile is considered complete if the quiz was finished AND
    at least one interest was provided.
    """
    return profile.get("quiz_completed", False) and len(profile.get("interests", [])) > 0