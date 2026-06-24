"""
Itinerary Modifier Agent — delta-based itinerary editing.

Fully rewritten to use **delta operations** instead of full itinerary
regeneration.  The LLM receives a compact textual summary and outputs
a tiny operation (REMOVE, SWAP, ADD, CHANGE_HOTEL, REORDER, RE_THEME)
via structured output.  Deterministic Python code in ``operations.py``
applies the operation to the in-memory itinerary.

Benefits:
  - No JSON formatting errors (structured output)
  - ~90% fewer tokens sent to the LLM
  - Faster, cheaper, more reliable
"""

import logging

from langchain_core.messages import HumanMessage

from ai_engine.services.operations import (
    ModifierResponse,
    apply_operation,
    build_compact_context,
)
from ai_engine.llm_config import invoke_with_fallback

logger = logging.getLogger(__name__)


# ── System-level instruction (sent alongside the prompt) ───────────────────

MODIFIER_SYSTEM_INSTRUCTION = (
    "You are the TourMate Itinerary Modifier. "
    "Based on the itinerary summary and available places below, decide "
    "what single operation best fulfills the user's modification request.\n\n"
    "Available operations (choose EXACTLY one — the `op` value must be exactly as shown):\n"
    "  • REMOVE — Delete a stop. Fields: op=\"REMOVE\", place_id\n"
    "  • SWAP — Replace one stop with another. Fields: op=\"SWAP\", remove_place_id, add_place_id, day_number, new_why_recommended\n"
    "  • ADD — Insert a new stop. Fields: op=\"ADD\", day_number, suggested_time_of_day (morning/afternoon/evening), add_place_id, why_recommended\n"
    "  • CHANGE_HOTEL — Replace/add a hotel. Fields: op=\"CHANGE_HOTEL\", old_hotel_id (optional), new_hotel_id, why_recommended\n"
    "  • REORDER — Reorder stops within a day. Fields: op=\"REORDER\", day_number, new_order (list of place IDs)\n"
    "  • RE_THEME — Update a day's theme. Fields: op=\"RE_THEME\", day_number, new_theme\n"
    "\n"
    "Rules:\n"
    "1. The `op` value MUST be exactly one of: REMOVE, SWAP, ADD, CHANGE_HOTEL, REORDER, RE_THEME. "
    "Do NOT use any other value.\n"
    "2. Pick places ONLY from the Available Places list.\n"
    "3. If a place the user wants to swap IN is already a stop elsewhere "
    "in the itinerary, use REORDER instead of SWAP.\n"
    "4. For ADD, pick a place that matches the user's request and fits "
    "the requested time slot (morning/afternoon/evening).\n"
    "5. If the modification cannot be done (e.g. no suitable place in the "
    "pool), use a REMOVE operation with the nearest matching place_id, "
    "or omit the operation and explain why in the `note`.\n"
    "6. Explain your reasoning briefly in the `note` field."
)


async def run_itinerary_modifier(
    current_itinerary: dict,
    modification_request: str,
    available_places: list[dict],
    preferences: dict | None = None,
) -> dict:
    """
    Run the Itinerary Modifier Agent using delta operations.

    Args:
        current_itinerary: The full itinerary JSON from the last pipeline run.
        modification_request: The user's edit request (e.g. "remove Saladin Citadel").
        available_places: Pool of candidate places from the last retrieval.
        preferences: Optional dict with budget/pace/interests for context.

    Returns:
        Modified itinerary dict.  If modification fails for any reason,
        returns the original itinerary unchanged.
    """
    if not current_itinerary or not modification_request:
        return current_itinerary

    # ── Build a compact textual context ─────────────────────────────────
    context = build_compact_context(
        itinerary=current_itinerary,
        modification_request=modification_request,
        available_places=available_places,
        preferences=preferences,
        max_places=30,
    )

    prompt = (
        f"{MODIFIER_SYSTEM_INSTRUCTION}\n\n"
        f"{context}\n\n"
        "Output the single operation that best fulfills the user's request."
    )

    messages = [HumanMessage(content=prompt)]

    try:
        response: ModifierResponse = await invoke_with_fallback(
            "modifier",
            messages,
            structured_output=ModifierResponse,
        )

        if response is None:
            logger.warning(
                "[ModifierAgent] LLM returned None — returning original itinerary"
            )
            return current_itinerary

        logger.info(
            "[ModifierAgent] LLM chose op=%s (note=%s)",
            response.op,
            (response.note[:120] + "...") if len(response.note) > 120 else response.note,
        )

        # ── Apply the operation ─────────────────────────────────────────
        # The flat ModifierResponse schema accepts ANY op name, so this
        # never crashes on validation.  Unknown ops are logged by
        # apply_operation's else branch and the original is returned.
        modified = apply_operation(
            itinerary=current_itinerary,
            operation=response,
            place_pool=available_places,
        )

        # Preserve the modifier note (raw, no prefix — the caller
        # wraps it as [ModifierAgent] {note} so we keep it clean)
        if response.note:
            existing = modified.get("_modifier_note", "")
            modified["_modifier_note"] = (
                f"{existing}\n{response.note}".strip()
            )

        return modified

    except Exception as exc:
        logger.error("[ModifierAgent] Modification failed: %s", exc)
        return current_itinerary
