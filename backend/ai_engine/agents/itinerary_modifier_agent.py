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

from ai_engine.agents.operations import (
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
    "Rules:\n"
    "1. Pick places ONLY from the Available Places list.\n"
    "2. If a place the user wants to swap IN is already a stop elsewhere "
    "in the itinerary, use REORDER instead of SWAP.\n"
    "3. For ADD, pick a place that matches the user's request and fits "
    "the requested time slot (morning/afternoon/evening).\n"
    "4. If the modification cannot be done (e.g. no suitable place in the "
    "pool), use a REMOVE operation with the nearest matching place_id, "
    "or omit the operation and explain why in the `note`.\n"
    "5. Explain your reasoning briefly in the `note` field."
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

        operation = response.operation
        note = response.note

        logger.info(
            "[ModifierAgent] LLM chose op=%s (note=%s)",
            operation.op,
            (note[:120] + "...") if len(note) > 120 else note,
        )

        # ── Apply the operation ─────────────────────────────────────────
        modified = apply_operation(
            itinerary=current_itinerary,
            operation=operation,
            place_pool=available_places,
        )

        # Preserve the modifier note (raw, no prefix — the caller
        # wraps it as [ModifierAgent] {note} so we keep it clean)
        if note:
            existing = modified.get("_modifier_note", "")
            modified["_modifier_note"] = (
                f"{existing}\n{note}".strip()
            )

        return modified

    except Exception as exc:
        logger.error("[ModifierAgent] Modification failed: %s", exc)
        return current_itinerary
