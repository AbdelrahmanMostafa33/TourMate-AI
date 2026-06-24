"""
End-to-end test for the Itinerary Modifier Agent.

Tests:
1. Generate a baseline itinerary via the full pipeline
2. Apply a modification request ("more entertaining")
3. Verify the modifier ran and changed the itinerary
"""

import sys
sys.path.insert(0, '.')

import asyncio
import os
import json

os.environ.setdefault("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

from ai_engine.chat.orchestrator import handle_chat


async def test():
    print("=" * 70)
    print("TEST 1: Generate itinerary (baseline)")
    print("=" * 70)
    result = await handle_chat(
        user_id="test_modifier_v2",
        user_message="Plan me a 3-day trip to Cairo",
    )
    phase = result.get("phase", "?")
    resp_type = result.get("response_type", "?")
    itinerary = result.get("itinerary")
    has_it = itinerary is not None and bool(itinerary.get("days"))
    print(f"Phase: {phase}")
    print(f"Response Type: {resp_type}")
    print(f"Has itinerary: {has_it}")

    if has_it:
        days = itinerary.get("days", [])
        total_stops = sum(len(d.get("stops", [])) for d in days)
        print(f"Days: {len(days)}, Stops: {total_stops}")
        for d in days:
            dn = d.get("day_number", "?")
            theme = d.get("theme", "")
            names = [s.get("name", "?") for s in d.get("stops", [])]
            print(f"  Day {dn}: {theme} — {', '.join(names)}")

    if not has_it:
        print("ERROR: No itinerary generated!")
        return

    print()
    print("=" * 70)
    print("TEST 2: Modify the itinerary (should use modifier agent)")
    print("=" * 70)
    result2 = await handle_chat(
        user_id="test_modifier_v2",
        user_message="Make it more entertaining — swap a museum for something fun like a show or nightlife",
    )
    phase2 = result2.get("phase", "?")
    resp_type2 = result2.get("response_type", "?")
    itinerary2 = result2.get("itinerary")
    has_it2 = itinerary2 is not None and bool(itinerary2.get("days"))
    print(f"Phase: {phase2}")
    print(f"Response Type: {resp_type2}")
    print(f"Has itinerary: {has_it2}")

    if has_it2:
        days2 = itinerary2.get("days", [])
        total_stops2 = sum(len(d.get("stops", [])) for d in days2)
        print(f"Days: {len(days2)}, Stops: {total_stops2}")
        for d in days2:
            dn = d.get("day_number", "?")
            theme = d.get("theme", "")
            names = [s.get("name", "?") for s in d.get("stops", [])]
            print(f"  Day {dn}: {theme} — {', '.join(names)}")

        # Check if changes were made
        original_stops = set()
        for d in itinerary.get("days", []):
            for s in d.get("stops", []):
                original_stops.add(s.get("name", ""))
        modified_stops = set()
        for d in itinerary2.get("days", []):
            for s in d.get("stops", []):
                modified_stops.add(s.get("name", ""))

        new_stops = modified_stops - original_stops
        removed_stops = original_stops - modified_stops
        print()
        print("--- CHANGE DETECTION ---")
        if new_stops:
            print(f"✅ New stops added: {new_stops}")
        if removed_stops:
            print(f"✅ Stops removed: {removed_stops}")
        if not new_stops and not removed_stops:
            print("❌ No changes detected (modifier may have fallen through to full pipeline)")
        print()

        # Check agent messages for modifier evidence
        agent_msgs = result2.get("agent_messages", [])
        if agent_msgs:
            print(f"Agent messages: {agent_msgs[:3]}")
        modifier_note = itinerary2.get("_modifier_note", "")
        if modifier_note:
            print(f"Modifier note: {modifier_note}")

    print()
    print("ALL TESTS COMPLETE")


if __name__ == "__main__":
    asyncio.run(test())
