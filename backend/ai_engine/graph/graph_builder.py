# ai/graph/graph_builder.py

from langgraph.graph import StateGraph, END

from ai_engine.graph.state import TripState
from ai_engine.graph.nodes import (
    planning_node, optimization_node, validation_node,
    load_profile_node, intent_parser_node
)
from ai_engine.graph.edges import should_optimize, should_validate, should_retry_or_end


def route_after_intent(state: TripState) -> str:
    """Routes after intent parsing based on intent_type."""
    return state.get("intent_type", "general_chat")


def build_trip_graph():
    """
    This function assembles the full agent graph.
    
    Think of it like drawing the flowchart:
      1. Create a blank canvas (StateGraph)
      2. Add each agent as a box on the canvas (add_node)
      3. Draw arrows between the boxes (add_edge / add_conditional_edges)
      4. Mark the starting box (set_entry_point)
      5. Compile it so LangGraph can execute it (compile)
    
    Returns a compiled graph object that FastAPI will call.
    """
    
    graph = StateGraph(TripState)

    # Add the new entry node
    graph.add_node("intent_parser", intent_parser_node)   # ← new
    graph.add_node("load_profile",  load_profile_node)
    graph.add_node("planner",       planning_node)
    graph.add_node("optimizer",     optimization_node)
    graph.add_node("validator",     validation_node)

    # New entry point
    graph.set_entry_point("intent_parser")

    # Route based on intent
    graph.add_conditional_edges(
        "intent_parser",
        route_after_intent,
        {
            "plan_trip":           "load_profile",   # full pipeline
            "needs_clarification": END,              # Task 3.7 will handle this
            "general_chat":        END,              # direct reply, no pipeline
        }
    )

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