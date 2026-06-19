# ai/graph/edges.py

from ai_engine.graph.state import TripState


def should_retrieve(state: TripState) -> str:
    """
    Called after the Preference Agent finishes.
    If extraction succeeded, proceed to retrieval.
    """
    if state.get("error"):
        return "end"
    return "retrieval"


def should_rank(state: TripState) -> str:
    """
    Called after the Retrieval Agent finishes.
    If filtering found places, proceed to ranking.
    """
    if state.get("error"):
        return "end"
    filtered = state.get("filtered_places") or []
    if not filtered:
        return "end"
    return "ranking"


def should_plan(state: TripState) -> str:
    """
    Called after the Ranking Agent finishes.
    If candidates exist, proceed to planning.
    """
    if state.get("error"):
        return "end"
    candidates = state.get("candidate_places") or []
    if not candidates:
        return "end"
    return "planner"


def should_optimize(state: TripState) -> str:
    """
    Called after the Planner node finishes.
    Did planning succeed? If yes, go to Optimizer.
    """
    if state.get("error"):
        return "end"
    return "optimizer"


def should_validate(state: TripState) -> str:
    """
    Called after the Optimizer node finishes.
    Did optimization succeed? If yes, go to Validator.
    """
    if state.get("error"):
        return "end"
    return "validator"


def should_retry_or_end(state: TripState) -> str:
    """
    Called after the Validator node finishes.
    - If valid → end the pipeline successfully.
    - If invalid and an error exists → end with the error.
    - If invalid but no error → retry planning (sends back to planner).
    """
    if state.get("is_valid"):
        return "end"
    if state.get("error"):
        return "end"
    # Itinerary was generated but failed validation — retry from planner
    return "planner"