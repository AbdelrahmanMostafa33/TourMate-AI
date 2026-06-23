"""
Itinerary Modifier Agent — surgically edits an existing itinerary.

Instead of re-running the full pipeline (retrieval → ranking → planning →
optimizer → validator), this agent makes targeted changes to the current
itinerary based on the user's modification request.

Capabilities:
  - SWAP: Replace one stop with another from the available places pool
  - REMOVE: Delete a specific stop and re-balance the day
  - ADD: Insert a new stop from the available pool into a specific day/time
  - CHANGE_HOTEL: Replace a hotel suggestion with another from the pool
  - RE_THEME: Update a day's theme or description
  - REORDER: Change the order of stops within a day

If the modification request is too complex or the LLM output is invalid,
the caller (conversation_agent.py) falls back to the full pipeline.
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from ai_engine.llm_config import invoke_with_fallback
from ai_engine.utils.json_utils import (
    extract_json_from_llm_output,
    repair_missing_commas,
    repair_truncated_json,
)

logger = logging.getLogger(__name__)


# ── Modifier Prompt ──────────────────────────────────────────────────────────

MODIFIER_SYSTEM_PROMPT = """\
You are the Itinerary Modifier Agent for TourMate AI. You receive:

1. **Current Itinerary**: Full JSON itinerary (days, stops, accommodation)
2. **Available Places Pool**: Places in the destination city you can choose from
3. **Modification Request**: What the user wants to change

**Your job**: Make ONLY the requested changes to the itinerary. Return the
**entire modified itinerary JSON** preserving everything the user didn't ask
to change.

**Available operations** — pick one or more:
- **SWAP**: Replace an existing stop with a DIFFERENT place from the available
  pool. Keep the same time slot and day position. Copy the new place's `id`,
  `name`, `category`, `sub_category`, `lat`, `lon`, and
  **`estimated_duration_minutes`** from the available pool entry. Do NOT reuse
  the old stop's duration — each place has its own intrinsic duration. Add a
  new `why_recommended` explaining why this new place fits the user's request.
  **IMPORTANT — deduplication check**: If the place the user wants to swap IN
  is already a stop elsewhere in the itinerary, do NOT SWAP. Instead, treat
  this as a **REORDER** (see below): move the existing stop to the target
  position and remove the one it's replacing.
- **REMOVE**: Delete a specific stop. If the removed stop was between other
  stops, reconnect the remaining stops by updating their
  `travel_time_to_next_minutes` and `transport_mode`.
- **ADD**: Insert a new stop from the available pool into a specific day/time.
  Pick a place that matches the user's modification request. If adding a
  restaurant, pick a cuisine type different from other restaurant stops
  nearby. Recompute travel times for affected stops.
- **CHANGE_HOTEL**: Replace or add a hotel in `accommodation_suggestions`.
  Pick from the available pool.
- **RE_THEME**: Update a day's `theme` string.
- **REORDER**: Swap the order of stops within a day. When reordering:
  **a)** Preserve each stop's own `estimated_duration_minutes` — do NOT swap
  durations between stops; each duration belongs to its place.
  **b)** Recalculate `travel_time_to_next_minutes` and `transport_mode` for
  the newly adjacent stops based on their actual lat/lon positions.
  **c)** Remove `travel_time_to_next_minutes` from the new last stop.
  **d)** Update each stop's `suggested_time_of_day` to match its new
  position in the day (morning → first, afternoon → middle, evening → last).
  **e)** Refresh each reordered stop's `why_recommended` so it reflects
  the new context rather than historical pipeline artifacts.

**Rules**:
1. Do NOT change stops the user didn't ask about — preserve them exactly.
2. Do NOT invent places — only use places from the Available Places Pool.
3. Every stop must have a `why_recommended` explaining why it fits.
4. Return ONLY valid JSON — no preamble, no markdown fences.
5. If the modification cannot be done (e.g. no suitable place in the pool),
   return the original itinerary unchanged with a note in `_modifier_note`.
6. **Acknowledge ALL sub-requests in `_modifier_note`**: List every change
   you made AND mention any requests you couldn't fulfill (e.g. "Removed X:
   X was not in the itinerary" or "Added Y: no suitable place available").
   This prevents silent omission of user requests.

