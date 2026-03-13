# ai/graph/edges.py

from graph.state import TripState

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