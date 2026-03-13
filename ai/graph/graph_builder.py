# ai/graph/graph_builder.py

from langgraph.graph import StateGraph, END

from graph.state import TripState
from graph.nodes import planning_node, optimization_node, validation_node
from graph.edges import should_optimize, should_validate


def build_graph():
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
    
    # Step A: Create the blank graph, tell it what state shape to use
    graph = StateGraph(TripState)
    
    # Step B: Add each agent node to the graph
    # First argument = the name you'll use in edges
    # Second argument = the actual Python function to call
    graph.add_node("planner", planning_node)
    graph.add_node("optimizer", optimization_node)
    graph.add_node("validator", validation_node)
    
    # Step C: Set the entry point — which agent runs FIRST?
    graph.set_entry_point("planner")
    
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
    
    # Simple fixed edge: after validator always go to END
    graph.add_edge("validator", END)
    
    # Step E: Compile — this validates your graph and makes it runnable
    compiled_graph = graph.compile()
    
    return compiled_graph


# Build the graph once when this module is imported
# FastAPI will import this and call it directly
trip_graph = build_graph()