**Output schema** — the SAME schema as the input itinerary, optionally with a
`_modifier_note` field at the top level explaining what changed:
{
  "destination": string,
  "duration_days": integer,
  "_modifier_note": string (optional — explain what you changed),
  "accommodation_suggestions": [...],
  "days": [
    {
      "day_number": integer,
      "theme": string,
      "stops": [
        {
          "id": string,
          "name": string,
          "category": string,
          "sub_category": string,
          "lat": float,
          "lon": float,
          "why_recommended": string,
          "estimated_duration_minutes": integer,
          "suggested_time_of_day": "morning" | "afternoon" | "evening",
          "travel_time_to_next_minutes": float (omit for last stop),
          "transport_mode": string (omit for last stop)
        }
      ]
    }
  ]
}
"""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _trim_for_modifier(place: dict) -> dict:
    """Reduce a place record to the information needed by the modifier."""
    trimmed = {
        "id": place.get("id", ""),
        "name": place.get("name", ""),
        "category": place.get("category", ""),
        "sub_category": place.get("sub_category", place.get("subcategory", "")),
        "lat": place.get("lat", 0),
        "lon": place.get("lon", 0),
        "rating": place.get("rating", 0),
        "popularity_score": place.get("popularity_score", 0),
    }
    # Include estimated_duration_minutes so the LLM has a source of truth for swaps
    dur = place.get("estimated_duration_minutes") or place.get("duration_minutes")
    if dur is not None:
        trimmed["estimated_duration_minutes"] = int(dur)

    # Include cuisine_type for restaurants
    if place.get("category") == "restaurant" and place.get("cuisine_type"):
        trimmed["cuisine_type"] = place["cuisine_type"]
    # Include accommodation_type and amenities for hotels
    if place.get("category") == "hotel":
        trimmed["accommodation_type"] = place.get("accommodation_type", "")
        amenities = place.get("amenities", [])
        trimmed["amenities"] = amenities[:3] if len(amenities) > 3 else amenities
    return trimmed


def _trim_itinerary(itinerary: dict) -> dict:
    """Strip bloat from the itinerary before sending it to the LLM.

    Removes large fields (photos, maps_link, address, phone, website,
    opening_hours, review_count, price_level) that the modifier doesn't
    need for decision-making.  Keeps structural fields (lat/lon, duration,
    transport, why_recommended) so the LLM can still make good edits.
    """
    trimmed = {
        "destination": itinerary.get("destination", ""),
        "duration_days": itinerary.get("duration_days", 0),
    }

    # Trim accommodation suggestions
    hotels = []
    for hotel in itinerary.get("accommodation_suggestions", []):
        h = {
            "id": hotel.get("id", ""),
            "name": hotel.get("name", ""),
            "sub_category": hotel.get("sub_category", ""),
            "accommodation_type": hotel.get("accommodation_type", ""),
            "lat": hotel.get("lat", 0),
            "lon": hotel.get("lon", 0),
            "rating": hotel.get("rating", 0),
            "category": hotel.get("category", ""),
            "why_recommended": hotel.get("why_recommended", ""),
        }
        amenities = hotel.get("amenities", [])
        if amenities:
            h["amenities"] = amenities[:3] if len(amenities) > 3 else amenities
        hotels.append(h)
    if hotels:
        trimmed["accommodation_suggestions"] = hotels

    # Trim days and stops
    trimmed_days = []
    for day in itinerary.get("days", []):
        trimmed_stops = []
        for stop in day.get("stops", []):
            s = {
                "id": stop.get("id", ""),
                "name": stop.get("name", ""),
                "category": stop.get("category", ""),
                "sub_category": stop.get("sub_category", ""),
                "lat": stop.get("lat", 0),
                "lon": stop.get("lon", 0),
                "why_recommended": stop.get("why_recommended", ""),
                "estimated_duration_minutes": stop.get("estimated_duration_minutes", 0),
                "suggested_time_of_day": stop.get("suggested_time_of_day", ""),
            }
            # Keep cuisine_type for restaurants
            if stop.get("cuisine_type"):
                s["cuisine_type"] = stop["cuisine_type"]
            # Keep transport fields
            travel_time = stop.get("travel_time_to_next_minutes")
            if travel_time is not None:
                s["travel_time_to_next_minutes"] = travel_time
                s["transport_mode"] = stop.get("transport_mode", "")
            trimmed_stops.append(s)

        trimmed_day = {
            "day_number": day.get("day_number", 0),
            "theme": day.get("theme", ""),
            "stops": trimmed_stops,
        }
        # Include total_travel_time_minutes if present (useful context for the LLM)
        total_travel = day.get("total_travel_time_minutes")
        if total_travel is not None:
            trimmed_day["total_travel_time_minutes"] = total_travel
        trimmed_days.append(trimmed_day)

    if trimmed_days:
        trimmed["days"] = trimmed_days

    return trimmed


# ── Category Detection ────────────────────────────────────────────────────


_CATEGORY_KEYWORDS: dict[str, tuple[str | None, str | None]] = {
    # Attractions by sub_category
    "museum": ("attraction", "museums"),
    "park": ("attraction", "parks"),
    "shopping": ("attraction", "shopping"),
    "nightlife": ("attraction", "nightlife"),
    "history": ("attraction", "history"),
    "nature": ("attraction", "nature"),
    "religious": ("attraction", "religious"),
    "sightseeing": ("attraction", "sightseeing"),
    "sports": ("attraction", "sports"),
    "wellness": ("attraction", "wellness"),
    "entertainment": ("attraction", "entertainment"),
    "family": ("attraction", "family"),
    "beach": ("attraction", "nature"),
    "garden": ("attraction", "parks"),
    # Restaurants
    "restaurant": ("restaurant", None),
    "food": ("restaurant", None),
    "eat": ("restaurant", None),
    "breakfast": ("restaurant", None),
    "lunch": ("restaurant", None),
    "dinner": ("restaurant", None),
    "cafe": ("restaurant", None),
    "coffee": ("restaurant", None),
    "bakery": ("restaurant", None),
    "street food": ("restaurant", None),
    # Hotels
    "hotel": ("hotel", None),
    "accommodation": ("hotel", None),
    "stay": ("hotel", None),
    "lodge": ("hotel", None),
    "hostel": ("hotel", None),
    "resort": ("hotel", None),
}


def _detect_category_from_request(modification_request: str) -> dict:
    """
    Detect what category/subcategory the user wants from the modification request
    using simple keyword matching.

    Returns a dict with zero or more of: ``category``, ``sub_category``.
    Used to ensure relevant places survive pool trimming.

    Example::
        >>> _detect_category_from_request("add a museum to day 2")
        {'category': 'attraction', 'sub_category': 'museums'}

        >>> _detect_category_from_request("change the hotel")
        {'category': 'hotel'}
    """
    request_lower = modification_request.lower()

    for keyword, (cat, subcat) in _CATEGORY_KEYWORDS.items():
        if keyword in request_lower:
            result: dict[str, str] = {}
            if cat:
                result["category"] = cat
            if subcat:
                result["sub_category"] = subcat
            return result

    return {}


def _reorder_pool_by_category(fresh_pool: list[dict], category_hints: dict) -> list[dict]:
    """
    Reorder *fresh_pool* so places matching *category_hints* come first.

    This ensures that when the pool is capped or halved for token budget,
    the places most relevant to the user's modification request survive.
    """
    if not category_hints:
        return fresh_pool

    cat = category_hints.get("category")
    subcat = category_hints.get("sub_category")

    matching: list[dict] = []
    non_matching: list[dict] = []

    for p in fresh_pool:
        match = True
        if cat and p.get("category") != cat:
            match = False
        if subcat and p.get("sub_category") != subcat:
            match = False
        if match:
            matching.append(p)
        else:
            non_matching.append(p)

    # Log how many matching places were found
    if matching:
        if subcat and cat:
            label = f"{subcat} ({cat})"
        elif cat:
            label = cat
        elif subcat:
            label = subcat
        else:
            label = "unknown"
        logger.info(
            "[ModifierAgent] Category '%s' — %d matching place(s) in pool "
            "(total pool: %d)",
            label, len(matching), len(fresh_pool),
        )

    return matching + non_matching


# ── Post-processing safeguard ───────────────────────────────────────────────


def _fix_durations_on_reorder(
    modified: dict,
    original: dict,
) -> None:
    """
    Fix `estimated_duration_minutes` for stops that were reordered (not swapped).

    The LLM sometimes swaps durations between stops during a REORDER. This
    function detects pre-existing stops by ID and restores their original
    duration, preventing duration drift.

    Only overrides durations for stops whose ID exists in the original
    itinerary (i.e. not newly SWAPPED or ADDED stops).
    """
    # Build index of original stop durations: {stop_id: duration}
    orig_durations: dict[str, int] = {}
    for day in original.get("days", []):
        for stop in day.get("stops", []):
            sid = stop.get("id", "")
            dur = stop.get("estimated_duration_minutes")
            if sid and dur is not None:
                orig_durations[sid] = int(dur)

    # Fix modified output: if a stop existed before, restore its original duration
    for day in modified.get("days", []):
        for stop in day.get("stops", []):
            sid = stop.get("id", "")
            if sid in orig_durations:
                stop["estimated_duration_minutes"] = orig_durations[sid]


# ── Main entry point ─────────────────────────────────────────────────────────


def _build_modifier_retry_note(last_error: str) -> str:
    """
    Build a targeted retry note for the modifier agent based on the error.

    Parses the error to detect the type of JSON issue and gives the LLM
    focused guidance on how to fix it.
    """
    error_lower = last_error.lower()

    # Missing comma between fields/values (most common Gemini issue)
    if "expecting '" in error_lower and "delimiter" in error_lower:
        return (
            f"\n\nYour previous output had a JSON formatting error: missing comma. "
            f"Error: {last_error}. "
            f"\nPlease ensure EVERY field and value in the JSON object is separated "
            f"by a comma. Common mistakes: missing commas between object properties, "
            f"between array elements, or before nested objects. "
            f"Return ONLY the raw JSON object \u2014 no preamble, no markdown fences."
        )

    # Missing property name (another common JSON issue)
    if "expecting property name" in error_lower:
        return (
            f"\n\nYour previous output had a JSON formatting error: missing property name. "
            f"Error: {last_error}. "
            f"\nThis often means a comma is missing before a new key-value pair. "
            f"Ensure every object key is enclosed in double quotes and preceded "
            f"by a comma when following another property. "
            f"Return ONLY the raw JSON object \u2014 no preamble, no markdown fences."
        )

    # Truncated/incomplete JSON
    if "unterminated" in error_lower or "unexpected end" in error_lower:
        return (
            f"\n\nYour previous output was truncated or incomplete. "
            f"Error: {last_error}. "
            f"\nYou MUST output the COMPLETE modified itinerary JSON \u2014 "
            f"every day, every stop, and every accommodation suggestion. "
            f"Do not abbreviate or skip sections. "
            f"Return ONLY the complete raw JSON object."
        )

    # Extra data after valid JSON (trailing commentary)
    if "extra data" in error_lower:
        return (
            f"\n\nYour previous output had extra text after the JSON object. "
            f"Error: {last_error}. "
            f"\nReturn ONLY the raw JSON object with NO text before or after. "
            f"No explanation, no markdown, no notes."
        )

    # Generic fallback - include the actual error
    return (
        f"\n\nYour previous output was invalid JSON. "
        f"Error: {last_error}. "
        f"\nReturn ONLY a single valid JSON object starting with {{ and ending with }}. "
        f"No preamble, no markdown fences, no trailing text."
    )


async def run_itinerary_modifier(
    current_itinerary: dict,
    modification_request: str,
    available_places: list[dict],
    preferences: dict | None = None,
) -> dict:
    """
    Run the Itinerary Modifier Agent.

    Args:
        current_itinerary: The full itinerary JSON from the last pipeline run.
        modification_request: The user's edit request (e.g. "swap the Egyptian
            Museum for something more entertaining").
        available_places: Pool of candidate places from the last retrieval
            (used as the source for swaps/additions).
        preferences: Optional dict with budget/pace/interests for context.

    Returns:
        Modified itinerary JSON (same schema as pipeline output).
        If modification fails, returns the original itinerary unchanged.
    """
    if not current_itinerary or not modification_request:
        return current_itinerary

    # Trim available places to only the info the modifier needs
    trimmed_pool = [_trim_for_modifier(p) for p in (available_places or [])]

    # Remove places already in the itinerary (no point suggesting them)
    used_ids = set()
    for day in current_itinerary.get("days", []):
        for stop in day.get("stops", []):
            used_ids.add(stop.get("id", ""))
    for hotel in current_itinerary.get("accommodation_suggestions", []):
        used_ids.add(hotel.get("id", ""))
    fresh_pool = [p for p in trimmed_pool if p["id"] not in used_ids]

    # Detect category from modification request and promote matching places
    # to the front so they survive the pool capping / halving below.
    category_hints = _detect_category_from_request(modification_request)
    fresh_pool = _reorder_pool_by_category(fresh_pool, category_hints)

    # Cap the pool to avoid blowing the token budget
    fresh_pool = fresh_pool[:60]

    # Build preferences context
    pref_text = ""
    if preferences:
        parts = []
        if preferences.get("budget_level"):
            parts.append(f"budget: {preferences['budget_level']}")
        if preferences.get("travel_style"):
            parts.append(f"style: {preferences['travel_style']}")
        if preferences.get("pace"):
            parts.append(f"pace: {preferences['pace']}")
        if preferences.get("interests"):
            parts.append(f"interests: {', '.join(preferences['interests'])}")
        if preferences.get("food_preferences"):
            parts.append(f"food: {', '.join(preferences['food_preferences'])}")
        if parts:
            pref_text = "User preferences:\n" + "\n".join(parts)

    # Trim both the itinerary and the pool to stay within token limits
    trimmed_itinerary = _trim_itinerary(current_itinerary)

    # Rough token estimate: ~4 chars per token.  Include the system prompt
    # and template wrapper overhead so we don't blow past Groq's 12k TPM.
    overhead = len(MODIFIER_SYSTEM_PROMPT) + len(pref_text) + 400  # 400 for template text
    pool_json = json.dumps(fresh_pool, indent=2, ensure_ascii=False)
    itinerary_json = json.dumps(trimmed_itinerary, indent=2, ensure_ascii=False)
    combined_estimate = len(pool_json) + len(itinerary_json) + len(modification_request) + overhead

    # If the combined payload is too large (~35k chars ≈ 8.75k tokens, leaving
    # headroom under 12k TPM), cap the pool further to squeeze under the limit.
    if combined_estimate > 35000:
        # Aim for ~28k chars total (~7k tokens, well under 12k TPM)
        target_total_chars = 28000
        max_pool_chars = max(5000, target_total_chars - len(itinerary_json) - len(modification_request) - overhead)
        while len(pool_json) > max_pool_chars and len(fresh_pool) > 3:
            fresh_pool = fresh_pool[:len(fresh_pool) // 2]
            pool_json = json.dumps(fresh_pool, indent=2, ensure_ascii=False)
        logger.info(
            "[ModifierAgent] Payload large (%d chars) — capped pool to %d places",
            combined_estimate, len(fresh_pool),
        )

    prompt = f"""\
