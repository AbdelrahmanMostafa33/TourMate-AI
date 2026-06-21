"""
End-to-end test: Run the full chat pipeline and verify the validator runs without errors.
Sends the same conversation as the user's original test run and captures key log lines.
"""
import asyncio
import logging
import sys

# Set up logging to capture validator and key manager output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)

# Reduce noise from third-party libraries
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("groq").setLevel(logging.WARNING)
logging.getLogger("google.genai").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

from ai_engine.chat.conversation_agent import handle_chat


async def main():
    user_id = "test_validator_user"

    messages = [
        "hello",
        "plan a 3 day trip to cairo with moderate pace and solo travel style",
        "medium budget and accomodation style will be hostel",
        "history and musuems",
        "street food",
    ]

    for msg in messages:
        print(f"\n{'='*60}")
        print(f"  Sending: {msg}")
        print(f"{'='*60}")

        response = await handle_chat(
            user_id=user_id,
            user_message=msg,
            token=None,
        )

        resp_type = response.get("response_type", "?")
        resp_msg = response.get("message", "") or ""

        # Show a preview
        preview = resp_msg[:200].replace("\n", " ")
        print(f"  Type: {resp_type}")
        print(f"  Response preview: {preview}...")

        # Check for validator messages in agent_messages
        agent_msgs = response.get("agent_messages", [])
        for am in agent_msgs:
            if "Validator" in am or "KeyManager" in am or "Fallback" in am:
                print(f"    >>> {am}")

        # Check validation results
        validation = response.get("validation")
        if validation:
            print(f"    >>> Validation: valid={validation.get('is_valid')} "
                  f"score={validation.get('score')} "
                  f"issues={len(validation.get('issues', []))}")

        # Check itinerary
        itinerary = response.get("itinerary")
        if itinerary:
            days = len(itinerary.get("days", []))
            stops = sum(len(d.get("stops", [])) for d in itinerary.get("days", []))
            print(f"    >>> Itinerary: {days} days, {stops} stops")
        elif resp_type == "itinerary":
            print(f"    >>> No itinerary in response (pipeline may have failed)")

        if resp_type == "itinerary":
            # Check if the full message contains any error indicators
            if "error" in resp_msg.lower() or "issue" in resp_msg.lower():
                print(f"  ⚠️  Possible error in response!")
                # Print the full message if there's an issue
                print(f"  Full response:\n{resp_msg}")
            else:
                print(f"  ✅ Itinerary generated successfully!")
                # Print the full formatted itinerary
                print(f"\n{resp_msg[:3000]}")

    print(f"\n{'='*60}")
    print(f"  Test complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
