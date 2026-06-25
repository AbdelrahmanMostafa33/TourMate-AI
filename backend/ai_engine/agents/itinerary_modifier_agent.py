"""
Itinerary Modifier Agent — delta-based itinerary editing.

Fully rewritten to use **delta operations** instead of full itinerary
regeneration.  The LLM receives a compact textual summary and outputs
a tiny operation (REMOVE, SWAP, EXCHANGE, ADD, CHANGE_HOTEL, REORDER, RE_THEME)
via structured output.  Deterministic Python code in ``operations.py``
applies the operation to the in-memory itinerary.

Benefits:
  - No JSON formatting errors (structured output)
  - ~90% fewer tokens sent to the LLM
  - Faster, cheaper, more reliable
"""

import copy
import logging

from langchain_core.messages import HumanMessage

from ai_engine.services.operations import (
    ModifierResponse,
    _detect_category_hints,
    apply_operation,
    build_compact_context,
    place_matches_semantic_hints,
)
from ai_engine.llm import invoke_with_fallback

logger = logging.getLogger(__name__)


# ── System-level instruction (sent alongside the prompt) ───────────────────

MODIFIER_SYSTEM_INSTRUCTION = (
    "You are the TourMate Itinerary Modifier. "
    "Based on the itinerary summary and available places below, decide "
    "what single operation best fulfills the user's modification request.\n\n"
    "Available operations (choose EXACTLY one — the `op` value must be exactly as shown):\n"
    "  • REMOVE — Delete a stop. Fields: op=\"REMOVE\", place_id\n"
    "  • SWAP — Replace one stop with a NEW place from the pool. "
    "Fields: op=\"SWAP\", remove_place_id, add_place_id, day_number, new_why_recommended\n"
    "  • EXCHANGE — Swap time slots between two stops ALREADY in the itinerary "
    "(e.g. swap lunch and dinner restaurants). "
    "Fields: op=\"EXCHANGE\", place_id_a, place_id_b\n"
    "  • ADD — Insert a new stop from the pool. "
    "Fields: op=\"ADD\", day_number, suggested_time_of_day (morning/afternoon/evening), "
    "add_place_id, why_recommended\n"
    "  • CHANGE_HOTEL — Replace/add a hotel. "
    "Fields: op=\"CHANGE_HOTEL\", old_hotel_id (optional), new_hotel_id, why_recommended\n"
    "  • REORDER — Change visit sequence within a day WITHOUT changing time slots. "
    "Fields: op=\"REORDER\", day_number, new_order (list of place IDs)\n"
    "  • RE_THEME — Update a day's theme. Fields: op=\"RE_THEME\", day_number, new_theme\n"
    "\n"
    "CRITICAL RULES:\n"
    "1. The `op` value MUST be exactly one of: REMOVE, SWAP, EXCHANGE, ADD, CHANGE_HOTEL, "
    "REORDER, RE_THEME. Do NOT use any other value.\n"
    "2. For ADD and SWAP operations, you MUST provide the `add_place_id` field with the EXACT "
    "ID from the Available Places list (shown in parentheses after each place name). "
    "Copy the ID exactly as shown — do NOT invent IDs or use the place name.\n"
    "3. For REMOVE, you MUST provide the `place_id` field with the EXACT ID from the itinerary.\n"
    "4. For SWAP and ADD, pick places ONLY from the Available Places list.\n"
    "5. When the user wants to swap/replace one itinerary stop with ANOTHER stop already "
    "in the itinerary (same trip), use EXCHANGE — never SWAP or REORDER for that case.\n"
    "6. Use REORDER only when the user asks to change visit order or reverse a day, "
    "not when swapping two named stops.\n"
    "7. For ADD, pick a place that exactly matches the user's request "
    "(e.g. church ≠ mosque). Respect any 'Required place type' line in the context.\n"
    "8. If the modification cannot be done (no matching place, wrong category), "
    "explain clearly in `note`. Do NOT substitute a different type of place.\n"
    "9. Explain your reasoning briefly in the `note` field.\n"
    "10. NEVER leave required fields (place_id, add_place_id, remove_place_id, new_hotel_id) "
    "as null or empty. Always provide the exact ID from the lists."
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

        # Validate required fields based on operation type
        if response.op == "ADD" and not response.add_place_id:
            logger.warning(
                "[ModifierAgent] ADD operation missing required add_place_id — attempting auto-selection"
            )
            # Auto-select the best matching place from the pool
            hints = _detect_category_hints(modification_request)
            semantics = hints.get("semantic", [])
            
            # Filter places by semantic hints if available
            if semantics:
                matching_places = [
                    p for p in available_places 
                    if place_matches_semantic_hints(p, semantics) and p.get("id")
                ]
            else:
                matching_places = [p for p in available_places if p.get("id")]
            
            # Remove places already in itinerary
            used_ids = set()
            for day in current_itinerary.get("days", []):
                for s in day.get("stops", []):
                    used_ids.add(s.get("id", ""))
            matching_places = [p for p in matching_places if p.get("id") not in used_ids]
            
            if matching_places:
                # Select the highest-scored place
                selected = max(
                    matching_places,
                    key=lambda p: p.get("composite_score", p.get("popularity_score", 0))
                )
                response.add_place_id = selected.get("id")
                response.day_number = response.day_number or 1
                response.suggested_time_of_day = response.suggested_time_of_day or "afternoon"
                logger.info(
                    "[ModifierAgent] Auto-selected place %s for ADD operation",
                    response.add_place_id
                )
            else:
                fallback = copy.deepcopy(current_itinerary)
                fallback["_modifier_note"] = "Cannot add place: No matching places available in the pool."
                return fallback

        if response.op == "SWAP" and (not response.remove_place_id or not response.add_place_id):
            logger.warning(
                "[ModifierAgent] SWAP operation missing required place IDs — returning original itinerary"
            )
            fallback = copy.deepcopy(current_itinerary)
            fallback["_modifier_note"] = "Cannot swap: LLM did not specify which places to swap."
            return fallback

        if response.op == "REMOVE" and not response.place_id:
            logger.warning(
                "[ModifierAgent] REMOVE operation missing required place_id — returning original itinerary"
            )
            fallback = copy.deepcopy(current_itinerary)
            fallback["_modifier_note"] = "Cannot remove: LLM did not specify which place to remove."
            return fallback

        logger.info(
            "[ModifierAgent] LLM chose op=%s (note=%s)",
            response.op,
            (response.note[:120] + "...") if len(response.note) > 120 else response.note,
        )

        modified = apply_operation(
            itinerary=current_itinerary,
            operation=response,
            place_pool=available_places,
        )

        if not _validate_modifier_result(
            modification_request,
            response,
            current_itinerary,
            modified,
            available_places,
        ):
            logger.warning(
                "[ModifierAgent] Operation %s failed validation for request: %s",
                response.op,
                modification_request[:80],
            )
            fallback = copy.deepcopy(current_itinerary)
            note = response.note or "Could not apply modification — no suitable match in the pool."
            fallback["_modifier_note"] = note
            return fallback

        if response.note:
            existing = modified.get("_modifier_note", "")
            modified["_modifier_note"] = (
                f"{existing}\n{response.note}".strip()
            )

        return modified

    except Exception as exc:
        logger.error("[ModifierAgent] Modification failed: %s", exc)
        return current_itinerary


def _validate_modifier_result(
    modification_request: str,
    operation: ModifierResponse,
    original: dict,
    modified: dict,
    place_pool: list[dict],
) -> bool:
    """Reject ADD/SWAP when the chosen place violates semantic category constraints."""
    hints = _detect_category_hints(modification_request)
    semantics = hints.get("semantic", [])
    if not semantics or operation.op not in ("ADD", "SWAP"):
        return True

    pool_index = {p.get("id"): p for p in (place_pool or []) if p.get("id")}
    place_id = operation.add_place_id
    if not place_id:
        return True

    place = pool_index.get(place_id)
    if place is None:
        return True

    return place_matches_semantic_hints(place, semantics)
