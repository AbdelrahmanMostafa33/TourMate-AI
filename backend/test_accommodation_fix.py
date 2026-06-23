"""
Quick test to verify the UnboundLocalError fix for "provide resorts instead of hotels".

Simulates a 2-turn chat:
  Turn 1: "plan me a 2 day trip to cairo"
  Turn 2: "provide resorts instead of hotels"

This verifies that the fix (initializing `reranked = None`) prevents the crash.
"""
import asyncio
import logging
import os
import sys

# Silence noisy logs during test
logging.basicConfig(level=logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from dotenv import load_dotenv
load_dotenv()

from ai_engine.chat.conversation_agent import handle_chat


async def main():
    user_id = "test_accommodation_user"

    print("=" * 60)
    print("Turn 1: 'plan me a 2 day trip to cairo'")
    print("=" * 60)

    try:
        result1 = await handle_chat(
            user_id=user_id,
            user_message="plan me a 2 day trip to cairo",
        )
        print(f"Response type: {result1.get('response_type')}")
        print(f"Phase: {result1.get('phase')}")
        has_itinerary = result1.get("itinerary") is not None
        print(f"Itinerary generated: {has_itinerary}")

        if not has_itinerary:
            print(f"Message: {result1.get('message', '')[:200]}")
            print("\n⚠ No itinerary was generated - cannot test Turn 2.")
            print("This may be due to API key / DB connectivity issues.")
            return

        session_id = result1.get("session_id")
        print(f"Session ID: {session_id}")

        # Check accommodation in itinerary
        itinerary = result1["itinerary"]
        hotels = itinerary.get("accommodation_suggestions", [])
        hotel_types = [h.get("accommodation_type") for h in hotels]
        print(f"Initial hotel types: {hotel_types}")

    except Exception as e:
        print(f"\n❌ Turn 1 failed with: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("Turn 2: 'provide resorts instead of hotels'")
    print("=" * 60)

    try:
        result2 = await handle_chat(
            user_id=user_id,
            user_message="provide resorts instead of hotels",
            session_id=session_id,
        )
        print(f"Response type: {result2.get('response_type')}")
        print(f"Phase: {result2.get('phase')}")
        has_itinerary2 = result2.get("itinerary") is not None
        print(f"Itinerary generated: {has_itinerary2}")

        if has_itinerary2:
            itinerary2 = result2["itinerary"]
            hotels2 = itinerary2.get("accommodation_suggestions", [])
            hotel_types2 = [h.get("accommodation_type") for h in hotels2]
            print(f"New hotel types: {hotel_types2}")

        print(f"\n✅ Test PASSED - No UnboundLocalError!")
        print(f"Message preview: {result2.get('message', '')[:200]}")

    except UnboundLocalError as e:
        print(f"\n❌ TEST FAILED - UnboundLocalError still occurs: {e}")
    except Exception as e:
        print(f"\n❌ Turn 2 failed with: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
