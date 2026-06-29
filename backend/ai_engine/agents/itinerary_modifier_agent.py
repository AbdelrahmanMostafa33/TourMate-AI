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
import re

from langchain_core.messages import HumanMessage, SystemMessage

from ai_engine.services.operations import (
    AdditionalAdd,
    ModifierResponse,
    _detect_category_hints,
    _find_best_day_for_place,
    _find_best_day_and_slot_for_place,
    apply_operation,
    build_compact_context,
    place_matches_semantic_hints,
)
from ai_engine.services.pool_manager import find_place_for_add
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
    "  • ADD — Insert one or more new stops from the pool. "
    "Fields: op=\"ADD\", day_number, suggested_time_of_day (morning/afternoon/evening), "
    "add_place_id, why_recommended. "
    "For multiple additions, also fill `additional_adds` list (see below).\n"
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
    "as null or empty. Always provide the exact ID from the lists.\n"
    "\n"
    "MULTI-ADD (for adding several places of the same type):\n"
    "When the user asks to add multiple places (e.g. \"add churches\", \"add more restaurants\"), "
    "set the primary ADD fields (add_place_id, day_number, etc.) for the first place, "
    "then list additional places in the `additional_adds` array.\n"
    "Each entry in `additional_adds` must have:\n"
    "  - add_place_id (EXACT ID from Available Places list)\n"
    "  - day_number (1-based)\n"
    "  - suggested_time_of_day (morning/afternoon/evening)\n"
    "  - why_recommended (brief reason)\n"
    "Aim for 2-4 additional adds at most — don't overload the itinerary."
)


