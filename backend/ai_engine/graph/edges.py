# ai/graph/edges.py

from ai_engine.graph.state import TripState

def should_optimize(state: TripState) -> str:
    """
    Called after the Planner node finishes.
    
    Decides: did planning succeed? If yes, go to Optimizer.
    If something went wrong, go to END.
    
    This is a 'conditional edge' — LangGraph calls this function
    and uses the return value (a string) to pick the next node.
    
    In Sprint 1: always returns "optimizer" (no failure cases yet).
    In later sprints: will return "end" if Planner couldn't find places.
    """
    if state.get("error"):
        return "end"
    return "optimizer"


def should_validate(state: TripState) -> str:
    """
    Called after the Optimizer node finishes.
    
    Decides: did optimization succeed? If yes, go to Validator.
    
    In Sprint 1: always returns "validator".
    In later sprints: will return "end" if OSRM call failed.
    """
    if state.get("error"):
        return "end"
    return "validator"


def should_retry_or_end(state: TripState) -> str:
    """
    Called after the Validator node finishes.

    Decides: is the itinerary valid?
    - If valid → end the pipeline successfully.
    - If invalid and an error exists → end with the error.
    - If invalid but no error → retry planning (sends back to planner).

    Sprint 2: retry logic is wired but planner is still a placeholder,
    so retries will immediately pass validation again. Real retry behaviour
    activates when the planner generates real itineraries in Sprint 4.
    """
    if state.get("is_valid"):
        return "end"
    if state.get("error"):
        return "end"
    # Itinerary was generated but failed validation — retry
    return "planner"