Modification Request: {modification_request}

{pref_text}

Current Itinerary:
{itinerary_json}

Available Places Pool ({len(fresh_pool)} places to choose from):
{pool_json}

Apply the modification now. Return the FULL modified itinerary JSON."""

    messages = [
        SystemMessage(content=MODIFIER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    max_attempts = 3
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            attempt_messages = list(messages)
            if attempt > 1 and last_error:
                retry_note = _build_modifier_retry_note(last_error)
                attempt_messages.append(HumanMessage(content=retry_note))

            response = await invoke_with_fallback("modifier", attempt_messages)
            raw_text = response.content

            # Step 1: Strip preamble, markdown fences, trailing text
            extracted = extract_json_from_llm_output(raw_text)

            # Step 2: Try to repair missing commas (common Gemini issue)
            extracted = repair_missing_commas(extracted)

            # Step 3: Try to repair truncation (unclosed brackets/strings)
            extracted = repair_truncated_json(extracted)

            modified = json.loads(extracted)

            # Validate: must have days and destination
            if not isinstance(modified, dict):
                raise ValueError("Output is not a dict")
            if "days" not in modified:
                raise ValueError("Missing 'days' in modified itinerary")
            if not modified.get("days"):
                raise ValueError("Empty 'days' array")

            # Keep the original destination/duration if modifier omitted them
            if not modified.get("destination"):
                modified["destination"] = current_itinerary.get("destination", "")
            if not modified.get("duration_days"):
                modified["duration_days"] = current_itinerary.get("duration_days", 0)

            # 🛡️ Fix durations for reordered stops (LLM sometimes swaps them)
            _fix_durations_on_reorder(modified, current_itinerary)

            # Reattach full metadata for any new stops
            place_index = {p.get("id", ""): p for p in (available_places or [])}
            for day in modified.get("days", []):
                for stop in day.get("stops", []):
                    stop_id = stop.get("id", "")
                    full = place_index.get(stop_id)
                    if full and stop_id not in used_ids:
                        # Newly added stop — copy full metadata
                        for key in ("address", "maps_link", "photos",
                                    "cuisine_type", "interest_tags",
                                    "phone", "website", "price_level",
                                    "opening_hours", "review_count"):
                            if full.get(key) and not stop.get(key):
                                stop[key] = full[key]

            # Reattach full metadata for new hotels
            for hotel in modified.get("accommodation_suggestions", []):
                hotel_id = hotel.get("id", "")
                full = place_index.get(hotel_id)
                if full and hotel_id not in {h.get("id", "") for h in
                        current_itinerary.get("accommodation_suggestions", [])}:
                    for key in ("address", "maps_link", "photos",
                                "rating", "amenities", "accommodation_type",
                                "category", "price_level"):
                        if full.get(key) and not hotel.get(key):
                            hotel[key] = full[key]

            logger.info(
                "[ModifierAgent] Modification applied: %s",
                modified.get("_modifier_note", "no note")
            )
            return modified

        except Exception as e:
            last_error = str(e)
            logger.warning(
                "[ModifierAgent] Attempt %d/%d failed: %s",
                attempt, max_attempts, last_error,
            )

    # All attempts failed — return original itinerary unchanged
    logger.warning(
        "[ModifierAgent] All %d attempts failed — returning original itinerary",
        max_attempts,
    )
    return current_itinerary
