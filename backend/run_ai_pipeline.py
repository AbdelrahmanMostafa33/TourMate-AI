import asyncio
import json
import os
import sys

# Add the current directory to sys.path to allow imports from ai_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from ai_engine.chat.orchestrator import handle_chat

# ── Test messages ──────────────────────────────────────────────────────────

# Single-turn: all 8 required slots provided at once
SINGLE_TURN_MESSAGE = (
    "Plan me a 2-day trip to Cairo focusing on history and food. "
    "I have a moderate budget, love cultural experiences, prefer a moderate pace, "
    "and I'm interested in history, art, and local cuisine. "
    "I like boutique hotels."
)

# Multi-turn: simulate a real conversation flow
MULTI_TURN_MESSAGES = [
    "I want to visit Cairo for 2 days",
    "Moderate budget, cultural style, moderate pace",
    "I'm into history, art, and food. I love local cuisine. I prefer boutique hotels.",
]


async def test_single_turn():
    """Test: complete info in one message → pipeline runs immediately."""
    print("=" * 70)
    print("TEST 1: Single-Turn (all fields in one message)")
    print("=" * 70)

    result = await handle_chat(
        user_id="test_single_turn",
        user_message=SINGLE_TURN_MESSAGE,
    )

    print(f"\nResponse Type: {result.get('response_type')}")
    print(f"Phase: {result.get('phase')}")
    print(f"Message: {result.get('message')[:200]}...")

    itinerary = result.get("itinerary")
    if itinerary:
        print(f"\nGenerated Itinerary ({len(itinerary.get('days', []))} days):")
        print(json.dumps(itinerary, indent=2, default=str)[:2000])
    else:
        print("\nNo itinerary generated.")
        print(f"Full response: {json.dumps(result, indent=2, default=str)[:1000]}")


async def test_multi_turn():
    """Test: collect slots across multiple turns → pipeline runs when complete."""
    print("\n" + "=" * 70)
    print("TEST 2: Multi-Turn (slots collected across turns)")
    print("=" * 70)

    session_id = None

    for i, msg in enumerate(MULTI_TURN_MESSAGES, 1):
        print(f"\n--- Turn {i} ---")
        print(f"User: {msg}")

        result = await handle_chat(
            user_id="test_multi_turn",
            user_message=msg,
            session_id=session_id,
        )
        session_id = result.get("session_id")

        print(f"Response Type: {result.get('response_type')}")
        print(f"Phase: {result.get('phase')}")
        print(f"Agent: {result.get('message')[:200]}")

        itinerary = result.get("itinerary")
        if itinerary:
            print(f"\nGenerated Itinerary ({len(itinerary.get('days', []))} days):")
            print(json.dumps(itinerary, indent=2, default=str)[:2000])
            break


async def main():
    print("TourMate AI Pipeline Test\n")

    # Check for API key
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        try:
            from app.core.config import settings
            api_key = settings.google_api_key
        except Exception:
            api_key = None

    if not api_key:
        print("WARNING: No API key found. Set GOOGLE_API_KEY in .env or as env var.")
        return

    # Run tests
    await test_single_turn()
    await test_multi_turn()

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
