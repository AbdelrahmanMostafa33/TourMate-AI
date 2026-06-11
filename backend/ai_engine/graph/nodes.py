from ai_engine.graph.state import TripState
from ai_engine.tools.profile_tool import load_behavioral_profile, load_mock_profile


# (state: TripState) -> parameter state with type hint TripState (our shared dictionary type).
# -> TripState -> return type hint, telling Python (and developers) that this function returns a TripState object.
# This function takes the shared trip state, adds/updates the draft itinerary, and returns the updated state.
async def planning_node(state: TripState) -> TripState:
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


async def optimization_node(state: TripState) -> TripState:
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


async def validation_node(state: TripState) -> TripState:
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


async def load_profile_node(state: TripState) -> TripState:
    """
    ENTRY NODE — Loads the user's behavioral profile into TripState.

    If the profile is already set in state (e.g. pre-loaded by chat_handler
    with auth credentials), this node is a no-op. Otherwise, it loads the
    real profile via HTTP when a token is available, falling back to the
    mock profile for development/testing.

    Runs before the planner so every downstream agent has access to
    the profile via state["profile"].
    """
    # Skip if profile was already loaded by the caller (e.g. chat_handler)
    if state.get("profile"):
        print(f"[LoadProfile] Profile already loaded: "
              f"{state['profile'].get('persona_name', 'unknown persona')}")
        return state

    user_id = state.get("user_id", "mock_user_001")
    token = state.get("token")
    print(f"[LoadProfile] Loading profile for user: {user_id}")

    if token:
        try:
            profile = await load_behavioral_profile(user_id=user_id, token=token)
            print(f"[LoadProfile] Real profile loaded: "
                  f"{profile.get('persona_name', 'unknown persona')}")
        except Exception as e:
            print(f"[LoadProfile] Failed to load real profile ({e}), "
                  f"falling back to mock")
            profile = load_mock_profile(user_id=user_id)
    else:
        print(f"[LoadProfile] No token provided, using mock profile")
        profile = load_mock_profile(user_id=user_id)

    state["profile"] = profile
    return state