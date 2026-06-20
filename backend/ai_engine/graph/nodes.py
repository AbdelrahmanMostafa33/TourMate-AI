from ai_engine.graph.state import TripState
from ai_engine.tools.profile_tool import load_trip_profile, load_mock_profile
from ai_engine.agents.preference_agent import run_preference_agent
from ai_engine.agents.retrieval_agent import run_retrieval_agent
from ai_engine.agents.ranking_agent import run_ranking_agent
from ai_engine.agents.planning_agent import run_planning_agent
from ai_engine.agents.optimization_agent import run_optimization_agent
from ai_engine.agents.validation_agent import run_validation_agent
from ai_engine.observability import traced


@traced(name="load_profile", tags=["agent", "profile"])
async def load_profile_node(state: TripState) -> TripState:
    """
    ENTRY NODE — Loads the per-trip profile into TripState.
    """
    if state.get("profile"):
        print(f"[LoadProfile] Profile already loaded (confidence={state['profile'].get('confidence', '?')})")
        return state

    user_id = state.get("user_id", "mock_user_001")
    token = state.get("token")
    trip_id = state.get("trip_id") or user_id
    print(f"[LoadProfile] Loading profile for trip: {trip_id}")

    if token:
        try:
            profile = await load_trip_profile(trip_id=trip_id, token=token)
            print(f"[LoadProfile] Real profile loaded (confidence={profile.get('confidence', '?')})")
        except Exception as e:
            print(f"[LoadProfile] Failed to load real profile ({e}), falling back to mock")
            profile = load_mock_profile(trip_id=trip_id)
    else:
        print("[LoadProfile] No token provided, using mock profile")
        profile = load_mock_profile(trip_id=trip_id)

    state["profile"] = profile
    return state


@traced(name="preference_agent", tags=["agent", "preference"], metadata={"role": "preference"})
async def preference_node(state: TripState) -> TripState:
    """
    PREFERENCE AGENT NODE — Extracts structured preferences from
    the user's message and behavioral profile.
    """
    ctx = (state.get("conversation_context") or state.get("user_message", ""))[:80]
    print(f"[PreferenceAgent] Refining profile (context: {ctx}...)")
    return await run_preference_agent(state)


@traced(name="retrieval_agent", tags=["agent", "retrieval"], metadata={"role": "retrieval"})
async def retrieval_node(state: TripState) -> TripState:
    """
    RETRIEVAL AGENT NODE — Filters places from the database using
    structured preference criteria.
    """
    print(f"[RetrievalAgent] Filtering places for: {state.get('destination_city', '?')}")
    return await run_retrieval_agent(state)


@traced(name="ranking_agent", tags=["agent", "ranking"], metadata={"role": "ranking"})
async def ranking_node(state: TripState) -> TripState:
    """
    RANKING AGENT NODE — Scores candidates with multi-signal ranking
    and diversity optimization.
    """
    filtered = state.get("filtered_places") or []
    print(f"[RankingAgent] Ranking {len(filtered)} filtered places")
    return await run_ranking_agent(state)


@traced(name="planning_agent", tags=["agent", "planner"], metadata={"role": "planner"})
async def planning_node(state: TripState) -> TripState:
    """
    PLANNING AGENT NODE — Generates the itinerary using the LLM,
    consuming pre-ranked candidates from upstream agents.
    """
    candidates = state.get("candidate_places") or []
    print(f"[Planner] Planning with {len(candidates)} candidates")
    return await run_planning_agent(state)


@traced(name="optimization_agent", tags=["agent", "optimizer"], metadata={"role": "optimizer"})
async def optimization_node(state: TripState) -> TripState:
    """
    OPTIMIZER AGENT NODE — Reorders stops by travel time.
    """
    draft = state.get("draft_itinerary")
    days = len(draft.get("days", [])) if draft else 0
    total_stops = sum(len(d.get("stops", [])) for d in (draft or {}).get("days", []))
    print(f"[Optimizer] Optimizing {days} days, {total_stops} stops...")
    return await run_optimization_agent(state)


@traced(name="validation_agent", tags=["agent", "validator"], metadata={"role": "validator"})
async def validation_node(state: TripState) -> TripState:
    """
    VALIDATION AGENT NODE — Programmatic + LLM validation.
    """
    opt = state.get("optimized_itinerary")
    days = len(opt.get("days", [])) if opt else 0
    print(f"[Validator] Validating {days}-day itinerary...")
    return await run_validation_agent(state)