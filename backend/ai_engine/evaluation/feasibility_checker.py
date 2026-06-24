"""
Feasibility Checker — Programmatic validation of itinerary feasibility.

Provides deterministic, rule-based checks that verify an itinerary is
physically and logistically possible. These checks run **before** the
LLM-based quality review in the Itinerary Validator.

Checks:
    - Stop count per day (min/max)
    - Total travel time per day
    - Consecutive same-category stops (diversity)
    - Distance between consecutive stops
    - Total number of days
    - Accommodation suggestions count

Usage::

    from ai_engine.evaluation.feasibility_checker import run_programmatic_checks

    issues = run_programmatic_checks(itinerary)
    if issues:
        for issue in issues:
            logger.warning(issue)
"""

from ai_engine.tools.haversine import haversine


# ── Programmatic Validation Thresholds ───────────────────────────────────────

MAX_DAILY_TRAVEL_MINUTES = 180
MAX_DAILY_STOPS = 8
MIN_DAILY_STOPS = 3
MAX_CONSECUTIVE_CATEGORY = 2
MIN_TOTAL_DAYS = 1
MAX_DISTANCE_BETWEEN_STOPS_KM = 40


def run_programmatic_checks(itinerary: dict) -> list[str]:
    """
    Run deterministic feasibility checks on an itinerary dict.

    Returns a list of human-readable issue strings. An empty list means
    the itinerary passed all programmatic checks.

    Args:
        itinerary: The itinerary dict (``optimized_itinerary`` in TripState).

    Returns:
        A list of issue descriptions. Empty if no issues found.
    """
    issues: list[str] = []
    days = itinerary.get("days", [])

    if len(days) < MIN_TOTAL_DAYS:
        issues.append(
            f"Itinerary has only {len(days)} day(s), expected at least {MIN_TOTAL_DAYS}"
        )

    for day in days:
        day_num = day.get("day_number", "?")
        stops = day.get("stops", [])

        if len(stops) > MAX_DAILY_STOPS:
            issues.append(
                f"Day {day_num}: {len(stops)} stops exceeds max of {MAX_DAILY_STOPS}"
            )
        if len(stops) < MIN_DAILY_STOPS:
            issues.append(
                f"Day {day_num}: only {len(stops)} stop(s), add more activities"
            )

        consecutive = 1
        for i in range(1, len(stops)):
            prev_cat = stops[i - 1].get("category", "")
            curr_cat = stops[i].get("category", "")
            if prev_cat == curr_cat and prev_cat != "hotel":
                consecutive += 1
                if consecutive > MAX_CONSECUTIVE_CATEGORY:
                    issues.append(
                        f"Day {day_num}: {consecutive} consecutive '{curr_cat}' stops "
                        f"(max {MAX_CONSECUTIVE_CATEGORY})"
                    )
            else:
                consecutive = 1

        total_travel = day.get("total_travel_time_minutes", 0)
        if total_travel > MAX_DAILY_TRAVEL_MINUTES:
            issues.append(
                f"Day {day_num}: {total_travel} min travel time "
                f"exceeds {MAX_DAILY_TRAVEL_MINUTES} min limit"
            )

        for i in range(len(stops) - 1):
            s1, s2 = stops[i], stops[i + 1]
            if s1.get("lat") and s1.get("lon") and s2.get("lat") and s2.get("lon"):
                dist = haversine(s1["lat"], s1["lon"], s2["lat"], s2["lon"])
                if dist > MAX_DISTANCE_BETWEEN_STOPS_KM:
                    issues.append(
                        f"Day {day_num}: Stop '{s1.get('name', '?')}' to "
                        f"'{s2.get('name', '?')}' is {dist:.1f}km — too far"
                    )

    hotels = itinerary.get("accommodation_suggestions", [])
    if len(hotels) == 0:
        issues.append("No accommodation suggestions provided")
    elif len(hotels) > 5:
        issues.append(f"{len(hotels)} hotel suggestions is too many (max 5)")

    _TIME_RANK = {"morning": 0, "afternoon": 1, "evening": 2}
    for day in days:
        day_num = day.get("day_number", "?")
        stops = day.get("stops", [])
        prev_rank = -1
        for i, stop in enumerate(stops):
            slot = stop.get("suggested_time_of_day", "")
            rank = _TIME_RANK.get(slot, -1)
            if rank < prev_rank:
                issues.append(
                    f'Day {day_num}: stop #{i + 1} "{stop.get("name", "?")}" '
                    f'has suggested_time_of_day="{slot}" which is out of order '
                    f'(previous was "{stops[i - 1].get("suggested_time_of_day", "?")}")'
                )
            prev_rank = rank

    return issues
