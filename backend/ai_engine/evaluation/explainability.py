"""
Explainability — Human-readable explanations of AI agent decisions.

Provides **deterministic, LLM-free** functions that translate the pipeline's
structured data (metrics, validation results, feasibility checks) into
natural-language explanations suitable for display to end users.

No LLM calls are made — all explanations are computed from the data that
already exists in ``TripState`` at the end of the pipeline.

Usage::

    from ai_engine.evaluation.explainability import (
        explain_validation_decision,
        explain_metric_scores,
        format_full_explanation,
    )

    explanation = format_full_explanation(
        itinerary=state.get("optimized_itinerary"),
        validation=state.get("validation"),
        metrics=state.get("validation", {}).get("metrics"),
        profile=state.get("profile"),
        feasibility_issues=[],
    )
"""

from __future__ import annotations

import re
from typing import Any, Optional


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

_METRIC_LABELS: dict[str, tuple[str, str]] = {
    "category_diversity": ("Category Diversity", "How well the itinerary mixes different types of places"),
    "interest_alignment": ("Interest Match", "How well the places match your stated interests"),
    "pacing": ("Pacing", "Whether the daily schedule feels balanced or rushed"),
    "geographic_coverage": ("Spread", "How geographically spread out the stops are"),
}

_METRIC_THRESHOLDS = {
    "excellent": 0.85,
    "good": 0.70,
    "fair": 0.50,
    "needs_improvement": 0.0,
}

_PACE_DESCRIPTIONS = {
    "relaxed": "a relaxed, unhurried pace",
    "balanced": "a moderate, balanced mix of activities and free time",
    "moderate": "a moderate, well-balanced pace",
    "packed": "a packed schedule with lots to see and do",
}

_STYLE_DESCRIPTIONS = {
    "romantic": "a romantic getaway",
    "adventure": "an adventure-focused trip",
    "family": "a family-friendly experience",
    "solo": "a solo travel experience",
    "cultural": "a cultural immersion",
    "relaxation": "a relaxing retreat",
}


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _rating_label(score: float) -> str:
    """Convert a 0.0-1.0 score to a qualitative label."""
    if score >= _METRIC_THRESHOLDS["excellent"]:
        return "excellent"
    elif score >= _METRIC_THRESHOLDS["good"]:
        return "good"
    elif score >= _METRIC_THRESHOLDS["fair"]:
        return "fair"
    return "needs improvement"


def _pluralize(singular: str, count: int, plural: Optional[str] = None) -> str:
    """Return ``count + word`` with correct pluralization.

    Args:
        singular: The singular form (e.g. ``"interest"``).
        count: How many.
        plural: Optional irregular plural (e.g. ``"categories"``).

    Examples::
        >>> _pluralize("stop", 1)
        "1 stop"
        >>> _pluralize("stop", 3)
        "3 stops"
        >>> _pluralize("category", 2, "categories")
        "2 categories"
    """
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural or singular + 's'}"


