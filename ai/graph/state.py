# ai/graph/state.py


""""
TypedDict (from typing) is a way to define dictionary-like objects where keys and their types are known ahead of time.
Optional (from typing) means that a field can be of a certain type or it can be None.
"""
from typing import TypedDict, Optional

class TripState(TypedDict):
    """
    This is the shared state object passed between all agents.
    Think of it as the baton in a relay race — every agent
    picks it up, adds something, and passes it on.
    
    In Sprint 1 we only define the fields we need for the skeleton.
    We'll add more fields (itinerary, profile, etc.) in later sprints.
    """
    
    # Who is making this request?
    user_id: str
    

    # What did the user type? (e.g. "Plan me a 2-day trip to Cairo")
    user_message: str
    

    # Which agent should run next?
    # LangGraph reads this to decide routing
    next_agent: Optional[str]
    
   
    # This is the preliminary trip plan created by the Planner agent.
    # Type: dict or None initially.
    # Example (after Planner fills it):
    # {
    #     "day_1": ["Museum of Cairo", "Lunch at local cafe"],
    #     "day_2": ["Pyramids", "Dinner cruise"]
    # }
    draft_itinerary: Optional[dict]

   
    # This will hold the final, optimized itinerary after processing by the Optimizer agent.
    # Type: dict or None.
    # The Optimizer could reorder activities for efficiency or balance.
    optimized_itinerary: Optional[dict]

    
    # Is the plan valid? — empty for now, Validator will fill this
    is_valid: Optional[bool]
    

    # Used to store any error messages encountered by agents.
    # Type: str or None.
    # Example: "No flights found for the selected dates".
    error: Optional[str]