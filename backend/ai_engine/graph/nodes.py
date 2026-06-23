from ai_engine.graph.state import TripState
from ai_engine.graph.progress import report_progress
from ai_engine.tools.profile_tool import load_trip_profile, load_mock_profile
from ai_engine.agents.retrieval_agent import run_retrieval_agent
from ai_engine.agents.ranking_agent import run_ranking_agent
from ai_engine.agents.planning_agent import run_planning_agent
from ai_engine.agents.optimization_agent import run_optimization_agent
from ai_engine.agents.validation_agent import run_validation_agent
from ai_engine.observability import traced


# ── Helpers ─────────────────────────────────────────────────────────────────


def _progress_key(state: TripState) -> str | None:
    """Extract the progress queue key from state, or None."""
    return state.get("progress_queue_key")



@traced(name="load_profile", tags=["agent", "profile"])
async def load_profile_node(state: TripState) -> TripState:
    """
    ENTRY NODE — Loads the per-trip profile into TripState.
    """
    pk = _progress_key(state)
    if pk:
        await report_progress(pk, "LoadProfile", "running", "Loading your travel profile...")

    if state.get("profile"):
        print("[LoadProfile] Profile already loaded")
        if pk:
            await report_progress(pk, "LoadProfile", "done", "Profile already loaded")
        return state

    user_id = state.get("user_id", "mock_user_001")
    token = state.get("token")
    trip_id = state.get("trip_id") or user_id
    print(f"[LoadProfile] Loading profile for trip: {trip_id}")

    if token:
        try:
            profile = await load_trip_profile(trip_id=trip_id, token=token)
            print("[LoadProfile] Real profile loaded")
            if pk:
                await report_progress(pk, "LoadProfile", "done", "Profile loaded from your account")
        except Exception as e:
            print(f"[LoadProfile] Failed to load real profile ({e}), falling back to mock")
            profile = load_mock_profile(trip_id=trip_id)
            if pk:
                await report_progress(pk, "LoadProfile", "done", "Using default travel preferences")
    else:
        print("[LoadProfile] No token provided, using mock profile")
        profile = load_mock_profile(trip_id=trip_id)
        if pk:
            await report_progress(pk, "LoadProfile", "done", "Using default travel preferences")

    state["profile"] = profile
    return state


@traced(name="retrieval_agent", tags=["agent", "retrieval"], metadata={"role": "retrieval"})
async def retrieval_node(state: TripState) -> TripState:
    """
    RETRIEVAL AGENT NODE — Filters places from the database using
    structured preference criteria.
    """
    city = state.get('destination_city', '?')
    pk = _progress_key(state)
    if pk:
        await report_progress(pk, "RetrievalAgent", "running", f"Searching for places in {city}...")

    print(f"[RetrievalAgent] Filtering places for: {city}")
    result = await run_retrieval_agent(state)

    filtered = result.get("filtered_places") or []
    if pk:
        await report_progress(pk, "RetrievalAgent", "done", f"Found {len(filtered)} places to explore")
    return result


@traced(name="ranking_agent", tags=["agent", "ranking"], metadata={"role": "ranking"})
async def ranking_node(state: TripState) -> TripState:
    """
    RANKING AGENT NODE — Scores candidates with multi-signal ranking
    and diversity optimization.
    """
    filtered = state.get("filtered_places") or []
    pk = _progress_key(state)
    if pk:
        await report_progress(pk, "RankingAgent", "running",
                              f"Ranking {len(filtered)} places by relevance...")

    print(f"[RankingAgent] Ranking {len(filtered)} filtered places")
    result = await run_ranking_agent(state)

    candidates = result.get("candidate_places") or []
    if pk:
        await report_progress(pk, "RankingAgent", "done",
                              f"Selected top {len(candidates)} places for your itinerary")
    return result


@traced(name="planning_agent", tags=["agent", "planner"], metadata={"role": "planner"})
async def planning_node(state: TripState) -> TripState:
    """
    PLANNING AGENT NODE — Generates the itinerary using the LLM,
    consuming pre-ranked candidates from upstream agents.
    """
    candidates = state.get("candidate_places") or []
    pk = _progress_key(state)
    if pk:
        await report_progress(pk, "Planner", "running",
                              f"Building your {state.get('duration_days', '?')}-day itinerary...")

    print(f"[Planner] Planning with {len(candidates)} candidates")
    result = await run_planning_agent(state)

    draft = result.get("draft_itinerary") or {}
    days = len(draft.get("days", []))
    total_stops = sum(len(d.get("stops", [])) for d in draft.get("days", []))
    if pk:
        if result.get("error"):
            await report_progress(pk, "Planner", "error",
                                  "Could not create itinerary, retrying...")
        else:
            await report_progress(pk, "Planner", "done",
                                  f"Created {days} days with {total_stops} stops")
    return result


@traced(name="optimization_agent", tags=["agent", "optimizer"], metadata={"role": "optimizer"})
async def optimization_node(state: TripState) -> TripState:
    """
    OPTIMIZER AGENT NODE — Reorders stops by travel time.
    """
    draft = state.get("draft_itinerary")
    days = len(draft.get("days", [])) if draft else 0
    total_stops = sum(len(d.get("stops", [])) for d in (draft or {}).get("days", []))

    pk = _progress_key(state)
    if pk:
        await report_progress(pk, "Optimizer", "running",
                              f"Optimizing route for {total_stops} stops across {days} days...")

    print(f"[Optimizer] Optimizing {days} days, {total_stops} stops...")
    result = await run_optimization_agent(state)

    if pk:
        opt = result.get("optimized_itinerary") or {}
        travel_time = sum(
            d.get("total_travel_time_minutes", 0) for d in opt.get("days", [])
        )
        await report_progress(pk, "Optimizer", "done",
                              f"Route optimized — {travel_time:.0f} min total travel time")
    return result


@traced(name="validation_agent", tags=["agent", "validator"], metadata={"role": "validator"})
async def validation_node(state: TripState) -> TripState:
    """
    VALIDATION AGENT NODE — Programmatic + LLM validation.
    """
    opt = state.get("optimized_itinerary")
    days = len(opt.get("days", [])) if opt else 0

    pk = _progress_key(state)
    if pk:
        await report_progress(pk, "Validator", "running", "Reviewing itinerary quality...")

    print(f"[Validator] Validating {days}-day itinerary...")
    result = await run_validation_agent(state)

    if pk:
        is_valid = result.get("is_valid")
        if is_valid:
            await report_progress(pk, "Validator", "done",
                                  "Itinerary passed quality checks! ✅")
        else:
            val = result.get("validation", {})
            score = val.get("score", "?")
            issues = len(val.get("issues", []))
            if result.get("planning_attempts", 1) < 2:
                await report_progress(pk, "Validator", "running",
                                      f"Score {score}/100 — improving quality...")
            else:
                await report_progress(pk, "Validator", "done",
                                      f"Final quality score: {score}/100 ({issues} notes)")
    return result