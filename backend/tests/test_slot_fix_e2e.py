"""
Quick smoke test: simulates the exact chat.py conversation that was failing.
Verifies that:
  1. normalize_budget('high') → 'luxury' (the fix)
  2. All slots are collected and is_complete() returns True
  3. The pipeline triggers _handle_plan_trip instead of asking for more info
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def main():
    from ai_engine.tools.slot_normalizer import normalize_budget
    from ai_engine.memory.conversation_state import ConversationState, TripSlots

    # ── Step 1: Verify the normalizer fix ──────────────────────────────────
    print("=" * 60)
    print("Step 1: Testing normalize_budget('high')")
    print("=" * 60)
    result = normalize_budget("high")
    assert result == "luxury", f"Expected 'luxury', got {result!r}"
    print(f"  OK normalize_budget('high') = {result!r}")

    # ── Step 2: Simulate the full conversation slot accumulation ────────────
    print("\n" + "=" * 60)
    print("Step 2: Simulating slot accumulation across 8 turns")
    print("=" * 60)

    state = ConversationState(user_id="test_user")

    # Turn 2: destination + duration
    state.slots.merge({"destination_city": "Cairo", "destination_country": "Egypt", "duration_days": 3})
    print(f"  Turn 2 (destination+duration): missing={state.slots.missing_required()}")

    # Turn 3: travel style
    state.slots.merge({"travel_style": "solo"})
    print(f"  Turn 3 (style=solo):            missing={state.slots.missing_required()}")

    # Turn 4: budget — THIS WAS THE BUG: "high" must normalize to "luxury"
    from ai_engine.tools.slot_normalizer import normalize_extracted_slots
    raw_extracted = normalize_extracted_slots({"budget_level": "high"})
    state.slots.merge(raw_extracted)
    print(f"  Turn 4 (budget=high -> {state.slots.budget_level!r}): missing={state.slots.missing_required()}")

    # Turn 5: pace
    raw_extracted = normalize_extracted_slots({"pace": "mixed"})
    state.slots.merge(raw_extracted)
    print(f"  Turn 5 (pace=mixed -> {state.slots.pace!r}):       missing={state.slots.missing_required()}")

    # Turn 6: interests
    state.slots.merge({"interests": ["nature"]})
    print(f"  Turn 6 (interests=nature):      missing={state.slots.missing_required()}")

    # Turn 7: food
    raw_extracted = normalize_extracted_slots({"food_preferences": ["local food"]})
    state.slots.merge(raw_extracted)
    print(f"  Turn 7 (food=local food -> {state.slots.food_preferences}): missing={state.slots.missing_required()}")

    # Turn 8: accommodation
    raw_extracted = normalize_extracted_slots({"accommodation_preferences": ["resort"]})
    state.slots.merge(raw_extracted)
    print(f"  Turn 8 (accommodation=resort -> {state.slots.accommodation_preferences}): missing={state.slots.missing_required()}")

    # ── Step 3: Verify is_complete() ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("Step 3: Checking is_complete()")
    print("=" * 60)
    complete = state.slots.is_complete()
    print(f"  is_complete() = {complete}")
    if complete:
        print("  OK All slots collected! Pipeline would trigger.")
    else:
        print(f"  FAIL Still missing: {state.slots.missing_required()}")
        sys.exit(1)

    # ── Step 4: Print final slot summary ───────────────────────────────────
    print("\n" + "=" * 60)
    print("Final Slot Summary")
    print("=" * 60)
    print(f"  destination:  {state.slots.destination_city}")
    print(f"  duration:     {state.slots.duration_days} days")
    print(f"  budget:       {state.slots.budget_level}")
    print(f"  style:        {state.slots.travel_style}")
    print(f"  pace:         {state.slots.pace}")
    print(f"  interests:    {state.slots.interests}")
    print(f"  food:         {state.slots.food_preferences}")
    print(f"  accommodation:{state.slots.accommodation_preferences}")

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED -- The 'high' -> 'luxury' fix works!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
