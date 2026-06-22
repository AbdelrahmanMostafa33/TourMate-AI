"""
End-to-end test: verify the editing flow works with the real LLM.

Tests:
1. Initial itinerary generation (plan trip to Cairo for 3 days)
2. "more entertaining" → should trigger Mode 1 (reranker) or Mode 2 (modifier)
   - Either is fine — the key is we get a modified itinerary
3. Print timing and token usage for both calls

Run: cd backend && GOOGLE_API_KEY="..." timeout 300 venv/Scripts/python test_end_to_end_editing.py
"""

import asyncio
import sys
import time
sys.path.insert(0, '.')

from ai_engine.chat.conversation_agent import handle_chat
from ai_engine.llm_config import token_tracker


import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


async def main():
    user_id = "e2e_test_user"

    print("=" * 70)
    print("🧪 E2E EDITING FLOW TEST")
    print("=" * 70)

    # ── Step 1: Generate itinerary ──
    print("\n[1/3] Generating itinerary: 'Plan me a 3-day trip to Cairo'")
    print("-" * 40)

    t0 = time.time()
    result1 = await handle_chat(user_id, "Plan me a 3-day trip to Cairo")
    t1 = time.time()

    itinerary1 = result1.get("itinerary")
    phase1 = result1.get("phase")
    response_type1 = result1.get("response_type")

    print(f"  Phase:          {phase1}")
    print(f"  Response type:  {response_type1}")
    print(f"  Time:           {t1 - t0:.1f}s")
    print(f"  Has itinerary:  {itinerary1 is not None}")

    if itinerary1:
        days = itinerary1.get("days", [])
        total_stops = sum(len(d.get("stops", [])) for d in days)
        hotels = len(itinerary1.get("accommodation_suggestions", []))
        print(f"  Days:           {len(days)}")
        print(f"  Total stops:    {total_stops}")
        print(f"  Hotels:         {hotels}")
    else:
        print(f"  Message:        {result1.get('message', 'N/A')[:200]}")
        print("\n⚠ Initial itinerary generation failed — skipping modification test.")
        token_tracker.print_summary()
        return

    # ── Step 2: Modify itinerary ──
    print("\n[2/3] Modifying itinerary: 'Make it more entertaining'")
    print("-" * 40)

    t2 = time.time()
    result2 = await handle_chat(user_id, "Make it more entertaining")
    t3 = time.time()

    itinerary2 = result2.get("itinerary")
    phase2 = result2.get("phase")
    response_type2 = result2.get("response_type")
    agent_msgs = result2.get("agent_messages", [])

    print(f"  Phase:          {phase2}")
    print(f"  Response type:  {response_type2}")
    print(f"  Time:           {t3 - t2:.1f}s")
    print(f"  Has itinerary:  {itinerary2 is not None}")

    if agent_msgs:
        print(f"\n  Agent messages ({len(agent_msgs)}):")
        for msg in agent_msgs:
            print(f"    {msg}")

    if itinerary2:
        days2 = itinerary2.get("days", [])
        total_stops2 = sum(len(d.get("stops", [])) for d in days2)
        print(f"  Days:           {len(days2)}")
        print(f"  Total stops:    {total_stops2}")

        # Check if itinerary changed from the original
        if itinerary1 and itinerary2:
            # Compare by checking if first stop changed
            orig_first = itinerary1.get("days", [{}])[0].get("stops", [{}])[0].get("name", "")
            new_first = days2[0].get("stops", [{}])[0].get("name", "") if days2 else ""
            print(f"\n  Original first stop:  {orig_first}")
            print(f"  New first stop:       {new_first}")
            if orig_first != new_first:
                print(f"  ✅ Itinerary was modified successfully!")
            else:
                print(f"  ℹ️  First stop unchanged — check full itinerary for differences")
    else:
        print(f"  Message:        {result2.get('message', 'N/A')[:200]}")

    # ── Step 3: Summary ──
    print("\n[3/3] Summary")
    print("-" * 40)
    print(f"  Initial generation:  {t1 - t0:.1f}s")
    print(f"  Modification:        {t3 - t2:.1f}s")
    print(f"  Total:               {t3 - t0:.1f}s")

    # Determine which mode was used based on timing
    mod_time = t3 - t2
    if mod_time < 5:
        print(f"  Editing mode:        🚀 Mode 2 (Surgical Modifier) — {mod_time:.1f}s")
    elif mod_time < 20:
        print(f"  Editing mode:        ⚡ Mode 1 (Preference Re-Ranking) — {mod_time:.1f}s")
    else:
        print(f"  Editing mode:        🐢 Mode 3 (Full Pipeline) — {mod_time:.1f}s")

    print()
    token_tracker.print_summary()

    # Clean exit
    print("\n✅ E2E test complete!")

    # Force Redis cleanup
    try:
        from ai_engine.memory.redis_memory import get_session_manager
        manager = await get_session_manager()
        await manager.close()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
