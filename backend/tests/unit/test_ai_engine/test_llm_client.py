import os
import sys
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage
from app.external.llm_client import get_planning_llm, get_fast_llm, get_reasoning_llm


def test_gemini_text():
    llm = get_planning_llm()
    messages = [HumanMessage(content="""
    You are a travel assistant for a tourism app.

    Task:
    Suggest exactly ONE tourist activity in Cairo.

    Constraints:
    - Output must be exactly ONE sentence.
    - Make it engaging and specific (mention a real place if possible).
    - Keep it under 20 words.
    - No emojis, no extra text.

    Output:
    """)]
    print("Testing planning LLM (Gemini 2.5 Flash)...")
    response = llm.invoke(messages)
    print(f"[OK] Response: {response.content}")
    assert response.content and len(response.content) > 0


def test_gemini_fast():
    """Test the fast LLM (Groq llama-3.1-8b-instant) for classification tasks."""
    if not os.environ.get("GROQ_API_KEY"):
        print("[SKIP] GROQ_API_KEY not set — skipping fast LLM test.")
        return

    llm = get_fast_llm()
    messages = [HumanMessage(content="""
    You are a strict intent classifier for a travel planning app.

    Classify the user request into EXACTLY ONE of these labels:

    - new_plan   → user wants to create a brand new trip from scratch (no existing plan mentioned)
    - modify     → user wants to change, update, add to, or remove from an existing trip

    Rules:
    - Output ONLY the label, nothing else.
    - Lowercase only.
    - No punctuation, no explanation.

    Examples:
    "Plan me a 3-day trip to Paris"              → new_plan
    "I want to visit Rome next summer"           → new_plan
    "Add a museum to my itinerary"               → modify
    "Remove the beach stop on day 2"             → modify
    "Can we swap day 1 and day 2?"               → modify
    "Change the hotel to something cheaper"      → modify

    User input:
    "I want to add a museum to my trip."

    Output:
    """)]
    print("Testing fast LLM (Groq llama-3.1-8b-instant)...")
    response = llm.invoke(messages)
    print(f"[OK] Response: {response.content}")
    assert response.content and len(response.content) > 0


async def test_gemini_vision():
    """
    Test vision via ``invoke_with_fallback``.

    Replaces the old ``analyze_image`` call which was synchronous and
    lacked key rotation / rate-limit backoff.  The canonical vision API
    is now ``ai_engine.vision.image_analyzer.analyze_travel_image``.
    """
    from ai_engine.llm.invoke import invoke_with_fallback
    from ai_engine.prompts.vision_prompt import VISION_EXTRACTION_PROMPT

    test_image = Path(__file__).parent / "sample.jpg"
    if not test_image.exists():
        print("[SKIP] No sample.jpg found in tests/ - skipping vision test.")
        return

    with open(test_image, "rb") as f:
        image_bytes = f.read()

    import base64
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    message = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        },
        {
            "type": "text",
            "text": VISION_EXTRACTION_PROMPT,
        },
    ])

    response = await invoke_with_fallback("vision", [message])
    print(f"[OK] Vision response: {response.content[:200]}...")
    assert response.content and len(response.content) > 0


if __name__ == "__main__":
    import asyncio
    test_gemini_text()
    test_gemini_fast()
    asyncio.run(test_gemini_vision())