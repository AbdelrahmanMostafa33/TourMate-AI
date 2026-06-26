"""
Persona Updater — Evolve the user's traveler_persona after each approved trip.

On each itinerary approval, this module feeds:
  - the user's *old* traveler_persona (free-text, from ``users`` table)
  - the *newly-approved TripProfile* data (as a plain dict)
  - the user's *preference confidence counts* (evidence across all trips)

…to an LLM and asks it to produce an **updated traveler_persona** that gently
absorbs signals from the latest trip without resetting the accumulated identity.

The prompt uses behavioral instructions rather than numeric weights, and the
confidence counts give the LLM concrete evidence to distinguish one-off choices
from enduring preferences.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from ai_engine.llm import get_llm_for_agent

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Prompt
# ══════════════════════════════════════════════════════════════════════════════

PERSONA_UPDATE_SYSTEM_PROMPT = """\
You are a travel-persona curator.

Your job is to maintain a user's **traveler persona** — a natural-language
summary (2-4 sentences) that captures the user's overall travel identity
across *all* their trips, not just the most recent one.

You will receive:
1. The **existing persona** (current understanding of the user).
2. The **new approved trip profile** (just-completed trip's preferences).
3. A **preference history** — how many times each value has appeared across
   all of the user's approved trips.

Guidelines:
- Write in **2nd person** ("You tend to prefer...", "You usually travel...").
- Keep the tone warm, insightful, and concise.

- **Use the preference history as your primary evidence.** If a value
  (e.g., "luxury") appears 3 times while "budget" appears only once, the
  user's enduring preference is luxury. Do not flip the persona based on
  a single outlier.

- **Only change an existing preference if**:
  (a) The new trip *strongly contradicts* it (e.g., 3 luxury trips → 1 budget
      trip is NOT a contradiction worth flipping for), OR
  (b) The same value has appeared across *multiple* trips, reinforcing a new
      pattern (e.g., the user chose "adventure" on trip 1, then again on trip 2).

- **Do not infer new personality traits** that are not supported by either
  the existing persona or the preference history.

- **Highlight patterns** that are reinforced across trips (e.g. "You have
  consistently chosen boutique hotels across your last 3 trips").

- If the existing persona is empty or None, build the persona exclusively
  from the preference history and the new trip data.

- **If the persona conflicts with the preference history, treat the
  preference history as the source of truth.**

- Do NOT include any meta-commentary about decision rules.
- Output ONLY the updated persona text — no introductory phrases, no
  labels, no formatting."""


def _extract_content(response) -> str:
    """Safely extract text content from an LLM response.

    Some providers return ``response.content`` as a string, others as a list
    of message parts (dicts with "text" keys, or other types).  This helper
    normalises to a single string regardless of provider.
    """
    content = response.content

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", ""))
            elif isinstance(part, str):
                parts.append(part)
            else:
                logger.debug("[PersonaUpdater] Unknown content part type in LLM response: %r", part)
        return "".join(parts).strip()

    # Fallback — unlikely but still handle gracefully
    logger.debug("[PersonaUpdater] Unexpected response.content type: %s", type(content).__name__)
    return str(content).strip()


def _profile_dict_to_text(profile_data: dict) -> str | None:
    """Convert a TripProfile dict to a structured text description.

    Returns ``None`` if there is no meaningful data to describe.
    """
    parts = []

    if profile_data.get("budget_level"):
        parts.append(f"Budget level: {profile_data['budget_level']}")
    if profile_data.get("travel_style"):
        parts.append(f"Travel style: {profile_data['travel_style']}")
    if profile_data.get("pace"):
        parts.append(f"Pace: {profile_data['pace']}")
    interests = profile_data.get("interests") or []
    if interests:
        parts.append(f"Interests: {', '.join(interests)}")
    food = profile_data.get("food_preferences") or []
    if food:
        parts.append(f"Food preferences: {', '.join(food)}")
    accommodation = profile_data.get("accommodation_preferences") or []
    if accommodation:
        parts.append(f"Accommodation preferences: {', '.join(accommodation)}")

    if not parts:
        return None

    return "\n".join(parts)


def _counts_to_text(preference_counts: Optional[dict]) -> str:
    """Convert the preference confidence counts dict to a readable summary."""
    if not preference_counts:
        return "(no preference history yet — this is the first trip)"

    lines: list[str] = []
    for category, values in preference_counts.items():
        if not values or not isinstance(values, dict):
            continue
        # Sort by count descending so the most frequent values appear first
        sorted_vals = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
        non_zero = [(v, c) for v, c in sorted_vals if c > 0]
        if non_zero:
            counts_str = ", ".join(f"{v}: {c}" for v, c in non_zero)
            lines.append(f"  {category}: {counts_str}")

    if not lines:
        return "(no preference history yet — this is the first trip)"

    return "\n".join(lines)


async def update_persona(
    old_persona: Optional[str],
    trip_profile_data: dict,
    preference_counts: Optional[dict] = None,
) -> Optional[str]:
    """Generate an updated traveler_persona by blending the old persona with
    newly-approved trip profile data, informed by preference confidence counts.

    Args:
        old_persona:        The user's current ``traveler_persona`` from the
                            ``users`` table (may be None or empty).
        trip_profile_data:  A dict of the approved trip's profile fields
                            (budget_level, travel_style, pace, interests,
                            food_preferences, accommodation_preferences).
        preference_counts:  Optional dict mapping preference categories to
                            value→count mappings (e.g. ``{"budget_level":
                            {"luxury": 3, "budget": 1}}``).  Pass ``None``
                            for the first trip.

    Returns:
        The updated persona text, or the original persona if the LLM call fails
        or there is no new data to learn from.
    """
    # ── Quick exit: no new data → no update needed ────────────────────
    new_trip_text = _profile_dict_to_text(trip_profile_data)
    if new_trip_text is None:
        logger.info(
            "[PersonaUpdater] Trip profile data is empty — keeping existing persona"
        )
        return old_persona

    # ── Build the user message ──────────────────────────────────────────
    old_persona_text = old_persona.strip() if old_persona else "(no previous persona)"
    counts_text = _counts_to_text(preference_counts)

    user_message = (
        "=== Existing Traveler Persona ===\n"
        f"{old_persona_text}\n\n"
        "=== Preference History (across all trips) ===\n"
        f"{counts_text}\n\n"
        "=== New Approved Trip Profile ===\n"
        f"{new_trip_text}\n\n"
        "Please produce an updated traveler persona. Use the preference "
        "history as evidence to decide what has truly changed."
    )

    # ── Call the LLM ────────────────────────────────────────────────────
    try:
        llm: BaseChatModel = get_llm_for_agent("persona_updater")
        messages = [
            SystemMessage(content=PERSONA_UPDATE_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
        response = await llm.ainvoke(messages)
        updated = _extract_content(response)

        if not updated:
            logger.warning(
                "[PersonaUpdater] LLM returned empty response; keeping old persona"
            )
            return old_persona

        logger.info(
            "[PersonaUpdater] Persona updated: %.120s…",
            updated,
        )
        return updated

    except Exception as exc:
        logger.exception(
            "[PersonaUpdater] Failed to update persona: %s", exc,
        )
        return old_persona  # graceful fallback — keep existing persona
