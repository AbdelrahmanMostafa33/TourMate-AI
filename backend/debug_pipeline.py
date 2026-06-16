"""Debug script to trace why run_ai_pipeline.py produces 'No itinerary generated'"""
import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.abspath("."))


async def main():
    from ai_engine.chat.intent_parser import parse_intent
    from ai_engine.tools.places_tool import get_places_for_city
    from ai_engine.agents.planning_agent import _select_candidates, _trim_for_prompt
    from ai_engine.tools.profile_tool import load_mock_profile
    from ai_engine.profiling.behavioral_profile import profile_to_text
    from ai_engine.graph.graph_builder import trip_graph
    from app.core.config import settings  # ensures GOOGLE_API_KEY is loaded early

    user_message = "Plan me a 2-day trip to Cairo focusing on history and food."

    # Step 1: Intent
    print("=" * 60)
    print("STEP 1: Intent Parsing")
    intent = parse_intent(user_message)
    print(f"  intent_type: {intent.get('intent_type')}")
    print(f"  destination_city: {intent.get('destination_city')}")
    print(f"  duration_days: {intent.get('duration_days')}")

    # Step 2: Places
    print("\n" + "=" * 60)
    print("STEP 2: Places Loading")
    city = intent.get("destination_city")
    profile = load_mock_profile("test_user")
    interests = profile.get("interests", [])
    print(f"  interests from profile: {interests}")
    places = get_places_for_city(city, interests=interests)
    print(f"  places count: {len(places)}")

    # Step 3: Candidate selection
    print("\n" + "=" * 60)
    print("STEP 3: Candidate Selection")
    duration_days = intent.get("duration_days") or 3
    candidates = _select_candidates(places, interests, duration_days)
    print(f"  candidates count: {len(candidates)}")
    trimmed = [_trim_for_prompt(p) for p in candidates]
    print(f"  trimmed count: {len(trimmed)}")
    if trimmed:
        print(f"  first trimmed: {json.dumps(trimmed[0], default=str)[:200]}")

    # Step 4: Full graph invocation
    print("\n" + "=" * 60)
    print("STEP 4: Full Graph Invocation")
    initial_state = {
        "user_id": "test_user",
        "user_message": user_message,
        "profile": profile,
        "token": None,
        "draft_itinerary": None,
        "optimized_itinerary": None,
        "is_valid": None,
        "next_agent": None,
        "error": None,
        "intent_type": intent.get("intent_type", "plan_trip"),
        "destination_city": intent.get("destination_city"),
        "destination_country": intent.get("destination_country"),
        "duration_days": intent.get("duration_days"),
        "travel_dates": intent.get("travel_dates"),
        "special_requests": intent.get("special_requests"),
        "group_size": intent.get("group_size"),
        "missing_fields": intent.get("missing_fields", []),
        "agent_messages": [],
    }

    try:
        result_state = await trip_graph.ainvoke(initial_state)
        print(f"  error in result: {result_state.get('error')}")
        print(f"  draft_itinerary: {'SET' if result_state.get('draft_itinerary') else 'NONE'}")
        print(f"  optimized_itinerary: {'SET' if result_state.get('optimized_itinerary') else 'NONE'}")
        print(f"  is_valid: {result_state.get('is_valid')}")
        print(f"  planning_attempts: {result_state.get('planning_attempts')}")
    except Exception as e:
        print(f"  GRAPH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("STEP 5: Final Result")
    itinerary = result_state.get("optimized_itinerary") if 'result_state' in dir() else None
    print(f"  itinerary: {'SET' if itinerary else 'NONE'}")


if __name__ == "__main__":
    asyncio.run(main())
