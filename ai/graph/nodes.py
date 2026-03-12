# ai/graph/nodes.py

from graph.state import TripState



# (state: TripState) → parameter state with type hint TripState (our shared dictionary type).
# -> TripState → return type hint, telling Python (and developers) that this function returns a TripState object.
# This function takes the shared trip state, adds/updates the draft itinerary, and returns the updated state.
def planning_node(state: TripState) -> TripState:
    """
    THE PLANNER AGENT NODE
    
    What it will eventually do (Sprint 4):
      - Call Gemini LLM with the user's message and profile
      - Call Overpass API to get real places in the destination
      - Generate a full day-by-day itinerary
    
    What it does RIGHT NOW (Sprint 1 skeleton):
      - Just proves it receives the state correctly
      - Puts a placeholder in draft_itinerary
      - Passes state to the next agent
    """

    # When the function runs, it logs:
    # [Planner] Received message: Plan me a 2-day trip to Cairo
    print(f"[Planner] Received message: {state['user_message']}")
    
    # PLACEHOLDER — real logic comes in Sprint 4
    # So in your structure: draft_itinerary is a dictionary (it describes one trip), 
    # and days inside it is a list (it holds multiple day objects), 
    # and each day is a dictionary (it describes one day), and stops inside each day is a list (multiple stops). 
    # They alternate — and that's completely normal and correct.
    state["draft_itinerary"] = {
        "status": "placeholder — planner ran successfully",
        "days": [] 
        
    }
    
    return state # return the updated state to be passed to the next agent in the graph


def optimization_node(state: TripState) -> TripState:
    """
    THE OPTIMIZER AGENT NODE
    
    What it will eventually do (Sprint 4):
      - Call OSRM to get travel times between stops
      - Reorder stops geographically
      - Check daily pacing (not too many stops in one day)
      - Return a fully optimized itinerary
    
    What it does RIGHT NOW (Sprint 1 skeleton):
      - Reads the draft from the Planner
      - Puts a placeholder in optimized_itinerary
    """
    print(f"[Optimizer] Received draft: {state.get('draft_itinerary')}")
    
    # PLACEHOLDER — real logic comes in Sprint 4
    state["optimized_itinerary"] = {
        "status": "placeholder — optimizer ran successfully",
        "days": []
    }
    
    return state


def validation_node(state: TripState) -> TripState:
    """
    THE VALIDATION AGENT NODE
    
    What it will eventually do (Sprint 4):
      - Check that every stop has valid opening hours
      - Check that travel times between stops are realistic
      - Flag any infeasible days
      - Set is_valid = True or False
    
    What it does RIGHT NOW (Sprint 1 skeleton):
      - Reads the optimized itinerary
      - Sets is_valid = True as a placeholder
    """
    print(f"[Validator] Received optimized plan: {state.get('optimized_itinerary')}")
    
    # PLACEHOLDER — real logic comes in Sprint 4
    state["is_valid"] = True
    
    return state