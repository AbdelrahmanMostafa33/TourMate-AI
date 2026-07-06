# ai_engine/tools/slot_normalizer.py

"""
Deterministic slot normalization — replaces LLM-dependent normalization.

The unified router's LLM extracts raw slot values from user messages.
This module post-processes those values into canonical forms using
keyword matching and fuzzy logic, eliminating LLM unreliability for
straightforward normalization tasks.

Design principle:
    "The AI decides what the user wants. The backend decides what is true."

Usage::

    from ai_engine.tools.slot_normalizer import normalize_extracted_slots

    # After LLM extracts slots:
    extracted = {"budget_level": "mid-range", "pace": "balanced", ...}
    normalized = normalize_extracted_slots(extracted)
    # → {"budget_level": "moderate", "pace": "moderate", ...}
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _contains_word(text: str, keyword: str) -> bool:
    """Check if *keyword* appears as a whole word in *text*.

    Uses regex word-boundary matching to prevent false positives like
    "party" matching "art" or "active" matching "act".

    Examples:
        _contains_word("solo trip", "solo") → True
        _contains_word("party animal", "art") → False
        _contains_word("I want action", "action") → True
    """
    pattern = re.compile(r'\b' + re.escape(keyword) + r'\b')
    return bool(pattern.search(text))


# ══════════════════════════════════════════════════════════════════════════════
# Canonical values (single source of truth)
# ══════════════════════════════════════════════════════════════════════════════

VALID_BUDGET_LEVELS = {"budget", "moderate", "luxury"}
VALID_TRAVEL_STYLES = {"romantic", "adventure", "family", "solo", "cultural", "relaxation"}
VALID_PACES = {"relaxed", "moderate", "packed"}

VALID_ACCOMMODATION_TYPES = {"hostel", "resort", "hotel", "luxury"}


# ══════════════════════════════════════════════════════════════════════════════
# Hotel star class normalization
# ══════════════════════════════════════════════════════════════════════════════

def normalize_hotel_star_class(value: Optional[str | int]) -> Optional[int]:
    """
    Normalize a raw hotel star class value to an integer (1-5).

    Handles both digit-based patterns ("4-star", "5 star", "3-star")
    and word-based patterns ("four star", "five-star", "three star").
    Also accepts bare integers (4, 5) directly.

    Examples::

        normalize_hotel_star_class("4-star")     → 4
        normalize_hotel_star_class("5 star")     → 5
        normalize_hotel_star_class(5)            → 5
        normalize_hotel_star_class("four star")  → 4
        normalize_hotel_star_class("five-star")  → 5
        normalize_hotel_star_class("3")          → 3
        normalize_hotel_star_class("luxury")     → None  (not a star class)
        normalize_hotel_star_class(None)          → None
    """
    if value is None:
        return None

    # Fast-path: if already a valid int, return it directly
    if isinstance(value, int):
        if 1 <= value <= 5:
            return value
        return None

    if not isinstance(value, str):
        return None

    normalized = value.lower().strip()

    # Try direct integer parsing first (e.g. "4", "5")
    try:
        star = int(normalized)
        if 1 <= star <= 5:
            return star
    except (ValueError, TypeError):
        pass

    # Try digit-based pattern: "4-star", "5 star"
    match = re.search(r"(\d+)\s*-?\s*star", normalized)
    if match:
        try:
            star = int(match.group(1))
            if 1 <= star <= 5:
                return star
        except (ValueError, TypeError):
            pass

    # Try word-based patterns: "four star", "five-star"
    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    }
    word_match = re.search(r"(one|two|three|four|five)\s*-?\s*star", normalized)
    if word_match:
        return word_map.get(word_match.group(1))

    # Fallback: standalone single digit 1-5
    single_digit = re.search(r"\b([1-5])\b", normalized)
    if single_digit:
        return int(single_digit.group(1))

    logger.debug("[SlotNormalizer] Could not normalize hotel star class: %r", value)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Budget normalization
# ══════════════════════════════════════════════════════════════════════════════

_BUDGET_MAP: Dict[str, str] = {
    # Already canonical — pass through
    "budget": "budget",
    "moderate": "moderate",
    "luxury": "luxury",

    # Budget synonyms
    "cheap": "budget",
    "low": "budget",
    "low-budget": "budget",
    "low budget": "budget",
    "economy": "budget",
    "affordable": "budget",
    "inexpensive": "budget",
    "broke": "budget",
    "student": "budget",

    # Moderate synonyms
    "medium": "moderate",
    "mid-range": "moderate",
    "mid range": "moderate",
    "mid": "moderate",
    "average": "moderate",
    "standard": "moderate",
    "normal": "moderate",
    "decent": "moderate",
    "reasonable": "moderate",
    "moderate": "moderate",

    # Luxury synonyms
    "high": "luxury",
    "high-end": "luxury",
    "high end": "luxury",
    "expensive": "luxury",
    "luxurious": "luxury",
    "premium": "luxury",
    "generous": "luxury",
    "splurge": "luxury",
    "5-star": "luxury",
    "5 star": "luxury",
    "five star": "luxury",
    "five-star": "luxury",
    "upscale": "luxury",
    "exclusive": "luxury",
    "vip": "luxury",
    "no limit": "luxury",
    "money is no object": "luxury",
    "sky is the limit": "luxury",
}


def normalize_budget(value: Optional[str]) -> Optional[str]:
    """
    Normalize a raw budget string to one of: 'budget', 'moderate', 'luxury'.

    Examples::

        normalize_budget("mid-range")       → "moderate"
        normalize_budget("cheap")           → "budget"
        normalize_budget("five star")       → "luxury"
        normalize_budget("anything")        → None  (not a budget keyword)
        normalize_budget(None)              → None
        normalize_budget("moderate")        → "moderate"  (already canonical)
    """
    if not value or not isinstance(value, str):
        return None

    normalized = value.lower().strip()

    # Direct match (includes all canonical values as keys)
    if normalized in _BUDGET_MAP:
        return _BUDGET_MAP[normalized]

    # Word-boundary substring match (e.g. "I want something mid-range please")
    for keyword, canonical in _BUDGET_MAP.items():
        if _contains_word(normalized, keyword):
            return canonical

    logger.debug("[SlotNormalizer] Could not normalize budget: %r", value)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Pace normalization
# ══════════════════════════════════════════════════════════════════════════════

_PACE_MAP: Dict[str, str] = {
    # Already canonical
    "relaxed": "relaxed",
    "balanced": "moderate",
    "moderate": "moderate",
    "packed": "packed",

    # Relaxed synonyms
    "slow": "relaxed",
    "easy": "relaxed",
    "leisurely": "relaxed",
    "chill": "relaxed",
    "lazy": "relaxed",
    "unhurried": "relaxed",
    "take it easy": "relaxed",
    "no rush": "relaxed",
    "at my own pace": "relaxed",

    # Moderate synonyms (includes all synonyms that were previously "balanced")
    "mixed": "moderate",
    "flexible": "moderate",
    "varied": "moderate",
    "medium": "moderate",
    "normal": "moderate",
    "whatever": "moderate",
    "anything": "moderate",
    "anything goes": "moderate",
    "don't care": "moderate",
    "i don't mind": "moderate",
    "no preference": "moderate",
    "surprise me": "moderate",
    "up to you": "moderate",
    "you decide": "moderate",
    "dealer's choice": "moderate",
    "any": "moderate",

    # Packed synonyms
    "busy": "packed",
    "intense": "packed",
    "full": "packed",
    "hectic": "packed",
    "action-packed": "packed",
    "action packed": "packed",
    "non-stop": "packed",
    "nonstop": "packed",
    "as much as possible": "packed",
    "see everything": "packed",
    "maximize": "packed",
    "maximize my time": "packed",
}


def normalize_pace(value: Optional[str]) -> Optional[str]:
    """
    Normalize a raw pace string to one of: 'relaxed', 'moderate', 'packed'.

    Examples::

        normalize_pace("flexible")          → "moderate"
        normalize_pace("anything")          → "moderate"
        normalize_pace("slow")              → "relaxed"
        normalize_pace("action-packed")     → "packed"
        normalize_pace("moderate")          → "moderate"
        normalize_pace("balanced")          → "moderate"
    """
    if not value or not isinstance(value, str):
        return None

    normalized = value.lower().strip()

    # Direct match (includes all canonical values as keys)
    if normalized in _PACE_MAP:
        return _PACE_MAP[normalized]

    # Word-boundary substring match
    for keyword, canonical in _PACE_MAP.items():
        if _contains_word(normalized, keyword):
            return canonical

    logger.debug("[SlotNormalizer] Could not normalize pace: %r", value)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Travel style normalization
# ══════════════════════════════════════════════════════════════════════════════

_STYLE_MAP: Dict[str, str] = {
    # Already canonical
    "romantic": "romantic",
    "adventure": "adventure",
    "family": "family",
    "solo": "solo",
    "cultural": "cultural",
    "relaxation": "relaxation",

    # Romantic synonyms
    "honeymoon": "romantic",
    "couple": "romantic",
    "couples": "romantic",
    "date": "romantic",
    "anniversary": "romantic",
    "love trip": "romantic",
    "with my partner": "romantic",
    "with my girlfriend": "romantic",
    "with my boyfriend": "romantic",
    "with my wife": "romantic",
    "with my husband": "romantic",

    # Adventure synonyms
    "hiking": "adventure",
    "outdoor": "adventure",
    "outdoors": "adventure",
    "active": "adventure",
    "extreme": "adventure",
    "thrilling": "adventure",
    "adrenaline": "adventure",
    "trekking": "adventure",
    "camping": "adventure",
    "safari": "adventure",
    "diving": "adventure",
    "climbing": "adventure",
    "backpacking": "adventure",
    "wild": "adventure",
    "rugged": "adventure",
    "exploring": "adventure",
    "adventurous": "adventure",
    "action": "adventure",

    # Family synonyms
    "kids": "family",
    "children": "family",
    "child-friendly": "family",
    "child friendly": "family",
    "kid-friendly": "family",
    "kid friendly": "family",
    "family-friendly": "family",
    "family friendly": "family",
    "with kids": "family",
    "with children": "family",
    "with my kids": "family",
    "with my children": "family",
    "family trip": "family",
    "family vacation": "family",

    # Solo synonyms
    "alone": "solo",
    "by myself": "solo",
    "solo trip": "solo",
    "solo travel": "solo",
    "solo travel": "solo",
    "single": "solo",
    "on my own": "solo",
    "independent": "solo",
    "backpacking alone": "solo",

    # Cultural synonyms
    "history": "cultural",
    "museums": "cultural",
    "heritage": "cultural",
    "historic": "cultural",
    "art": "cultural",
    "architecture": "cultural",
    "traditions": "cultural",
    "museum": "cultural",
    "ancient": "cultural",
    "archaeology": "cultural",
    "archaeological": "cultural",
    "religious": "cultural",
    "spiritual": "cultural",
    "cultural travel": "cultural",
    "cultural trip": "cultural",

    # Relaxation synonyms
    "chill": "relaxation",
    "rest": "relaxation",
    "beach": "relaxation",
    "relax": "relaxation",
    "relaxing": "relaxation",
    "unwind": "relaxation",
    "de-stress": "relaxation",
    "destress": "relaxation",
    "spa": "relaxation",
    "peaceful": "relaxation",
    "quiet": "relaxation",
    "tranquil": "relaxation",
    "serene": "relaxation",
    "calm": "relaxation",
    "laid-back": "relaxation",
    "laid back": "relaxation",
    "retreat": "relaxation",
    "vacation": "relaxation",
    "getaway": "relaxation",
    "sunbathing": "relaxation",
    "lounging": "relaxation",
    "nothing planned": "relaxation",
}


def normalize_style(value: Optional[str]) -> Optional[str]:
    """
    Normalize a raw travel style string to one of the canonical values.

    Examples::

        normalize_style("history")        → "cultural"
        normalize_style("honeymoon")      → "romantic"
        normalize_style("hiking")         → "adventure"
        normalize_style("solo trip")      → "solo"
        normalize_style("cultural")       → "cultural"  (already canonical)
        normalize_style("food")           → None  (that's an interest, not a style)
    """
    if not value or not isinstance(value, str):
        return None

    normalized = value.lower().strip()

    # Direct match (includes all canonical values as keys)
    if normalized in _STYLE_MAP:
        return _STYLE_MAP[normalized]

    # Word-boundary substring match (prevents "party" → "art" → "cultural")
    for keyword, canonical in _STYLE_MAP.items():
        if _contains_word(normalized, keyword):
            return canonical

    logger.debug("[SlotNormalizer] Could not normalize travel style: %r", value)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Food preferences normalization
# ══════════════════════════════════════════════════════════════════════════════

_FOOD_SYNONYM_MAP: Dict[str, str] = {
    # Normalize common phrases to canonical food preference tags
    "local food": "local cuisine",
    "local dishes": "local cuisine",
    "local": "local cuisine",
    "traditional food": "local cuisine",
    "traditional dishes": "local cuisine",
    "authentic food": "local cuisine",
    "authentic cuisine": "local cuisine",
    "street food": "street food",
    "street eats": "street food",
    "market food": "street food",
    "food stalls": "street food",
    "vegetarian": "vegetarian",
    "veggie": "vegetarian",
    "meat-free": "vegetarian",
    "meat free": "vegetarian",
    "plant-based": "vegetarian",
    "plant based": "vegetarian",
    "vegan": "vegan",
    "halal": "halal",
    "halal food": "halal",
    "kosher": "kosher",
    "kosher food": "kosher",
    "seafood": "seafood",
    "fish": "seafood",
    "sushi": "seafood",
    "mediterranean": "mediterranean",
    "italian": "italian",
    "chinese": "chinese",
    "japanese": "japanese",
    "indian": "indian",
    "thai": "thai",
    "mexican": "mexican",
    "french": "french",
    "arabic": "arabic",
    "middle eastern": "middle eastern",
    "african": "african",
    "asian": "asian",
    "fast food": "fast food",
    "fine dining": "fine dining",
    "fine-dining": "fine dining",
    "gourmet": "fine dining",
    "michelin": "fine dining",
    "budget food": "budget food",
    "cheap eats": "budget food",
    "buffet": "buffet",
    "all you can eat": "buffet",
    "all-you-can-eat": "buffet",
}


def normalize_food(preferences: Optional[List[str]]) -> Optional[List[str]]:
    """
    Normalize a list of food preference strings.

    - Deduplicates items (case-insensitive)
    - Maps synonyms to canonical tags
    - Strips whitespace
    - Removes empty strings

    Examples::

        normalize_food(["local food", "vegetarian"])
        → ["local cuisine", "vegetarian"]

        normalize_food(["street food", "street eats"])
        → ["street food"]

        normalize_food(None) → None
    """
    if not preferences or not isinstance(preferences, list):
        return None

    seen: set[str] = set()
    result: List[str] = []

    for item in preferences:
        if not item or not isinstance(item, str):
            continue

        normalized = item.lower().strip()
        if not normalized:
            continue

        # Try synonym map first
        canonical = _FOOD_SYNONYM_MAP.get(normalized)

        # Try substring match if no direct match
        if canonical is None:
            for keyword, tag in _FOOD_SYNONYM_MAP.items():
                if _contains_word(normalized, keyword):
                    canonical = tag
                    break

        # If no mapping found, use the original (cleaned)
        if canonical is None:
            canonical = normalized

        # Deduplicate
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)

    return result if result else None


# ══════════════════════════════════════════════════════════════════════════════
# Accommodation preferences normalization
# ══════════════════════════════════════════════════════════════════════════════

_ACCOMMODATION_KEYWORDS: list[tuple[str, str]] = [
    # Order matters: more specific phrases first to avoid partial matches
    # (hostel)
    ("hostel",        "hostel"),
    ("backpacker",    "hostel"),
    ("backpackers",   "hostel"),
    ("dorm",          "hostel"),
    ("dormitory",     "hostel"),
    ("budget stay",   "hostel"),
    ("budget accommodation", "hostel"),
    ("cheap place",   "hostel"),
    ("cheap hotel",   "hostel"),
    ("shared room",   "hostel"),
    # resort
    ("resort",        "resort"),
    ("beach resort",  "resort"),
    ("all-inclusive",  "resort"),
    ("all inclusive",  "resort"),
    ("spa resort",    "resort"),
    ("waterpark",     "resort"),
    ("water park",    "resort"),
    # luxury
    ("luxury",        "luxury"),
    ("luxury hotel",  "luxury"),
    ("boutique",      "luxury"),
    ("boutique hotel","luxury"),
    ("palace",        "luxury"),
    ("premium",       "luxury"),
    ("high-end",      "luxury"),
    ("high end",      "luxury"),
    ("upscale",       "luxury"),
    ("executive",     "luxury"),
    ("villa",         "luxury"),
    ("private villa", "luxury"),
    # hotel (default)
    ("hotel",         "hotel"),
    ("apartment",     "hotel"),
    ("airbnb",        "hotel"),
    ("motel",         "hotel"),
    ("guesthouse",    "hotel"),
    ("guest house",   "hotel"),
    ("bnb",           "hotel"),
    ("bed and breakfast", "hotel"),
    ("bed & breakfast", "hotel"),
    ("standard",      "hotel"),
]


def normalize_accommodation(preferences: Optional[List[str]]) -> Optional[List[str]]:
    """
    Normalize accommodation preference strings to canonical types.

    Always returns a list with ONE item (the dominant preference).

    Examples::

        normalize_accommodation(["boutique hotel"])
        → ["luxury"]

        normalize_accommodation(["cheap place to stay"])
        → ["hostel"]

        normalize_accommodation(["nice resort", "beach resort"])
        → ["resort"]

        normalize_accommodation(["standard hotel"])
        → ["hotel"]
    """
    if not preferences or not isinstance(preferences, list):
        return None

    # Find the dominant (most specific) accommodation type
    # Priority: luxury > resort > hostel > hotel
    result_priority = {"hostel": 1, "hotel": 2, "resort": 3, "luxury": 4}
    best_type: Optional[str] = None
    best_priority = 0

    for item in preferences:
        if not item or not isinstance(item, str):
            continue

        normalized = item.lower().strip()
        if not normalized:
            continue

        # Check keyword matches (specific first, using word-boundary matching)
        matched_type: Optional[str] = None
        for keyword, acc_type in _ACCOMMODATION_KEYWORDS:
            if _contains_word(normalized, keyword):
                matched_type = acc_type
                break

        if matched_type is None:
            # Check if it's already a valid type
            if normalized in VALID_ACCOMMODATION_TYPES:
                matched_type = normalized

        if matched_type:
            priority = result_priority.get(matched_type, 0)
            if priority > best_priority:
                best_type = matched_type
                best_priority = priority

    if best_type:
        return [best_type]

    logger.debug("[SlotNormalizer] Could not normalize accommodation: %r", preferences)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Accommodation → canonical type (shared with Place Retriever)
# ══════════════════════════════════════════════════════════════════════════════


def map_accommodation_to_type(accommodation_preferences: list[str]) -> str:
    """
    Map a list of accommodation preference phrases to a single canonical
    accommodation type string (e.g. 'luxury', 'resort', 'hostel', 'hotel').

    Uses the same keyword list as ``normalize_accommodation()`` but with
    simple substring matching (``keyword in pref_lower``) instead of
    word-boundary matching, consistent with the Place Retriever's existing
    filter logic.

    Returns the last matching type, or an empty string if no match.
    """
    result = ""
    for pref in accommodation_preferences:
        pref_lower = pref.lower().strip()
        for keyword, acc_type in _ACCOMMODATION_KEYWORDS:
            if keyword in pref_lower:
                result = acc_type
                break
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Interest normalization
# ══════════════════════════════════════════════════════════════════════════════

# Command verbs that indicate an instruction, not an interest (used to filter noise)
_INTEREST_COMMAND_VERBS: set[str] = {
    "remove", "swap", "add", "delete", "change", "insert",
    "replace", "drop", "update", "modify", "edit", "reorder",
    "move", "put", "take", "shift", "switch", "exchange",
}

_INTEREST_SYNONYM_MAP: Dict[str, str] = {
    "history": "history",
    "historical": "history",
    "historic": "history",
    "historic sites": "history",
    "heritage": "history",
    "ancient": "history",
    "architecture": "architecture",
    "buildings": "architecture",
    "art": "art",
    "art galleries": "art",
    "gallery": "art",
    "galleries": "art",
    "museums": "museums",
    "museum": "museums",
    "culture": "museums",
    "cultural sites": "museums",
    "food": "food",
    "cuisine": "food",
    "eating": "food",
    "dining": "food",
    "shopping": "shopping",
    "markets": "shopping",
    "bazaar": "shopping",
    "souvenirs": "shopping",
    "mall": "shopping",
    "malls": "shopping",
    "nightlife": "nightlife",
    "bars": "nightlife",
    "clubs": "nightlife",
    "clubbing": "nightlife",
    "party": "nightlife",
    "partying": "nightlife",
    "entertainment": "entertainment",
    "shows": "entertainment",
    "live shows": "entertainment",
    "night shows": "entertainment",
    "nature": "nature",
    "parks": "parks",
    "park": "parks",
    "gardens": "parks",
    "garden": "parks",
    "family": "family",
    "family activities": "family",
    "family-friendly": "family",
    "family friendly": "family",
    "kid-friendly": "family",
    "kid friendly": "family",
    "child-friendly": "family",
    "child friendly": "family",
    "nature walks": "nature",
    "wildlife": "nature",
    "photography": "photography",
    "photos": "photography",
    "sightseeing": "sightseeing",
    "landmarks": "sightseeing",
    "monuments": "sightseeing",
    "viewpoints": "sightseeing",
    "scenic spots": "sightseeing",
    "adventure": "adventure",
    "outdoor activities": "adventure",
    "sports": "sports",
    "fitness": "sports",
    "water sports": "water sports",
    "snorkeling": "water sports",
    "diving": "water sports",
    "surfing": "water sports",
    "religion": "religion",
    "religious sites": "religion",
    "temples": "religion",
    "mosques": "religion",
    "churches": "religion",
    "beaches": "beaches",
    "beach": "beaches",
    "coast": "beaches",
    "wine": "wine",
    "wine tasting": "wine",
    "vineyards": "wine",
    "local life": "local culture",
    "local culture": "local culture",
    "daily life": "local culture",
    "music": "music",
    "concerts": "music",
    "festivals": "festivals",
    "events": "festivals",
    "science": "science",
    "technology": "technology",
    "tech": "technology",
    "wellness": "wellness",
    "spa": "wellness",
    "yoga": "wellness",
    "meditation": "wellness",
}


def normalize_interests(interests: Optional[List[str]]) -> Optional[List[str]]:
    """
    Normalize a list of interest strings to canonical tags.

    Filters out noise: commands ('remove X', 'swap Y', 'add Z'), specific place names
    ('Al-Azhar Mosque', 'Eiffel Tower'), and multi-word instructions.

    - Deduplicates items (case-insensitive)
    - Maps synonyms to canonical tags
    - Strips whitespace
    - Skips items containing command verbs (remove, swap, add, delete, etc.)
    - Skips items longer than 5 words (likely instructions, not interest keywords)

    Examples::

        normalize_interests(["museums", "art galleries", "history"])
        → ["museums", "art", "history"]

        normalize_interests(["sightseeing", "landmarks", "photos"])
        → ["sightseeing", "photography"]

        normalize_interests(["remove abo tarek restaurant from the itinerary", "museums"])
        → ["museums"]  (command phrase filtered out)
    """
    if not interests or not isinstance(interests, list):
        return None

    seen: set[str] = set()
    result: List[str] = []

    for item in interests:
        if not item or not isinstance(item, str):
            continue

        normalized = item.lower().strip()
        if not normalized:
            continue

        # ── Noise filters ────────────────────────────────────────────
        # Skip items containing command verbs (e.g. "remove abo tarek" → filtered)
        if any(_contains_word(normalized, verb) for verb in _INTEREST_COMMAND_VERBS):
            logger.debug(
                "[SlotNormalizer] Filtered out command-like interest: %r", item
            )
            continue

        # Skip items that are too long (> 5 words suggests an instruction, not keyword)
        word_count = len(normalized.split())
        if word_count > 5:
            logger.debug(
                "[SlotNormalizer] Filtered out long interest phrase (%d words): %r",
                word_count, item,
            )
            continue

        # ── Synonym matching ─────────────────────────────────────────
        # Try synonym map
        canonical = _INTEREST_SYNONYM_MAP.get(normalized)

        # Try substring match
        if canonical is None:
            for keyword, tag in _INTEREST_SYNONYM_MAP.items():
                if _contains_word(normalized, keyword):
                    canonical = tag
                    break

        if canonical is None:
            canonical = normalized

        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)

    return result if result else None


# ══════════════════════════════════════════════════════════════════════════════
# Traveler group type normalization
# ══════════════════════════════════════════════════════════════════════════════

VALID_TRAVELER_GROUP_TYPES = {"solo", "couple", "family", "friends", "business"}

_TRAVELER_GROUP_MAP: Dict[str, str] = {
    # Already canonical
    "solo": "solo",
    "couple": "couple",
    "family": "family",
    "friends": "friends",
    "business": "business",

    # Solo synonyms
    "alone": "solo",
    "by myself": "solo",
    "just me": "solo",
    "solo traveler": "solo",
    "solo travel": "solo",
    "single": "solo",
    "on my own": "solo",
    "independent": "solo",
    "traveling alone": "solo",
    "travelling alone": "solo",
    "one person": "solo",
    "just myself": "solo",

    # Couple synonyms
    "romantic": "couple",
    "honeymoon": "couple",
    "with my partner": "couple",
    "with my girlfriend": "couple",
    "with my boyfriend": "couple",
    "with my wife": "couple",
    "with my husband": "couple",
    "with my spouse": "couple",
    "as a couple": "couple",
    "two people": "couple",
    "pair": "couple",
    "date": "couple",
    "anniversary": "couple",
    "me and my partner": "couple",

    # Family synonyms
    "with kids": "family",
    "with children": "family",
    "with my kids": "family",
    "with my children": "family",
    "with my family": "family",
    "family trip": "family",
    "family vacation": "family",
    "family holiday": "family",
    "kids": "family",
    "children": "family",
    "child": "family",
    "baby": "family",
    "toddler": "family",
    "multi-generational": "family",
    "multigenerational": "family",
    "extended family": "family",

    # Friends synonyms
    "with friends": "friends",
    "with my friends": "friends",
    "group of friends": "friends",
    "friend group": "friends",
    "buddies": "friends",
    "mates": "friends",
    "pals": "friends",
    "crew": "friends",
    "gang": "friends",
    "squad": "friends",
    "besties": "friends",

    # Business synonyms
    "work": "business",
    "work trip": "business",
    "business trip": "business",
    "corporate": "business",
    "conference": "business",
    "meeting": "business",
    "workation": "business",
    "professional": "business",
    "work travel": "business",
    "work-related": "business",
    "work related": "business",
    "business travel": "business",
}


def normalize_traveler_group_type(value: Optional[str]) -> Optional[str]:
    """
    Normalize a raw traveler group type string to one of:
    'solo', 'couple', 'family', 'friends', 'business'.

    Examples::

        normalize_traveler_group_type("just me")       → "solo"
        normalize_traveler_group_type("with my wife")  → "couple"
        normalize_traveler_group_type("with kids")     → "family"
        normalize_traveler_group_type("group of friends") → "friends"
        normalize_traveler_group_type("business trip") → "business"
        normalize_traveler_group_type(None)             → None
    """
    if not value or not isinstance(value, str):
        return None

    normalized = value.lower().strip()

    # Direct match (includes all canonical values as keys)
    if normalized in _TRAVELER_GROUP_MAP:
        return _TRAVELER_GROUP_MAP[normalized]

    # Word-boundary substring match
    for keyword, canonical in _TRAVELER_GROUP_MAP.items():
        if _contains_word(normalized, keyword):
            return canonical

    logger.debug("[SlotNormalizer] Could not normalize traveler_group_type: %r", value)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Main entry point — normalize all extracted slots at once
# ══════════════════════════════════════════════════════════════════════════════

def normalize_extracted_slots(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply deterministic normalization to all extracted slot values.

    This function is the single entry point called after the LLM extracts
    slots from the user's message. It ensures every categorical field is
    in its canonical form before being stored in ConversationState.

    Args:
        extracted: Raw dict from LLM extraction (may contain non-canonical values).

    Returns:
        Dict with normalized values. Only includes fields that were present
        in the input (or successfully normalized). None values are dropped.

    Example::

        raw = {
            "budget_level": "mid-range",
            "pace": "balanced",
            "travel_style": "honeymoon",
            "food_preferences": ["local food", "street food"],
            "accommodation_preferences": ["boutique hotel"],
            "interests": ["museums", "art galleries"],
        }
        normalized = normalize_extracted_slots(raw)
        # {
        #     "budget_level": "moderate",
        #     "pace": "moderate",
        #     "travel_style": "romantic",
        #     "food_preferences": ["local cuisine", "street food"],
        #     "accommodation_preferences": ["luxury"],
        #     "interests": ["museums", "art"],
        # }
    """
    result = dict(extracted)

    # ── Scalar normalizations ────────────────────────────────────────────

    if "budget_level" in result:
        result["budget_level"] = normalize_budget(result["budget_level"])

    if "pace" in result:
        result["pace"] = normalize_pace(result["pace"])

    if "travel_style" in result:
        result["travel_style"] = normalize_style(result["travel_style"])

    if "traveler_group_type" in result:
        result["traveler_group_type"] = normalize_traveler_group_type(result["traveler_group_type"])

    # ── List normalizations ──────────────────────────────────────────────

    if "food_preferences" in result:
        result["food_preferences"] = normalize_food(result["food_preferences"])

    if "accommodation_preferences" in result:
        result["accommodation_preferences"] = normalize_accommodation(
            result["accommodation_preferences"]
        )

    if "interests" in result:
        result["interests"] = normalize_interests(result["interests"])

    # ── Hotel star class normalization ────────────────────────────────────

    if "preferred_hotel_star_class" in result:
        result["preferred_hotel_star_class"] = normalize_hotel_star_class(
            result["preferred_hotel_star_class"]
        )

    # ── Drop None values ─────────────────────────────────────────────────

    result = {k: v for k, v in result.items() if v is not None}

    return result
