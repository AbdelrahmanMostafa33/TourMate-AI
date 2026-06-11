# ai/graph/graph_builder.py

from langgraph.graph import StateGraph, END

from ai_engine.graph.state import TripState
from ai_engine.graph.nodes import (
    planning_node, optimization_node, validation_node,
    load_profile_node,
)
from ai_engine.graph.edges import should_optimize, should_validate, should_retry_or_end


def build_trip_graph():
    """
    This function assembles the full agent graph.
    
    The graph handles only the plan_trip pipeline:
      load_profile → planner → optimizer → validator
    
    Intent parsing and routing (plan_trip vs general_chat vs
    needs_clarification) is handled by chat_handler.py before
    the graph is invoked, so the graph doesn't need its own
    intent parser node.
    
    Returns a compiled graph object that FastAPI will call.
    """
    
    graph = StateGraph(TripState)

    # Add nodes
    graph.add_node("load_profile",  load_profile_node)
    graph.add_node("planner",       planning_node)
    graph.add_node("optimizer",     optimization_node)
    graph.add_node("validator",     validation_node)

    # Entry point — profile is loaded first so downstream agents
    # can personalize the itinerary
    graph.set_entry_point("load_profile")

    # Fixed edge: after profile loads, always go to planner
    graph.add_edge("load_profile", "planner")
    
    # Step D: Add conditional edges (arrows with decision logic)
    # "After planner runs, call should_optimize() to decide next node"
    graph.add_conditional_edges(
        "planner",          # from this node
        should_optimize,    # call this function to decide
        {
            "optimizer": "optimizer",   # if function returns "optimizer" → go there
            "end": END                  # if function returns "end" → stop
        }
    )
    
    # "After optimizer runs, call should_validate() to decide next node"
    graph.add_conditional_edges(
        "optimizer",
        should_validate,
        {
            "validator": "validator",
            "end": END
        }
    )
    
    # Conditional edge: after validator, retry or end based on is_valid
    graph.add_conditional_edges(
        "validator",
        should_retry_or_end,
        {
            "planner": "planner",
            "end": END
        }
    )
    
    # Step E: Compile — this validates your graph and makes it runnable
    compiled_graph = graph.compile()
    
    return compiled_graph


# Build the graph once when this module is imported
# FastAPI will import this and call it directly
trip_graph = build_trip_graph()