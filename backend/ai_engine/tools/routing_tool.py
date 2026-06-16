from typing import List
from app.external.osrm_client import get_duration, get_travel_time_matrix
from ai_engine.tools.haversine import haversine


# Stops closer than this threshold (km) are assumed walkable.
WALK_THRESHOLD_KM = 2.0

# Average walking speed in km/h — used as fallback estimation.
_WALK_SPEED_KMH = 5.0


async def get_travel_time_minutes(origin: dict, destination: dict) -> float:
    """
    Returns estimated travel time in minutes between two lat/lon points.

    Kept for backward compatibility — prefer compute_day_matrix() for
    batch computation.
    """
    return await get_duration(origin["lat"], origin["lon"], destination["lat"], destination["lon"])


async def compute_day_matrix(stops: List[dict]) -> list[list[float]]:
    """
    Compute the full NxN travel-time matrix for a day's stops using
    the OSRM Table API.

    For stop pairs closer than WALK_THRESHOLD_KM (2 km), a Haversine
    walking estimate is used.  For all other pairs, driving is used.  This
    produces a single NxN matrix with the best transport mode per pair.

    Args:
        stops: List of stop dicts with 'lat' and 'lon' keys.

    Returns:
        NxN matrix where matrix[i][j] is minutes from stop i to j.
    """
    n = len(stops)
    if n <= 1:
        return [[0.0]]

    # Precompute the Haversine distance between every pair so we can
    # decide which pairs are walkable without extra API calls.
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine(stops[i]["lat"], stops[i]["lon"],
                          stops[j]["lat"], stops[j]["lon"])
            dist[i][j] = d
            dist[j][i] = d

    # Split pairs into walkable vs driving.
    walk_indices = []   # (i, j) pairs that are walkable
    drive_indices = []  # (i, j) pairs that need driving
    for i in range(n):
        for j in range(i + 1, n):
            if dist[i][j] <= WALK_THRESHOLD_KM:
                walk_indices.append((i, j))
            else:
                drive_indices.append((i, j))

    # Start with a matrix of zeros.
    matrix = [[0.0] * n for _ in range(n)]

    # --- Walking pairs: use Haversine estimate (fast, no API call) ---
    for i, j in walk_indices:
        walk_min = round((dist[i][j] / _WALK_SPEED_KMH) * 60, 1)
        matrix[i][j] = walk_min
        matrix[j][i] = walk_min

    # --- Driving pairs: single OSRM Table API call ---
    if drive_indices:
        # Build sub-lists of only the stops that need driving.
        # Map sub-matrix indices back to original indices.
        drive_stop_indices = sorted(set(
            idx for pair in drive_indices for idx in pair
        ))
        sub_stops = [stops[i] for i in drive_stop_indices]
        sub_matrix = await get_travel_time_matrix(sub_stops, profile="driving")

        # Map sub-matrix results back into the full matrix.
        orig_to_sub = {orig: sub for sub, orig in enumerate(drive_stop_indices)}
        for i, j in drive_indices:
            si, sj = orig_to_sub[i], orig_to_sub[j]
            matrix[i][j] = sub_matrix[si][sj]
            matrix[j][i] = sub_matrix[sj][si]

    return matrix


def order_stops_by_proximity(stops: List[dict]) -> list[dict]:
    """
    Reorder stops using greedy nearest-neighbor on **Euclidean** distance.

    Kept as a fast fallback when no travel-time matrix is available.
    Prefer ``order_stops_by_matrix()`` when you have a precomputed matrix.
    """
    if not stops:
        return []

    unvisited = stops[:]
    ordered = [unvisited.pop(0)]

    while unvisited:
        current = ordered[-1]
        next_stop = min(unvisited, key=lambda x: (x["lat"] - current["lat"]) ** 2 + (x["lon"] - current["lon"]) ** 2)
        ordered.append(next_stop)
        unvisited.remove(next_stop)

    return ordered


def get_reorder_indices(
    stops: List[dict],
    matrix: list[list[float]],
) -> list[int]:
    """
    Return the index permutation produced by greedy nearest-neighbor on
    the travel-time matrix.

    ``result[i]`` is the original index of the stop that should be
    in position *i* of the reordered route.  Use this when you need
    to look up travel times from the original matrix after reordering.

    Args:
        stops:  Original list of stop dicts.
        matrix: NxN travel-time matrix (minutes) where matrix[i][j] is the
                time from stop i to stop j.

    Returns:
        List of original indices in reordered route order.
    """
    n = len(stops)
    if n <= 1:
        return list(range(n))

    remaining = set(range(1, n))
    order = [0]

    while remaining:
        current = order[-1]
        nearest = min(remaining, key=lambda j: matrix[current][j])
        order.append(nearest)
        remaining.remove(nearest)

    return order


def improve_order_2opt(
    order: list[int],
    matrix: list[list[float]],
    max_iterations: int = 100,
) -> list[int]:
    """
    Improve a route using 2-opt local search on the travel-time matrix.

    2-opt repeatedly tries reversing a segment of the route.  If
    reversing segment [i+1 .. j] reduces the total travel time, the
    reversal is kept.  The algorithm stops when no improving swap is
    found or *max_iterations* is reached.

    Args:
        order:           Current route as a list of original indices.
        matrix:          NxN travel-time matrix (minutes).
        max_iterations:  Safety cap to guarantee O(n²) worst-case.

    Returns:
        Improved route (list of original indices).
    """
    n = len(order)
    if n <= 3:
        return order

    best = list(order)

    improved = True
    iterations = 0

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1

        for i in range(1, n - 1):
            for j in range(i + 1, n):
                # Current edges:  (i-1 → i) and (j → j+1)
                # Swapped edges: (i-1 → j) and (i → j+1)
                # If j is the last stop, there is no (j → j+1) edge.
                if j + 1 < n:
                    old_cost = matrix[best[i - 1]][best[i]] + matrix[best[j]][best[j + 1]]
                    new_cost = matrix[best[i - 1]][best[j]] + matrix[best[i]][best[j + 1]]
                else:
                    old_cost = matrix[best[i - 1]][best[i]]
                    new_cost = matrix[best[i - 1]][best[j]]

                if new_cost < old_cost:
                    # Reverse the segment between i and j (inclusive).
                    best[i:j + 1] = reversed(best[i:j + 1])
                    improved = True

    return best


def order_stops_by_matrix(
    stops: List[dict],
    matrix: list[list[float]],
) -> list[dict]:
    """
    Reorder stops using greedy nearest-neighbor on **actual travel times**
    from a precomputed NxN matrix.

    Convenience wrapper — returns the reordered list of stop dicts.
    For index-level access (e.g. matrix remapping), use
    ``get_reorder_indices()`` instead.
    """
    return [stops[i] for i in get_reorder_indices(stops, matrix)]
