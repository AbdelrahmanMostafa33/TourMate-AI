"""
Itinerary Metrics — Quantitative quality scoring for generated itineraries.

Computes measurable quality signals for a generated itinerary:
    - Category diversity  — Mix of attraction/restaurant/etc. across the itinerary
    - Interest alignment  — How well stops match user preferences
    - Pacing              — Balanced vs. rushed day distribution
    - Geographic coverage — Spread of stops across the destination

Each score is normalized to 0.0–1.0. A composite ``overall`` score is also
provided, weighted toward interest alignment (most important to users).

Usage::

    from ai_engine.evaluation.itinerary_metrics import compute_all_metrics

    metrics = compute_all_metrics(itinerary, profile)
    # {
    #   "category_diversity": 0.85,
    #   "interest_alignment": 0.72,
    #   "pacing": 0.91,
    #   "geographic_coverage": 0.65,
    #   "overall": 0.78,
    # }
"""

from __future__ import annotations

import math
from typing import Optional

from ai_engine.tools.haversine import haversine


# ── Composite Weights ─────────────────────────────────────────────────────────

_WEIGHT_DIVERSITY = 0.30   # Category diversity (evenness + mixing)
_WEIGHT_INTEREST  = 0.35   # Interest alignment (most important to users)
_WEIGHT_PACING    = 0.20   # Pacing / load balance
_WEIGHT_COVERAGE  = 0.15   # Geographic spread

# ── Pacing Thresholds ────────────────────────────────────────────────────────

_IDEAL_STOPS_PER_DAY_MIN = 3          # minimum recommended stops
_IDEAL_STOPS_PER_DAY_MAX = 5          # max before it feels rushed
_IDEAL_DURATION_MIN      = 240        # 4 hours minimum
_IDEAL_DURATION_MAX      = 600        # 10 hours max
_MAX_CV                  = 0.8        # coefficient of variation cap

# ── Interest-to-Subcategory Mapping ─────────────────────────────────────────

