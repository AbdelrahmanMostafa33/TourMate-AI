"""
End-to-end test: simulates the full chat.py conversation via handle_chat().
Tracks itinerary generation across ALL turns (not just the last one).
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def main():
    from ai_engine.conversation.orchestrator import handle_chat

    import uuid
    user_id = f"e2e_test_{uuid.uuid4().hex[:8]}"
    session_id = None

    messages = [
        "hello tourmate",
        "I want a trip to cairo for 3 days",
        "solo",
        "high",
        "mixed",
        "nature",
        "local food",
        "resort",
    ]

    print("=" * 60)
    print("End-to-End Chat Pipeline Test")
    print("=" * 60)

    itinerary_generated = False
    itinerary_turn = None
    itinerary_data = None
    last_response_type = None
    last_message = None

    for i, msg in enumerate(messages, 1):
        print(f"\n--- Turn {i}: User says '{msg}' ---")
        try:
            result = await handle_chat(
                user_id=user_id,
                user_message=msg,
                session_id=session_id,
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            return

        session_id = result.get("session_id", session_id)
        response_type = result.get("response_type", "")
        phase = result.get("phase", "")
        message = result.get("message", "")
        itinerary = result.get("itinerary")

        last_response_type = response_type
        last_message = message

        print(f"  phase: {phase}")
        print(f"  response_type: {response_type}")
        print(f"  message: {message[:200]}")

        # Track itinerary generation across ALL turns
        if itinerary and not itinerary_generated:
            itinerary_generated = True
            itinerary_turn = i
            itinerary_data = itinerary
            days = itinerary.get("days", [])
            hotels = itinerary.get("accommodation_suggestions", [])
            print(f"  >>> ITINERARY GENERATED! {len(days)} days, {len(hotels)} hotels")
            for day in days:
                day_num = day.get("day_number", "?")
                theme = day.get("theme", "")
                stops = day.get("stops", [])
                print(f"    Day {day_num}: {theme} ({len(stops)} stops)")

        # Track if itinerary was lost (regression check)
        if itinerary_generated and response_type == "plan_generation" and not itinerary:
            print(f"  >>> WARNING: Itinerary was generated but lost in turn {i}!")

    # Final check
    print("\n" + "=" * 60)
    print("Final Result")
    print("=" * 60)

    if itinerary_generated:
        days = itinerary_data.get("days", [])
        hotels = itinerary_data.get("accommodation_suggestions", [])
        print(f"SUCCESS: Itinerary generated at turn {itinerary_turn}!")
        print(f"  - {len(days)} days planned")
        print(f"  - {len(hotels)} accommodation suggestions")
        for day in days:
            day_num = day.get("day_number", "?")
            theme = day.get("theme", "")
            stops = day.get("stops", [])
            print(f"  Day {day_num}: {theme} ({len(stops)} stops)")
    else:
        print("FAILURE: No itinerary was generated in any turn.")
        print(f"  Last response_type: {last_response_type}")
        print(f"  Last message: {last_message[:200] if last_message else 'None'}")

    # Cleanup session
    from ai_engine.conversation.redis_memory import get_session_manager
    manager = await get_session_manager()
    await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
