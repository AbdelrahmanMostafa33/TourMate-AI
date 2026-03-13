# ai/main.py

from graph.graph_builder import trip_graph

def test_skeleton():
    """
    A simple test to verify the LangGraph skeleton works.
    
    We create a minimal initial state and invoke the graph.
    In Sprint 1, no real AI happens — we just confirm:
      1. The graph compiles without errors
      2. Each node runs in the correct order (Planner → Optimizer → Validator)
      3. The state is passed correctly between nodes
    """
    
    # Create the initial state — just the minimum required fields
    initial_state = {
        "user_id": "test_user_001",
        "user_message": "Plan me a 2-day trip to Cairo",
        "next_agent": None,
        "draft_itinerary": None,
        "optimized_itinerary": None,
        "is_valid": None,
        "error": None
    }
    
    print("=== Starting TourMate AI graph skeleton test ===\n")
    
    # Invoke the graph — this runs all nodes in sequence
    final_state = trip_graph.invoke(initial_state)
    
    print("\n=== Final state after all agents ran ===")
    print(f"Draft itinerary:     {final_state['draft_itinerary']}")
    print(f"Optimized itinerary: {final_state['optimized_itinerary']}")
    print(f"Is valid:            {final_state['is_valid']}")
    print("\n=== Task 1.8 complete — skeleton works ===")


if __name__ == "__main__":
    test_skeleton()