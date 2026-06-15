from ai_engine.graph.state import TripState
from ai_engine.tools.profile_tool import load_behavioral_profile, load_mock_profile
from ai_engine.agents.planning_agent import run_planning_agent
from ai_engine.agents.optimization_agent import run_optimization_agent
from ai_engine.agents.validation_agent import run_validation_agent

async def planning_node(state: TripState) -> TripState:
    """
    THE PLANNER AGENT NODE
    """
    print(f"[Planner] Running for message: {state['user_message']}")
    return await run_planning_agent(state)


async def optimization_node(state: TripState) -> TripState:
    """
    THE OPTIMIZER AGENT NODE
    """
    print(f"[Optimizer] Running optimization...")
    return await run_optimization_agent(state)


async def validation_node(state: TripState) -> TripState:
    """
    THE VALIDATION AGENT NODE
    """
    print(f"[Validator] Running validation...")
    return await run_validation_agent(state)


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