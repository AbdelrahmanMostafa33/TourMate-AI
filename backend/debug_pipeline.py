"""Debug script to run the full AI pipeline end-to-end.

Runs the pipeline directly (bypassing Redis/conversation agent):
  load_profile → preference → retrieval → ranking → planner → optimizer → validator

Requires: GOOGLE_API_KEY in .env (for Gemini LLM calls).
Does NOT require Redis.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from app.core.config import settings  # loads .env early


async def main():
    from ai_engine.graph.graph_builder import trip_graph

    user_message = "Plan me a 2-day trip to Cairo focusing on history and food."

    # Build initial state with a mock profile (no token = no DB lookup)
    initial_state = {
        # ── Core request ──────────────────────────────────────
        "user_id":  "debug_user",
        "user_message": user_message,

        # ── Profile (mock) ────────────────────────────────────
        "profile": {
            "profile_id": "mock_profile_001",
            "trip_id": "debug_trip_001",
            "budget_level": "moderate",
            "travel_style": "cultural",
            "pace": "moderate",
            "interests": ["history", "food", "art"],
            "food_preferences": ["local cuisine", "street food"],
            "accommodation_preferences": ["boutique hotel"],
            "luxury_score": None,
            "culture_score": None,
            "adventure_score": None,

            "confidence": None,
            "generated_at": None,
            "updated_at": None,
        },

        "token": None,
        "trip_id": "debug_trip_001",

        # ── Preference extraction ─────────────────────────────
        "extracted_preferences": None,

        # ── Retrieval pipeline ────────────────────────────────
        "filtered_places": None,
        "candidate_places": None,

        # ── Pipeline outputs ──────────────────────────────────
        "draft_itinerary": None,
        "optimized_itinerary": None,
        "is_valid": None,
        "validation": None,
        "planning_attempts": 0,

        # ── Control flow ──────────────────────────────────────
        "next_agent": None,
        "error": None,

        # ── Intent fields ─────────────────────────────────────
        "intent_type":         "plan_trip",
        "destination_city":    "Cairo",
        "destination_country": "Egypt",
        "duration_days":       2,
        "travel_dates":        None,
        "special_requests":    "focus on history and food",
        "group_size":          None,
        "missing_fields":      [],

        # ── Trace ─────────────────────────────────────────────
        "agent_messages": [],
    }

    # Fix Windows console encoding for special characters
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    print("=" * 70)
    print("TourMate AI - Full Pipeline Debug Run")
    print("=" * 70)
    print(f"\nUser Message: {user_message}")
    print(f"Destination: Cairo, Egypt | Duration: 2 days")
    print(f"Profile: cultural, moderate budget, interests: history, food, art")
    print()

    try:
        result_state = await trip_graph.ainvoke(initial_state)
    except Exception as e:
        print(f"\n[ERROR] PIPELINE EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return

    # ── Print results ──────────────────────────────────────────
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    # Error check
    if result_state.get("error"):
        print(f"\n[ERROR] Pipeline Error: {result_state['error']}")

    # Agent trace
    messages = result_state.get("agent_messages", [])
    if messages:
        print(f"\n📋 Agent Trace ({len(messages)} messages):")
        for msg in messages:
            print(f"  {msg}")

    # Profile enrichment
    profile = result_state.get("profile", {})
    if profile:
        print(f"\n👤 Enriched Profile:")
        print(f"  Budget: {profile.get('budget_level')}")
        print(f"  Style:  {profile.get('travel_style')}")
        print(f"  Pace:   {profile.get('pace')}")
        print(f"  Luxury score:  {profile.get('luxury_score')}")
        print(f"  Culture score: {profile.get('culture_score')}")
        print(f"  Adventure score: {profile.get('adventure_score')}")
        print(f"  Confidence: {profile.get('confidence')}")

    # Extracted preferences
    prefs = result_state.get("extracted_preferences")
    if prefs:
        print(f"\n🎯 Extracted Preferences:")
        print(json.dumps(prefs, indent=2, default=str))

    # Filtered places count
    filtered = result_state.get("filtered_places", [])
    print(f"\n🔍 Filtered Places: {len(filtered)}")
    for p in filtered[:5]:
        print(f"  - {p.get('name', '?')} ({p.get('category', '?')}) rating={p.get('rating', '?')}")

    # Candidate places count
    candidates = result_state.get("candidate_places", [])
    print(f"\n⭐ Ranked Candidates: {len(candidates)}")

    # Itinerary
    itinerary = result_state.get("optimized_itinerary") or result_state.get("draft_itinerary")
    if itinerary:
        print(f"\n🗺️  Generated Itinerary:")
        print(json.dumps(itinerary, indent=2, default=str))
    else:
        print(f"\n[ERROR] No itinerary generated")

    # Validation
    if result_state.get("validation"):
        val = result_state["validation"]
        print(f"\n✅ Validation:")
        print(f"  Valid: {result_state.get('is_valid')}")
        print(f"  Score: {val.get('score', '?')}")
        if val.get("issues"):
            print(f"  Issues: {val['issues']}")
        if val.get("suggestions"):
            print(f"  Suggestions: {val['suggestions']}")

    print(f"\nPlanning attempts: {result_state.get('planning_attempts', 0)}")


if __name__ == "__main__":
    asyncio.run(main())
