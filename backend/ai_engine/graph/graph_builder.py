# ai/graph/graph_builder.py

from langgraph.graph import StateGraph, END

from ai_engine.graph.state import TripState
from ai_engine.graph.nodes import (
    load_profile_node,
    retrieval_node,
    ranking_node,
    planning_node,
    optimization_node,
    validation_node,
)
from ai_engine.graph.edges import (
    should_rank,
    should_plan,
    should_optimize,
    should_validate,
    should_retry_or_end,
)


def build_trip_graph():
    """
    Assembles the full pipeline graph for itinerary generation.

    Pipeline:
      load_profile → retrieval → scorer → planner → optimizer → validator

    Each node handles one concern:
      - load_profile: Load trip profile from DB
      - retrieval:    Filter places using SQL-style criteria (PlaceRetriever)
      - scorer:       Score candidates with multi-signal formula + diversity (CandidateScorer)
      - planner:      LLM generates the day-by-day itinerary
      - optimizer:    Reorder stops by travel time via OSRM + 2-opt (RouteOptimizer)
      - validator:    Programmatic feasibility + LLM quality checks (ItineraryValidator)

    Intent parsing and routing (plan_trip vs general_chat vs
    needs_clarification)    is handled by orchestrator.py before
    the graph is invoked.

    Returns a compiled graph object that FastAPI will call.
    """
    graph = StateGraph(TripState)

    # ── Add all agent nodes ───────────────────────────────────────
    graph.add_node("load_profile",  load_profile_node)
    graph.add_node("retrieval",     retrieval_node)
    graph.add_node("ranking",       ranking_node)
    graph.add_node("planner",       planning_node)
    graph.add_node("optimizer",     optimization_node)
    graph.add_node("validator",     validation_node)

    # ── Entry point ───────────────────────────────────────────────
    graph.set_entry_point("load_profile")

    # ── Fixed edges (always follow this path) ─────────────────────
    graph.add_edge("load_profile", "retrieval")

    # ── Conditional edges (routing based on agent output) ─────────
    graph.add_conditional_edges(
        "retrieval",
        should_rank,
        {
            "ranking": "ranking",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "ranking",
        should_plan,
        {
            "planner": "planner",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "planner",
        should_optimize,
        {
            "optimizer": "optimizer",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "optimizer",
        should_validate,
        {
            "validator": "validator",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "validator",
        should_retry_or_end,
        {
            "planner": "planner",
            "end": END,
        },
    )

    # ── Compile ───────────────────────────────────────────────────
    compiled_graph = graph.compile()
    return compiled_graph


# Build the graph once when this module is imported
trip_graph = build_trip_graph()