_INTEREST_TO_SUBCATEGORY: dict[str, list[str]] = {
    "history":       ["history", "historical"],
    "nightlife":     ["nightlife", "entertainment", "bar", "club"],
    "shopping":      ["shopping", "market", "mall"],
    "parks":         ["parks", "garden", "nature"],
    "museums":       ["museums", "museum", "gallery"],
    "culture":       ["museums", "history", "art", "cultural", "heritage"],
    "nature":        ["nature", "parks", "garden", "beach", "waterfront"],
    "religious":     ["religious", "mosque", "church", "temple", "shrine"],
    "family":        ["family", "park", "entertainment", "kids"],
    "sports":        ["sports", "stadium", "arena"],
    "wellness":      ["wellness", "spa", "health", "hamam"],
    "entertainment": ["entertainment", "nightlife", "cinema", "theatre"],
    "art":           ["art", "museum", "gallery", "street art"],
    "food":          [],   # matched via food_preferences instead of subcategory
    "adventure":     ["adventure", "sports", "nature", "outdoor"],
    "sightseeing":   ["sightseeing", "landmark", "monument", "viewpoint"],
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _normalize(value: str) -> str:
    """Normalize a string for matching."""
    return value.lower().strip()


def _get_all_stops(itinerary: dict) -> list[dict]:
    """Extract all stops across all days into a flat list."""
    stops: list[dict] = []
    for day in itinerary.get("days", []):
        stops.extend(day.get("stops", []))
    return stops


def _get_subcategory(stop: dict) -> str:
    """Get the sub_category from a stop, handling different key names."""
    return _normalize(stop.get("sub_category") or stop.get("subcategory", ""))


def _get_interest_tags(stop: dict) -> list[str]:
    """Get interest_tags from a stop, returning normalized lowercase list."""
    tags = stop.get("interest_tags") or []
    return [_normalize(t) for t in tags if t]


# ═══════════════════════════════════════════════════════════════════════════════
# Metric: Category Diversity
# ═══════════════════════════════════════════════════════════════════════════════


def score_category_diversity(itinerary: dict) -> float:
    """
    Evaluate category diversity across the itinerary.

    Components:
        1. Overall balance — Shannon evenness across categories (60% weight)
        2. Per-day mixing  — Penalty for 3+ consecutive same-category (40% weight)

    Returns:
        Float 0.0–1.0, higher = more diverse.
    """
    stops = _get_all_stops(itinerary)
    if not stops:
        return 0.0

    # ── 1. Shannon Evenness ─────────────────────────────────────────────
    cat_counts: dict[str, int] = {}
    for s in stops:
        cat = _normalize(s.get("category", "other"))
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    n_categories = len(cat_counts)
    total = len(stops)

    if n_categories <= 1:
        evenness = 0.0
    else:
        entropy = 0.0
        for count in cat_counts.values():
            p = count / total
            entropy -= p * math.log(p)
        evenness = entropy / math.log(n_categories) if n_categories > 1 else 0.0

    # ── 2. Per-day Consecutive Category Penalty ─────────────────────────
    penalty_count = 0
    total_stops_checked = 0
    for day in itinerary.get("days", []):
        day_stops = day.get("stops", [])
        consecutive = 1
        for i in range(1, len(day_stops)):
            prev = _normalize(day_stops[i - 1].get("category", ""))
            curr = _normalize(day_stops[i].get("category", ""))
            if prev == curr and prev != "hotel":
                consecutive += 1
                if consecutive > 2:
                    penalty_count += 1
            else:
                consecutive = 1
        total_stops_checked += len(day_stops)

    mixing_ratio = 1.0
    if total_stops_checked > 0:
        mixing_ratio = 1.0 - (penalty_count / max(total_stops_checked, 1))

    # ── Combine ─────────────────────────────────────────────────────────
    score = 0.60 * evenness + 0.40 * mixing_ratio
    return round(min(max(score, 0.0), 1.0), 4)


# ═══════════════════════════════════════════════════════════════════════════════
# Metric: Interest Alignment
# ═══════════════════════════════════════════════════════════════════════════════


def score_interest_alignment(
    itinerary: dict,
    profile: Optional[dict] = None,
) -> float:
    """
    Evaluate how well the itinerary matches the user's stated interests.

    Components:
        1. **Coverage** — What fraction of user interests appear in the
           itinerary? (60% weight)
        2. **Depth** — For covered interests, are they well-represented
           without being over-saturated? (40% weight)

    User interests can match stops via:
        - Stop's ``interest_tags`` field (direct match)
        - Stop's ``sub_category`` field (mapped via :data:`_INTEREST_TO_SUBCATEGORY`)
        - Food preferences match ``cuisine_type`` on restaurant stops

    Returns:
        Float 0.0–1.0, higher = better alignment. Returns 0.5 (neutral)
        when no profile is available.
    """
    if not profile:
        return 0.5

    interests = profile.get("interests") or []
    food_prefs = profile.get("food_preferences") or []

    if not interests and not food_prefs:
        return 0.5  # neutral — nothing to match against

    stops = _get_all_stops(itinerary)
    if not stops:
        return 0.0

    # ── Build interest-to-stop mapping ──────────────────────────────────
    matched_interests: dict[str, list[dict]] = {}
    for interest in interests:
        matched_interests[_normalize(interest)] = []
    for food_pref in food_prefs:
        matched_interests[f"food:{_normalize(food_pref)}"] = []

    for stop in stops:
        stop_tags = _get_interest_tags(stop)
        stop_subcat = _get_subcategory(stop)
        stop_cat = _normalize(stop.get("category", ""))

        # Check each standard interest
        for interest in interests:
            norm = _normalize(interest)
            if norm not in matched_interests:
                matched_interests[norm] = []

            # Direct tag match
            if norm in stop_tags:
                matched_interests[norm].append(stop)
                continue

            # Subcategory mapping match
            relevant_subcats = _INTEREST_TO_SUBCATEGORY.get(norm, [])
            if stop_subcat in relevant_subcats:
                matched_interests[norm].append(stop)
                continue

        # Check food preferences against restaurant stops
        if stop_cat == "restaurant":
            stop_cuisine = _normalize(stop.get("cuisine_type", ""))
            for food_pref in food_prefs:
                fnorm = _normalize(food_pref)
                key = f"food:{fnorm}"
                if key not in matched_interests:
                    matched_interests[key] = []

                if fnorm in stop_tags or (stop_cuisine and fnorm in stop_cuisine):
                    matched_interests[key].append(stop)

    # ── Coverage: what % of interests are represented? ─────────────────
    total_interests = len(interests) + len(food_prefs)
    covered_count = sum(1 for sl in matched_interests.values() if sl)
    coverage = covered_count / total_interests if total_interests > 0 else 0.5

    # ── Depth: are interests over/under-represented? ──────────────────
    ideal_per_interest = max(1.0, len(stops) / max(total_interests, 1))
    depth_scores: list[float] = []
    for sl in matched_interests.values():
        actual = len(sl)
        if actual == 0:
            depth_scores.append(0.0)
        elif actual <= ideal_per_interest * 1.5:
            depth_scores.append(min(1.0, actual / ideal_per_interest))
        else:
            # Over-represented → diminishing returns penalty
            depth_scores.append(max(0.3, ideal_per_interest / actual))

    avg_depth = sum(depth_scores) / len(depth_scores) if depth_scores else 0.0

    # ── Combine ─────────────────────────────────────────────────────────
    score = 0.60 * coverage + 0.40 * avg_depth
    return round(min(max(score, 0.0), 1.0), 4)


# ═══════════════════════════════════════════════════════════════════════════════
# Metric: Pacing
# ═══════════════════════════════════════════════════════════════════════════════


def score_pacing(itinerary: dict) -> float:
    """
    Evaluate itinerary pacing — is the trip balanced or rushed?

    Components:
        1. Stop count consistency — CV of stops-per-day across days (40%)
        2. Daily load — stops count + estimated duration per day (40%)
        3. Time-of-day spread — how many of 3 time slots are used (20%)

    Returns:
        Float 0.0–1.0, higher = better paced.
    """
    days = itinerary.get("days", [])
    if not days:
        return 0.0

    stops_per_day = [len(d.get("stops", [])) for d in days]

    # ── 1. Stop Count Consistency ───────────────────────────────────────
    if len(stops_per_day) > 1:
        mean_stops = sum(stops_per_day) / len(stops_per_day)
        variance = sum((s - mean_stops) ** 2 for s in stops_per_day) / len(stops_per_day)
        std_dev = variance ** 0.5
        cv = std_dev / mean_stops if mean_stops > 0 else 999.0
        consistency = max(0.0, 1.0 - min(cv / _MAX_CV, 1.0))
    else:
        consistency = 1.0  # single day is always consistent

    # ── 2. Daily Load Reasonableness ───────────────────────────────────
    load_scores: list[float] = []
    for day in days:
        n_stops = len(day.get("stops", []))
        total_dur = sum(
            s.get("estimated_duration_minutes", 60) for s in day.get("stops", [])
        )

        # Stop count: ideal is 3–5
        if n_stops < _IDEAL_STOPS_PER_DAY_MIN:
            stop_score = n_stops / _IDEAL_STOPS_PER_DAY_MIN
        elif n_stops <= _IDEAL_STOPS_PER_DAY_MAX:
            stop_score = 1.0
        else:
            stop_score = max(0.0, 1.0 - (n_stops - _IDEAL_STOPS_PER_DAY_MAX) * 0.15)

        # Duration: ideal is 4–10 hours (240–600 min)
        if total_dur < _IDEAL_DURATION_MIN:
            dur_score = total_dur / _IDEAL_DURATION_MIN
        elif total_dur <= _IDEAL_DURATION_MAX:
            dur_score = 1.0
        else:
            dur_score = max(0.0, 1.0 - (total_dur - _IDEAL_DURATION_MAX) * 0.002)

        load_scores.append(0.50 * stop_score + 0.50 * dur_score)

    avg_load = sum(load_scores) / len(load_scores) if load_scores else 0.0

    # ── 3. Time-of-Day Spread ──────────────────────────────────────────
    time_slot_scores: list[float] = []
    for day in days:
        slots = {s.get("suggested_time_of_day", "") for s in day.get("stops", [])}
        time_slot_scores.append(len(slots) / 3.0)
    avg_time_spread = (
        sum(time_slot_scores) / len(time_slot_scores) if time_slot_scores else 0.0
    )

    # ── Combine ─────────────────────────────────────────────────────────
    score = 0.40 * consistency + 0.40 * avg_load + 0.20 * avg_time_spread
    return round(min(max(score, 0.0), 1.0), 4)


# ═══════════════════════════════════════════════════════════════════════════════
# Metric: Geographic Coverage
# ═══════════════════════════════════════════════════════════════════════════════


def score_geographic_coverage(itinerary: dict) -> float:
    """
    Evaluate geographic spread — are stops spread across the destination
    or clustered in one small area?

    Uses :func:`haversine` distance to compute:
        1. Max pairwise distance between any two stops (normalized)
        2. Average distance from the geographic centroid

    A very tight cluster (all stops within 1 km) gets a low score because
    the user misses out on exploring different areas. An ideal spread is
    10–30 km between farthest stops.

    Returns:
        Float 0.0–1.0, higher = better geographic coverage.
    """
    stops = _get_all_stops(itinerary)
    if len(stops) < 2:
        return 0.0

    # Filter to stops with valid coordinates
    valid: list[tuple[float, float]] = []
    for s in stops:
        lat = s.get("lat")
        lon = s.get("lon")
        if lat and lon and lat != 0.0 and lon != 0.0:
            valid.append((float(lat), float(lon)))

    if len(valid) < 2:
        return 0.0

    # ── 1. Max Pairwise Distance ────────────────────────────────────────
    max_dist = 0.0
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            dist = haversine(valid[i][0], valid[i][1], valid[j][0], valid[j][1])
            if dist > max_dist:
                max_dist = dist

    # Normalize: ideal spread is 10–30 km for a city trip
    if max_dist <= 1.0:
        max_dist_score = 0.1      # all clustered together
    elif max_dist <= 15:
        max_dist_score = 0.3 + 0.7 * (max_dist / 15.0)  # ramp 0.3→1.0
    elif max_dist <= 30:
        max_dist_score = 1.0      # ideal
    else:
        max_dist_score = max(0.2, 1.0 - (max_dist - 30) * 0.02)  # gradual decline

    # ── 2. Average Distance from Centroid ──────────────────────────────
    center_lat = sum(lat for lat, _ in valid) / len(valid)
    center_lon = sum(lon for _, lon in valid) / len(valid)
    avg_dist = sum(
        haversine(lat, lon, center_lat, center_lon) for lat, lon in valid
    ) / len(valid)

    if avg_dist <= 0.5:
        centroid_score = 0.1
    elif avg_dist <= 10:
        centroid_score = 0.2 + 0.8 * (avg_dist / 10.0)
    elif avg_dist <= 20:
        centroid_score = 1.0
    else:
        centroid_score = max(0.2, 1.0 - (avg_dist - 20) * 0.02)

    # ── Combine ─────────────────────────────────────────────────────────
    score = 0.50 * max_dist_score + 0.50 * centroid_score
    return round(min(max(score, 0.0), 1.0), 4)


# ═══════════════════════════════════════════════════════════════════════════════
# Composite API
# ═══════════════════════════════════════════════════════════════════════════════


def compute_all_metrics(
    itinerary: dict,
    profile: Optional[dict] = None,
) -> dict[str, float]:
    """
    Compute all itinerary quality metrics.

    Args:
        itinerary: The generated itinerary dict (``optimized_itinerary``
            or ``draft_itinerary`` from TripState).
        profile: Optional :class:`~ai_engine.graph.state.TripProfile` dict
            with user interests and food preferences.

    Returns:
        A dict with per-metric scores (0.0–1.0) and an ``overall`` composite::

            {
                "category_diversity": 0.85,
                "interest_alignment": 0.72,
                "pacing": 0.91,
                "geographic_coverage": 0.65,
                "overall": 0.78,
            }
    """
    diversity = score_category_diversity(itinerary)
    interest = score_interest_alignment(itinerary, profile)
    pacing = score_pacing(itinerary)
    coverage = score_geographic_coverage(itinerary)

    overall = (
        _WEIGHT_DIVERSITY * diversity
        + _WEIGHT_INTEREST * interest
        + _WEIGHT_PACING * pacing
        + _WEIGHT_COVERAGE * coverage
    )

    return {
        "category_diversity": diversity,
        "interest_alignment": interest,
        "pacing": pacing,
        "geographic_coverage": coverage,
        "overall": round(overall, 4),
    }
