# ai/graph/edges.py

from ai_engine.graph.state import TripState


def should_rank(state: TripState) -> str:
    """
    Called after the Place Retriever finishes.
    If filtering found places, proceed to scoring.
    """
    if state.get("error"):
        return "end"
    filtered = state.get("filtered_places") or []
    if not filtered:
        return "end"
    return "ranking"


def should_plan(state: TripState) -> str:
    """
    Called after the Candidate Scorer finishes.
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
    Called after the Route Optimizer node finishes.
    Did optimization succeed? If yes, go to Validator.
    """
    if state.get("error"):
        return "end"
    return "validator"


# Maximum number of full pipeline retry cycles (planner → optimizer → validator).
# Prevents infinite loops when the validator keeps rejecting output.
_MAX_PLANNING_RETRIES = 3


def should_retry_or_end(state: TripState) -> str:
    """
    Called after the Itinerary Validator node finishes.
    - If valid → end the pipeline successfully.
    - If invalid and an error exists → end with the error.
    - If invalid but no error and retries remain → retry from planner.
    - If invalid and retries exhausted → set error and end.
    """
    if state.get("is_valid"):
        return "end"
    if state.get("error"):
        return "end"

    # Check retry cap so we don't loop forever
    attempts = state.get("planning_attempts", 0)
    if attempts >= _MAX_PLANNING_RETRIES:
        state["error"] = (
            f"Pipeline failed after {attempts} planning attempts — "
            f"itinerary could not pass quality validation"
        )
        return "end"

    # Itinerary was generated but failed validation — retry from planner
    return "planner"