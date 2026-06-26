"""
PreferenceTracker — Centralised service for managing preference confidence counts.

The ``PreferenceTracker`` is the single source of truth for merging new trip
profile data into a user's accumulated preference history.  It replaces the old
``_merge_profile_into_counts`` private function with a testable, importable
service.

Architecture
------------
::

    Trip Approved
         │
         ▼
    PreferenceTracker.merge()
         │
         ├── Deep-copies existing counts
         ├── Increments observed values
         │
         ▼
    Updated preference_counts
         │
         ▼
    PersonaUpdater.update_persona()     ← reads the updated counts as evidence
"""

from __future__ import annotations

import copy
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Categories where the value is a single enum-like string ───────────────
SCALAR_CATEGORIES = ["budget_level", "travel_style", "pace"]

# ── Categories where the value is a list of strings ──────────────────────
LIST_CATEGORIES = ["interests", "food_preferences", "accommodation_preferences"]

ALL_CATEGORIES = SCALAR_CATEGORIES + LIST_CATEGORIES


class PreferenceTracker:
    """Centralised service for managing preference confidence counts.

    Usage::

        tracker = PreferenceTracker()
        merged = tracker.merge(old_counts=user.preference_counts, profile_data=profile_dict)
        user.preference_counts = merged
    """

    @staticmethod
    def merge(
        old_counts: Optional[dict],
        profile_data: dict,
    ) -> dict:
        """Merge a new TripProfile's data into the user's preference confidence counts.

        For each category in the profile (budget_level, travel_style, pace, etc.),
        increment the count for each observed value.  List-type categories
        (interests, food_preferences, accommodation_preferences) increment every
        item in the list.

        **Crucially**, old counts for categories that are absent from the new
        profile are **preserved** — they are not dropped.

        Args:
            old_counts:    The user's current ``preference_counts`` dict (may be
                           ``None`` or empty ``{}``).
            profile_data:  The plain dict of the approved trip's profile fields
                           (budget_level, travel_style, pace, interests,
                           food_preferences, accommodation_preferences).

        Returns:
            A new dict with the merged counts (old + new).
        """
        # ── Start from a deep copy of old_counts so nothing is lost ──────
        merged: dict = copy.deepcopy(old_counts) if old_counts else {}

        # ── Increment scalar categories ─────────────────────────────────
        for cat in SCALAR_CATEGORIES:
            val = profile_data.get(cat)
            if not val:
                continue
            cat_counts = merged.setdefault(cat, {})
            cat_counts[str(val)] = cat_counts.get(str(val), 0) + 1

        # ── Increment list categories ───────────────────────────────────
        for cat in LIST_CATEGORIES:
            items = profile_data.get(cat) or []
            if not items:
                continue
            cat_counts = merged.setdefault(cat, {})
            for item in items:
                key = str(item).strip()
                if key:
                    cat_counts[key] = cat_counts.get(key, 0) + 1

        return merged

    @staticmethod
    def total_trips(preference_counts: Optional[dict]) -> int:
        """Return the total number of trips reflected in the preference counts.

        This is derived from the highest count across all categories,
        which represents the number of trips that contributed data.
        """
        if not preference_counts:
            return 0

        max_count = 0
        for category_values in preference_counts.values():
            if isinstance(category_values, dict):
                for count in category_values.values():
                    if isinstance(count, (int, float)) and count > max_count:
                        max_count = int(count)

        return max_count