async def run_itinerary_modifier(
    current_itinerary: dict,
    modification_request: str,
    available_places: list[dict],
    preferences: dict | None = None,
    destination_city: str | None = None,
    destination_country: str | None = None,
) -> dict:
    """
    Run the Itinerary Modifier Agent using delta operations.

    Args:
        current_itinerary: The full itinerary JSON from the last pipeline run.
        modification_request: The user's edit request (e.g. "remove Saladin Citadel").
        available_places: Pool of candidate places from the last retrieval.
        preferences: Optional dict with budget/pace/interests for context.
        destination_city: City name for place search (falls back to itinerary)
        destination_country: Country name for place search (falls back to itinerary)

    Returns:
        Modified itinerary dict.  If modification fails for any reason,
        returns the original itinerary unchanged.
    """
    if not current_itinerary or not modification_request:
        return current_itinerary

    # ── NEW: Try hybrid search for ADD operations before LLM ─────────────
    # This gives us exact matches for specific place names without LLM ambiguity
    pre_selected_places = []
    if "add" in modification_request.lower():
        # Use explicit destination if provided; fall back to itinerary's "destination" key
        city = destination_city or current_itinerary.get("destination")
        country = destination_country
        print(f"[DEBUG] Running hybrid search for: '{modification_request}' (city={city}, country={country})")
        logger.info(
            "[ModifierAgent] Running hybrid search for: '%s' (city=%s, country=%s)",
            modification_request,
            city,
            country,
        )
        pre_selected_places = await find_place_for_add(
            modification_request=modification_request,
            city=city,
            country=country,
            available_places=available_places,
            preferences=preferences,
        )
        print(f"[DEBUG] Hybrid search result: {pre_selected_places}")
        if pre_selected_places:
            logger.info(
                "[ModifierAgent] Hybrid search found %d places: %s",
                len(pre_selected_places),
                [p.get("name") for p in pre_selected_places],
            )
            # ── Merge pre-selected places into available_places pool ─────
            # The hybrid search queries the DB directly and may return places
            # that were filtered out by the Place Retriever (e.g. capped by
            # subcategory sampling, filtered by rating/distance). These places
            # exist in the city's DB but not in the in-memory pool.
            #
            # Without this merge, apply_operation → _exec_add can't find
            # these places in place_pool and fails with "not found in pool".
            existing_ids = {p.get("id") for p in (available_places or []) if p.get("id")}
            pre_selected_new = [
                p for p in pre_selected_places
                if p.get("id") and p["id"] not in existing_ids
            ]
            for p in pre_selected_new:
                available_places.append(p)
                existing_ids.add(p["id"])
            logger.info(
                "[ModifierAgent] Merged %d pre-selected place(s) into pool "
                "(pool now has %d places)",
                len(pre_selected_new),
                len(available_places or []),
            )
        else:
            logger.info(
                "[ModifierAgent] Hybrid search returned empty list — will rely on LLM selection"
            )

    # ── Build a compact textual context ─────────────────────────────────
    context = await build_compact_context(
        itinerary=current_itinerary,
        modification_request=modification_request,
        available_places=available_places,
        preferences=preferences,
        max_places=30,
    )

    # If we found places via hybrid search, add them to the context
    # with the best day recommendation based on free time, balance, and proximity
    if pre_selected_places:
        context += "\n\nPRE-SELECTED PLACES (from hybrid search):\n"
        for i, place in enumerate(pre_selected_places, 1):
            best_day, best_score = _find_best_day_for_place(current_itinerary, place)
            day_hint = (
                f"  Best day to insert: Day {best_day} (score: {best_score})"
                if best_day else ""
            )
            context += (
                f"  {i}. Name: {place.get('name')}\n"
                f"     ID: {place.get('id')}\n"
                f"     Category: {place.get('category')}\n"
                f"     {day_hint}\n"
            )
        context += "  Use these places for ADD operations if appropriate."

    prompt = (
        f"{context}\n\n"
        "Output the operation(s) that best fulfill the user's request.\n"
        "- For single additions: use the primary ADD fields (add_place_id, day_number, etc.).\n"
        "- For multiple additions (e.g. 'add churches', 'add several restaurants'): "
        "fill the primary ADD fields for the first place, "
        "then list the rest in `additional_adds`.\n"
        "- Leave `additional_adds` empty for non-ADD operations or single adds."
    )

    messages = [
        SystemMessage(content=MODIFIER_SYSTEM_INSTRUCTION),
        HumanMessage(content=prompt),
    ]

    # ── Retry loop ───────────────────────────────────────────────────
    # If the LLM returns an invalid operation or validation fails, retry
    # with feedback about what went wrong.
    max_modifier_attempts = 2
    last_error = None
    final_modified = None

    for attempt in range(1, max_modifier_attempts + 1):
        try:
            if attempt > 1 and last_error:
                # Rebuild prompt with error feedback
                # Note: the SystemMessage already contains the full operation
                # instructions, so we only send the error feedback + context.
                retry_prompt = (
                    f"{context}\n\n"
                    f"## Feedback from previous attempt\n"
                    f"Your previous attempt was rejected: {last_error}\n"
                    f"Please try a different approach — pay close attention "
                    f"to the required fields for each operation type."
                )
                attempt_messages = [
                    SystemMessage(content=MODIFIER_SYSTEM_INSTRUCTION),
                    HumanMessage(content=retry_prompt),
                ]
            else:
                attempt_messages = list(messages)

            response: ModifierResponse = await invoke_with_fallback(
                "modifier",
                attempt_messages,
                structured_output=ModifierResponse,
            )

            if response is None:
                last_error = "LLM returned no response"
                logger.warning(
                    "[ModifierAgent] Attempt %d/%d: LLM returned None",
                    attempt, max_modifier_attempts,
                )
                if attempt == max_modifier_attempts:
                    return current_itinerary
                continue

            # ── Use pre-selected places if available and operation is ADD ───
            if pre_selected_places and response.op == "ADD":
                pre_selected_place = pre_selected_places[0]
                response.add_place_id = pre_selected_place.get("id")
                response.why_recommended = (
                    response.why_recommended or 
                    f"Matched your request for '{pre_selected_place.get('name')}'"
                )
                if not response.day_number or response.day_number <= 0:
                    best_day, best_score = _find_best_day_for_place(
                        current_itinerary, pre_selected_place
                    )
                    response.day_number = best_day or 1
                if not response.suggested_time_of_day:
                    response.suggested_time_of_day = "afternoon"

            # ── Validate required fields per operation type ─────────
            validation_error = _get_validation_error(response, available_places, modification_request, current_itinerary)
            if validation_error:
                last_error = validation_error
                logger.warning(
                    "[ModifierAgent] Attempt %d/%d: %s",
                    attempt, max_modifier_attempts, validation_error,
                )
                if attempt == max_modifier_attempts:
                    fallback = copy.deepcopy(current_itinerary)
                    fallback["_modifier_note"] = validation_error
                    return fallback
                continue

            logger.info(
                "[ModifierAgent] Attempt %d/%d: LLM chose op=%s",
                attempt, max_modifier_attempts, response.op,
            )

            modified = apply_operation(
                itinerary=current_itinerary,
                operation=response,
                place_pool=available_places,
            )

            # ── Validate operation result ────────────────────────────
            if not _validate_modifier_result(
                modification_request,
                response,
                current_itinerary,
                modified,
                available_places,
            ):
                validation_error = response.note or "Operation does not match the requested modification category."
                last_error = validation_error
                logger.warning(
                    "[ModifierAgent] Attempt %d/%d: validation failed: %s",
                    attempt, max_modifier_attempts, validation_error,
                )
                if attempt == max_modifier_attempts:
                    fallback = copy.deepcopy(current_itinerary)
                    fallback["_modifier_note"] = validation_error
                    return fallback
                continue

            # ── Success ────────────────────────────────────────────────
            final_modified = modified
            break

        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "[ModifierAgent] Attempt %d/%d failed with exception: %s",
                attempt, max_modifier_attempts, exc,
            )
            if attempt == max_modifier_attempts:
                logger.error(
                    "[ModifierAgent] All %d attempts exhausted: %s",
                    max_modifier_attempts, exc,
                )
                return current_itinerary
            continue

    if final_modified is None:
        logger.warning("[ModifierAgent] No successful modification — returning original itinerary")
        return current_itinerary

    modified = final_modified

    # ── Apply remaining pre-selected places sequentially ──────────────
    # If the user asked to add multiple places (e.g. "add X and Y"),
    # apply each remaining pre-selected place as a separate ADD
    # operation on the accumulating modified itinerary.
    # Uses smart distribution: tracks used slots per day across the batch
    # to avoid clustering same-category places in the same slot.
    added_names = [pre_selected_places[0].get("name", "")] if pre_selected_places and response.op == "ADD" else []
    used_slots_per_day: dict[int, set[str]] = {}
    if response.day_number and response.suggested_time_of_day:
        used_slots_per_day.setdefault(response.day_number, set()).add(response.suggested_time_of_day)

    if pre_selected_places and response.op == "ADD" and len(pre_selected_places) > 1:
        remaining = pre_selected_places[1:]
        logger.info(
            "[ModifierAgent] Applying %d remaining ADD operations: %s",
            len(remaining),
            [p.get("name") for p in remaining],
        )
        for i, place in enumerate(remaining):
            best_day, best_slot = _find_best_day_and_slot_for_place(
                modified, place, used_slots_per_day,
            )
            used_slots_per_day.setdefault(best_day, set()).add(best_slot)
            sub_op = ModifierResponse(
                op="ADD",
                add_place_id=place.get("id"),
                day_number=best_day,
                suggested_time_of_day=best_slot,
                why_recommended=f"Also matched your request for '{place.get('name')}'",
                note="",
            )
            modified = apply_operation(
                itinerary=modified,
                operation=sub_op,
                place_pool=available_places,
            )
            added_names.append(place.get("name", ""))
            logger.info(
                "[ModifierAgent] Applied sequential ADD %d/%d: %s → Day %d (%s)",
                i + 1, len(remaining), place.get("name"), best_day, best_slot,
            )

    # ── Apply additional_adds from LLM response ─────────────────
    # The LLM can specify extra ADD operations in additional_adds
    # (used when the user wants multiple places of the same type).
    extra_names: list[str] = []
    if response.op == "ADD" and response.additional_adds:
        logger.info(
            "[ModifierAgent] Applying %d additional ADD operations from LLM",
            len(response.additional_adds),
        )
        for i, add_op in enumerate(response.additional_adds):
            source_place = next(
                (p for p in (available_places or [])
                 if p.get("id") == add_op.add_place_id),
                None,
            )
            if source_place:
                best_day, best_slot = _find_best_day_and_slot_for_place(
                    modified, source_place, used_slots_per_day,
                )
            else:
                best_day = add_op.day_number
                best_slot = add_op.suggested_time_of_day

            used_slots_per_day.setdefault(best_day, set()).add(best_slot)
            sub_op = ModifierResponse(
                op="ADD",
                add_place_id=add_op.add_place_id,
                day_number=best_day,
                suggested_time_of_day=best_slot,
                why_recommended=add_op.why_recommended or f"Additional place matching your request",
                note="",
            )
            modified = apply_operation(
                itinerary=modified,
                operation=sub_op,
                place_pool=available_places,
            )
            pool_name = next(
                (p.get("name", "") for p in (available_places or [])
                 if p.get("id") == add_op.add_place_id),
                add_op.add_place_id,
            )
            extra_names.append(pool_name)
            logger.info(
                "[ModifierAgent] Applied additional ADD %d/%d: %s → Day %d (%s)",
                i + 1, len(response.additional_adds), pool_name, best_day, best_slot,
            )
        added_names.extend(extra_names)

    # Build a combined note about all added places
    notes = []
    if response.note:
        notes.append(response.note)
    if len(added_names) > 1:
        notes.append(f"Added {len(added_names)} places: {', '.join(added_names)}")
    elif added_names:
        notes.append(f"Added {added_names[0]}")
    if notes:
        existing = modified.get("_modifier_note", "")
        combined = "\n".join(notes)
        modified["_modifier_note"] = (
            f"{existing}\n{combined}".strip()
        )

    return modified


