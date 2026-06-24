"""Integration test for token tracking feature."""
import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from ai_engine.conversation.orchestrator import handle_chat
from ai_engine.llm import token_tracker


async def test():
    token_tracker.reset()
    user_id = "test_user_token_tracking"

    print("=" * 60)
    print("  Token Tracking Integration Test")
    print("=" * 60)

    # Test 1: Send a greeting
    print("\n--- Test 1: Sending 'hello' ---")
    r = await handle_chat(user_id=user_id, user_message="hello")
    print(f"Response type: {r.get('response_type')}")
    print(f"Message: {r.get('message', '')[:80]}...")
    print(f"LLM calls so far: {token_tracker.call_count}")
    assert token_tracker.call_count >= 1, f"Expected >=1 LLM calls, got {token_tracker.call_count}"
    assert token_tracker.total.total_tokens > 0, "Expected positive token count"
    print(f"Total tokens so far: {token_tracker.total.total_tokens}")
    print("PASS: First LLM call tracked")

    # Test 2: Send destination
    print("\n--- Test 2: Sending 'Cairo for 3 days' ---")
    r2 = await handle_chat(
        user_id=user_id,
        user_message="Cairo for 3 days",
        session_id=r.get("session_id"),
    )
    print(f"Response type: {r2.get('response_type')}")
    print(f"Message: {r2.get('message', '')[:80]}...")
    print(f"LLM calls so far: {token_tracker.call_count}")
    assert token_tracker.call_count >= 2, f"Expected >=2 LLM calls, got {token_tracker.call_count}"
    assert token_tracker.total.total_tokens > 0, "Expected positive token count"
    print("PASS: Second LLM call tracked")

    # Test 3: Print full summary
    print("\n--- Test 3: Full Token Usage Summary ---")
    token_tracker.print_summary()

    # Verify per-role breakdown exists
    assert len(token_tracker._by_role) >= 1, "Expected at least 1 role in breakdown"
    for role, usage in token_tracker._by_role.items():
        assert usage.total_tokens > 0, f"Role {role} should have positive tokens"
        print(f"  {role}: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED!")
    print(f"  Total LLM calls: {token_tracker.call_count}")
    print(f"  Total tokens: {token_tracker.total.total_tokens}")
    print(f"  Roles tracked: {', '.join(token_tracker._by_role.keys())}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test())