def _comma_list(items: list[str], conjunction: str = "and") -> str:
    """Format ``["a", "b", "c"]`` -> ``"a, b, and c"``."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return ", ".join(items[:-1]) + f", {conjunction} {items[-1]}"


# ══════════════════════════════════════════════════════════════════════════════
# Validation Decision Explanation
# ══════════════════════════════════════════════════════════════════════════════


def explain_validation_decision(
    validation: Optional[dict],
    metrics: Optional[dict[str, float]] = None,
    feasibility_issues: Optional[list[str]] = None,
) -> list[str]:
    """
    Explain why the validator accepted or rejected an itinerary.

    Args:
        validation: The ``validation`` dict from ``TripState``
            (with ``is_valid``, ``score``, ``issue``, ``suggestion``).
        metrics: Optional metrics dict from ``compute_all_metrics()``.
        feasibility_issues: Optional list of issues from
            :func:`~ai_engine.evaluation.feasibility_checker.run_programmatic_checks`.

    Returns:
        A list of human-readable explanation sentences.
    """
    lines: list[str] = []

    if not validation:
        lines.append("Itinerary validation was not performed.")
        return lines

    # Fall back to metrics inside validation dict if not provided
    if metrics is None:
        metrics = validation.get("metrics")

    is_valid = validation.get("is_valid", False)
    score = validation.get("score", 0)
    issue = validation.get("issue", "")
    suggestion = validation.get("suggestion", "")

    # ── Overall verdict ─────────────────────────────────────────────────
    if is_valid:
        lines.append(
            f"Passed quality checks with a score of **{score}/100**."
        )
    else:
        lines.append(
            f"Did not pass quality checks (score: **{score}/100**)."
        )

    # ── Key issue ───────────────────────────────────────────────────────
    if issue:
        lines.append(f"Issue: {issue}")

    # ── Suggestions ─────────────────────────────────────────────────────
    if suggestion:
        lines.append(f"Suggestion: {suggestion}")

    # ── Overall metric context ──────────────────────────────────────────
    if metrics and metrics.get("overall", 0) > 0:
        overall = metrics["overall"]
        label = _rating_label(overall)
        lines.append(
            f"Overall itinerary quality is **{label}** "
            f"({overall * 100:.0f}/100)."
        )

    return lines


# ══════════════════════════════════════════════════════════════════════════════
# Metric Score Explanations
# ══════════════════════════════════════════════════════════════════════════════


def explain_metric_scores(metrics: Optional[dict[str, float]]) -> list[str]:
    """
    Generate human-readable explanations for each quantitative metric.

    Args:
        metrics: Dict from :func:`~ai_engine.evaluation.itinerary_metrics.compute_all_metrics`.

    Returns:
        A list of explanation sentences per metric plus overall summary.
    """
    lines: list[str] = []

    if not metrics:
        lines.append("No quality metrics available for this itinerary.")
        return lines

    overall = metrics.get("overall", 0)
    lines.append(f"Overall Quality: {overall * 100:.0f}/100 ({_rating_label(overall)})")
    lines.append("")

    for key, (label, description) in _METRIC_LABELS.items():
        score = metrics.get(key, 0)
        if score == 0 and key != "geographic_coverage":
            continue

        rating = _rating_label(score)
        comment = _metric_comment(key, score)
        lines.append(
            f"  **{label}:** **{score * 100:.0f}%** ({rating})"
        )
        lines.append(f"    {description}")
        if comment:
            lines.append(f"    {comment}")
        lines.append("")

    return lines


def _metric_comment(key: str, score: float) -> str:
    """Generate a qualitative comment for a specific metric score."""
    if score >= 0.85:
        if key == "category_diversity":
            return "Great mix of activities, no two days feel the same."
        elif key == "interest_alignment":
            return "Strong match with your preferences."
        elif key == "pacing":
            return "Well-balanced schedule with comfortable transitions."
        elif key == "geographic_coverage":
            return "Good geographic variety, different areas to explore."
    elif score >= 0.60:
        if key == "category_diversity":
            return "Decent variety, though some categories could be better mixed."
        elif key == "interest_alignment":
            return "Most of your interests are covered."
        elif key == "pacing":
            return "Generally well-paced, though some days may feel busier."
        elif key == "geographic_coverage":
            return "Reasonable spread, but some areas are clustered."
    elif score >= 0.30:
        if key == "category_diversity":
            return "Could use more variety; mixing in different place types would help."
        elif key == "interest_alignment":
            return "Some of your interests are missing from the itinerary."
        elif key == "pacing":
            return "Pacing could be improved; some days feel rushed or empty."
        elif key == "geographic_coverage":
            return "Stops are quite clustered; consider other neighborhoods."
    else:
        if key == "category_diversity":
            return "Most stops are the same type; variety would improve the experience."
        elif key == "interest_alignment":
            return "The itinerary does not strongly reflect your stated interests."
        elif key == "pacing":
            return "Schedule feels unbalanced, consider adjusting daily loads."
        elif key == "geographic_coverage":
            return "Very limited geographic spread."
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# Preference Change Explanation
# ══════════════════════════════════════════════════════════════════════════════


def explain_preference_change(
    old_prefs: Optional[dict],
    new_prefs: Optional[dict],
    adjustments: Optional[dict] = None,
) -> list[str]:
    """
    Explain how user preference changes affected the itinerary.

    Args:
        old_prefs: Previous preference dict (``TripProfile``-like).
        new_prefs: Updated preference dict after adjustments.
        adjustments: Optional dict from
            :func:`~ai_engine.agents.preference_reranker_agent.interpret_preference_adjustment`.

    Returns:
        A list of sentences describing what changed and why.
    """
    lines: list[str] = []

    if not adjustments and (not old_prefs or not new_prefs):
        lines.append("No preference changes were made.")
        return lines

    changes: list[str] = []

    # Detect changes in scalar fields
    for field, label in [
        ("budget_level", "Budget"),
        ("travel_style", "Travel style"),
        ("pace", "Pace"),
    ]:
        old_val = (old_prefs or {}).get(field)
        new_val = (new_prefs or {}).get(field)
        if old_val and new_val and old_val != new_val:
            changes.append(f"**{label}** changed from {old_val} to {new_val}.")

    # Detect changes in list fields
    for field, label in [
        ("interests", "interests"),
        ("food_preferences", "food preferences"),
        ("accommodation_preferences", "accommodation preferences"),
    ]:
        old_list = set((old_prefs or {}).get(field) or [])
        new_list = set((new_prefs or {}).get(field) or [])
        added = new_list - old_list
        removed = old_list - new_list

        if added:
            changes.append(
                f"Added {_pluralize('new interest', len(added))}: "
                f"{_comma_list(sorted(added))}."
            )
        if removed:
            changes.append(
                f"Removed {_pluralize('interest', len(removed))}: "
                f"{_comma_list(sorted(removed))}."
            )

    if not changes:
        changes.append("Minor preference adjustments were applied.")

    lines.append("Preference Changes")
    for c in changes:
        lines.append(f"  - {c}")

    # Include the reranker's reason if available
    if adjustments and adjustments.get("rerank_reason"):
        lines.append(f"  *{adjustments['rerank_reason']}*")

    return lines


# ══════════════════════════════════════════════════════════════════════════════
# Stop Placement Explanation
# ══════════════════════════════════════════════════════════════════════════════


def explain_stop_placement(
    stop: dict,
    day_context: Optional[dict] = None,
    profile: Optional[dict] = None,
) -> list[str]:
    """
    Explain why a specific stop was placed where it is in the itinerary.

    Args:
        stop: A stop dict (from a day's ``stops`` list).
        day_context: The day dict this stop belongs to (for theme/time context).
        profile: Optional user profile for interest-match context.

    Returns:
        A list of explanation sentences.
    """
    lines: list[str] = []
    name = stop.get("name", "Unknown")
    category = stop.get("category", "")
    subcategory = stop.get("sub_category", "")
    time_slot = stop.get("suggested_time_of_day", "")
    duration = stop.get("estimated_duration_minutes", 60)
    why = stop.get("why_recommended", "")
    tags = stop.get("interest_tags", [])
    rating = stop.get("rating")

    # ── Stop header ────────────────────────────────────────────────────
    label = subcategory or category or "place"
    lines.append(f"**{name}** - {label}")

    # ── Time of day reasoning ───────────────────────────────────────────
    time_reason = _explain_time_slot(time_slot, category, subcategory)
    if time_reason:
        lines.append(f"  Scheduled for **{time_slot}** - {time_reason}")

    # ── Duration ────────────────────────────────────────────────────────
    lines.append(f"  Estimated visit: **{duration} min**")

    # ── Why recommended ────────────────────────────────────────────────
    if why:
        lines.append(f"  {why}")
    elif tags:
        lines.append(f"  Matches your interest in {_comma_list(tags)}.")
    if rating:
        lines.append(f"  Rating: **{rating}/5**")

    # ── Interest match ──────────────────────────────────────────────────
    if profile and tags:
        user_interests = set(
            (i or "").lower().strip() for i in (profile.get("interests") or [])
        )
        matching = [
            t for t in tags if t.lower().strip() in user_interests
        ]
        if matching:
            lines.append(
                f"  Matches your interest{'' if len(matching) == 1 else 's'}: "
                f"{_comma_list(matching)}."
            )

    # ── Day context ─────────────────────────────────────────────────────
    if day_context:
        day_theme = day_context.get("theme", "")
        day_num = day_context.get("day_number", "?")
        context = f"Part of Day {day_num}"
        if day_theme:
            context += f' - "{day_theme}"'
        lines.append(f"  {context}")

    lines.append("")
    return lines


def _explain_time_slot(time_slot: str, category: str, subcategory: str) -> str:
    """Generate a reason for placing a stop at a particular time of day."""
    cat_lower = (category + " " + subcategory).lower()

    if time_slot == "morning":
        if any(kw in cat_lower for kw in ("museum", "historic", "temple", "mosque")):
            return "museums and historic sites are best visited early before crowds."
        elif any(kw in cat_lower for kw in ("park", "garden", "nature")):
            return "parks and gardens are most pleasant in the morning cool."
        elif any(kw in cat_lower for kw in ("tour", "walk")):
            return "walking tours are best in the morning when energy is high."
        return "morning is the best time to start the day exploration."

    elif time_slot == "afternoon":
        if any(kw in cat_lower for kw in ("indoor", "museum", "shopping", "market")):
            return "indoor attractions and shopping are ideal for the afternoon."
        elif any(kw in cat_lower for kw in ("restaurant", "cafe", "lunch")):
            return "a natural time for a lunch break."
        return "afternoon is a good time for relaxed exploration."

    elif time_slot == "evening":
        if any(kw in cat_lower for kw in ("restaurant", "dinner", "cuisine")):
            return "evening is the perfect time for dinner."
        elif any(kw in cat_lower for kw in ("nightlife", "bar", "club", "show")):
            return "nightlife and entertainment come alive in the evening."
        elif any(kw in cat_lower for kw in ("viewpoint", "sunset", "rooftop")):
            return "best enjoyed at sunset or after dark for the lights."
        return "evening offers a different atmosphere and cooler temperatures."

    return ""


# ══════════════════════════════════════════════════════════════════════════════
# Profile Summary
# ══════════════════════════════════════════════════════════════════════════════


def explain_profile(profile: Optional[dict]) -> list[str]:
    """
    Generate a human-readable summary of the user travel profile.

    Args:
        profile: A ``TripProfile`` dict.

    Returns:
        A list of sentences describing the profile.
    """
    lines: list[str] = []

    if not profile:
        lines.append("Using default travel preferences.")
        return lines

    style = profile.get("travel_style")
    pace = profile.get("pace")
    budget = profile.get("budget_level")
    interests = profile.get("interests") or []
    food = profile.get("food_preferences") or []
    accommodation = profile.get("accommodation_preferences") or []

    style_text = _STYLE_DESCRIPTIONS.get(style) if style else "a personalized trip"
    pace_text = _PACE_DESCRIPTIONS.get(pace) if pace else "a comfortable pace"

    lines.append(f"Your Travel Profile")
    lines.append(f"  - Planning **{style_text}** at **{pace_text}**.")
    if budget:
        lines.append(f"  - Budget level: **{budget.capitalize()}**")

    if interests:
        lines.append(f"  - Interests: {_comma_list(interests)}")
    if food:
        lines.append(f"  - Food preferences: {_comma_list(food)}")
    if accommodation:
        lines.append(f"  - Accommodation preference: {_comma_list(accommodation)}")

    return lines


# ══════════════════════════════════════════════════════════════════════════════
# Full Itinerary Explanation
# ══════════════════════════════════════════════════════════════════════════════


def format_full_explanation(
    itinerary: Optional[dict] = None,
    validation: Optional[dict] = None,
    metrics: Optional[dict[str, float]] = None,
    profile: Optional[dict] = None,
    feasibility_issues: Optional[list[str]] = None,
    preference_changes: Optional[dict] = None,
    agent_messages: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Generate a complete human-readable explanation for a pipeline run.

    Combines all available data into a structured dict with sections
    ready for display.

    Args:
        itinerary: The final ``optimized_itinerary`` from TripState.
        validation: The ``validation`` dict from TripState.
        metrics: Metrics dict from ``compute_all_metrics()``
            (if not provided, reads from ``validation``).
        profile: User ``TripProfile``.
        feasibility_issues: Issues from ``run_programmatic_checks()``.
        preference_changes: Dict with ``old_prefs``, ``new_prefs``,
            and optional ``adjustments`` keys.
        agent_messages: Raw agent trace messages from TripState.

    Returns:
        A dict with sections:
            {
                "title": "...",
                "profile": [...],
                "verdict": [...],
                "metrics": [...],
                "stop_details": [...],
                "preference_changes": [...],
                "agent_trace": [...],
            }
    """
    if metrics is None and validation is not None:
        metrics = validation.get("metrics")

    result: dict[str, Any] = {}

    # ── Title ───────────────────────────────────────────────────────────
    if itinerary:
        destination = itinerary.get("destination", "your destination")
        days = len(itinerary.get("days", []))
        total_stops = sum(
            len(d.get("stops", [])) for d in itinerary.get("days", [])
        )
        result["title"] = (
            f"Your {days}-day itinerary for {destination} "
            f"with {total_stops} stops"
        )
    else:
        result["title"] = "Itinerary Summary"

    # ── Profile ─────────────────────────────────────────────────────────
    result["profile"] = explain_profile(profile)

    # ── Validation verdict ──────────────────────────────────────────────
    result["verdict"] = explain_validation_decision(
        validation, metrics, feasibility_issues,
    )

    # ── Metrics ─────────────────────────────────────────────────────────
    result["metrics"] = explain_metric_scores(metrics)

    # ── Stop details (top 5) ───────────────────────────────────────────
    stop_lines: list[str] = []
    if itinerary:
        days = itinerary.get("days", [])
        total_stops_display = sum(len(d.get("stops", [])) for d in days)
        shown = 0
        for day in days:
            for stop in day.get("stops", []):
                if shown >= 5:
                    break
                stop_lines.extend(
                    explain_stop_placement(stop, day_context=day, profile=profile)
                )
                shown += 1
            if shown >= 5:
                break

        if total_stops_display > 5:
            stop_lines.append(
                f"... and {total_stops_display - 5} more stops in the full itinerary."
            )

    result["stop_details"] = stop_lines

    # ── Preference changes ──────────────────────────────────────────────
    if preference_changes:
        result["preference_changes"] = explain_preference_change(
            preference_changes.get("old_prefs"),
            preference_changes.get("new_prefs"),
            preference_changes.get("adjustments"),
        )

    # ── Agent trace (trimmed) ───────────────────────────────────────────
    if agent_messages:
        trimmed = []
        for msg in agent_messages:
            clean = msg.strip()
            if clean and not clean.startswith("["):
                continue
            trimmed.append(clean[:200])
        result["agent_trace"] = trimmed[:10]

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Quick Summary (single string)
# ══════════════════════════════════════════════════════════════════════════════


def quick_summary(
    itinerary: Optional[dict] = None,
    validation: Optional[dict] = None,
    metrics: Optional[dict[str, float]] = None,
    profile: Optional[dict] = None,
) -> str:
    """
    Generate a one-paragraph plain-text summary of the itinerary quality.

    Useful for logging, debug output, or short UI previews. No markdown.

    Args:
        itinerary: The final itinerary dict.
        validation: The validation dict from TripState.
        metrics: Metrics dict from ``compute_all_metrics()``.
        profile: User TripProfile.

    Returns:
        A single plain-text paragraph.
    """
    parts: list[str] = []

    if itinerary:
        destination = itinerary.get("destination", "your trip")
        days = len(itinerary.get("days", []))
        total_stops = sum(
            len(d.get("stops", [])) for d in itinerary.get("days", [])
        )
        parts.append(f"Generated {days}-day itinerary for {destination}")
        parts.append(f"with {total_stops} stops")

    if validation:
        status = "passed" if validation.get("is_valid") else "needs review"
        score = validation.get("score", "?")
        parts.append(f"(validation: {status}, score: {score})")

    if metrics and metrics.get("overall", 0) > 0:
        overall = metrics["overall"]
        parts.append(f"[quality: {_rating_label(overall)} at {overall * 100:.0f}%]")

    return " ".join(parts)