def _get_validation_error(
    operation: ModifierResponse,
    available_places: list[dict],
    modification_request: str,
    current_itinerary: dict,
) -> str | None:
    """Check required fields for the operation and return an error string if invalid.

    Returns None if the operation is valid, or a descriptive error string
    explaining what's wrong (to be fed back to the LLM on retry).
    """
    if operation.op == "ADD" and not operation.add_place_id:
        return (
            "ADD operation is missing the required `add_place_id` field. "
            "You MUST provide the exact ID from the Available Places list."
        )

    if operation.op == "SWAP" and (not operation.remove_place_id or not operation.add_place_id):
        return (
            "SWAP operation is missing required fields. "
            "You MUST provide both `remove_place_id` and `add_place_id`."
        )

    if operation.op == "REMOVE" and not operation.place_id:
        return (
            "REMOVE operation is missing the required `place_id` field. "
            "You MUST provide the exact ID of the place to remove."
        )

    if operation.op == "REORDER" and (not operation.day_number or not operation.new_order):
        return (
            "REORDER operation is missing required fields. "
            "You MUST provide both `day_number` and `new_order` (list of place IDs)."
        )

    if operation.op == "CHANGE_HOTEL" and not operation.new_hotel_id:
        return (
            "CHANGE_HOTEL operation is missing the required `new_hotel_id` field. "
            "You MUST provide the exact hotel ID."
        )

    if operation.op == "RE_THEME" and (not operation.day_number or not operation.new_theme):
        return (
            "RE_THEME operation is missing required fields. "
            "You MUST provide both `day_number` and `new_theme`."
        )

    return None


def _validate_modifier_result(
    modification_request: str,
    operation: ModifierResponse,
    original: dict,
    modified: dict,
    place_pool: list[dict],
) -> bool:
    """Reject ADD/SWAP when the chosen place violates semantic category constraints."""
    hints = _detect_category_hints(modification_request, pool=place_pool)
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


