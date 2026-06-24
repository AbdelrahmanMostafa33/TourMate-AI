from ai_engine.graph.state import TripState
from ai_engine.graph.progress import report_progress
from ai_engine.tools.profile_tool import load_trip_profile, load_mock_profile
from ai_engine.services.place_retriever import retrieve_places
from ai_engine.services.candidate_scorer import score_candidates
from ai_engine.agents.planning_agent import run_planning_agent
from ai_engine.services.route_optimizer import optimize_route
from ai_engine.services.itinerary_validator import validate_itinerary
from ai_engine.observability import traced
from ai_engine.evaluation.agent_metrics import agent_metrics


# ── Helpers ─────────────────────────────────────────────────────────────────


def _progress_key(state: TripState) -> str | None:
    """Extract the progress queue key from state, or None."""
    return state.get("progress_queue_key")



@traced(name="load_profile", tags=["agent", "profile"])
async def load_profile_node(state: TripState) -> TripState:
    """
    ENTRY NODE — Loads the per-trip profile into TripState.
    """
    async with agent_metrics.track_async("profile_loader"):
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


@traced(name="retrieval", tags=["agent", "retrieval"], metadata={"role": "retrieval"})
async def retrieval_node(state: TripState) -> TripState:
    """
    RETRIEVAL NODE — Filters places from the database using
    structured preference criteria.
    """
    async with agent_metrics.track_async("place_retriever"):
        city = state.get('destination_city', '?')
        pk = _progress_key(state)
        if pk:
            await report_progress(pk, "PlaceRetriever", "running", f"Searching for places in {city}...")

        print(f"[PlaceRetriever] Filtering places for: {city}")
        result = await retrieve_places(state)

        filtered = result.get("filtered_places") or []
        if pk:
            await report_progress(pk, "PlaceRetriever", "done", f"Found {len(filtered)} places to explore")
        return result


@traced(name="ranking", tags=["agent", "ranking"], metadata={"role": "ranking"})
async def ranking_node(state: TripState) -> TripState:
    """
    CANDIDATE SCORER NODE — Scores candidates with multi-signal scoring
    and diversity optimization.
    """
    async with agent_metrics.track_async("candidate_scorer"):
        filtered = state.get("filtered_places") or []
        pk = _progress_key(state)
        if pk:
            await report_progress(pk, "CandidateScorer", "running",
                                  f"Scoring {len(filtered)} places by relevance...")

        print(f"[CandidateScorer] Scoring {len(filtered)} filtered places")
        result = await score_candidates(state)

        candidates = result.get("candidate_places") or []
        if pk:
            await report_progress(pk, "CandidateScorer", "done",
                                  f"Selected top {len(candidates)} places for your itinerary")
        return result


@traced(name="planning_agent", tags=["agent", "planner"], metadata={"role": "planner"})
async def planning_node(state: TripState) -> TripState:
    """
    PLANNING AGENT NODE — Generates the itinerary using the LLM,
    consuming pre-ranked candidates from upstream services.
    """
    async with agent_metrics.track_async("planner"):
        candidates = state.get("candidate_places") or []
        pk = _progress_key(state)
        if pk:
            await report_progress(pk, "Planner", "running",
                                  f"Building your {state.get('duration_days', '?')}-day itinerary...")

        print(f"[Planner] Planning with {len(candidates)} candidates")

        # Build a progress callback so invoke_with_fallback can report
        # intermediate rate-limit retries to the Flutter UI.
        async def _planner_retry_cb(attempt, max_retries, reason):
            if pk:
                await report_progress(pk, "Planner", "running",
                    f"{reason} ({attempt}/{max_retries})")

        result = await run_planning_agent(state, on_retry=_planner_retry_cb)

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


@traced(name="optimization", tags=["agent", "optimizer"], metadata={"role": "optimizer"})
async def optimization_node(state: TripState) -> TripState:
    """
    ROUTE OPTIMIZER NODE — Reorders stops by travel time.
    """
    async with agent_metrics.track_async("route_optimizer"):
        draft = state.get("draft_itinerary")
        days = len(draft.get("days", [])) if draft else 0
        total_stops = sum(len(d.get("stops", [])) for d in (draft or {}).get("days", []))

        pk = _progress_key(state)
        if pk:
            await report_progress(pk, "RouteOptimizer", "running",
                                  f"Optimizing route for {total_stops} stops across {days} days...")

        print(f"[RouteOptimizer] Optimizing {days} days, {total_stops} stops...")
        result = await optimize_route(state)

        if pk:
            opt = result.get("optimized_itinerary") or {}
            travel_time = sum(
                d.get("total_travel_time_minutes", 0) for d in opt.get("days", [])
            )
            await report_progress(pk, "RouteOptimizer", "done",
                                  f"Route optimized — {travel_time:.0f} min total travel time")
        return result


@traced(name="validation", tags=["agent", "validator"], metadata={"role": "validator"})
async def validation_node(state: TripState) -> TripState:
    """
    ITINERARY VALIDATOR NODE — Programmatic + LLM validation.
    """
    async with agent_metrics.track_async("itinerary_validator"):
        opt = state.get("optimized_itinerary")
        days = len(opt.get("days", [])) if opt else 0

        pk = _progress_key(state)
        if pk:
            await report_progress(pk, "ItineraryValidator", "running", "Reviewing itinerary quality...")

        print(f"[ItineraryValidator] Validating {days}-day itinerary...")

        # Build a progress callback for LLM retry reporting
        async def _validator_retry_cb(attempt, max_retries, reason):
            if pk:
                await report_progress(pk, "ItineraryValidator", "running",
                    f"{reason} ({attempt}/{max_retries})")

        result = await validate_itinerary(state, on_retry=_validator_retry_cb)

        if pk:
            is_valid = result.get("is_valid")
            if is_valid:
                await report_progress(pk, "ItineraryValidator", "done",
                                      "Itinerary passed quality checks! ✅")
            else:
                val = result.get("validation", {})
                score = val.get("score", "?")
                issues = len(val.get("issues", []))
                if result.get("planning_attempts", 1) < 2:
                    await report_progress(pk, "ItineraryValidator", "running",
                                          f"Score {score}/100 — improving quality...")
                else:
                    await report_progress(pk, "ItineraryValidator", "done",
                                          f"Final quality score: {score}/100 ({issues} notes)")
        return result