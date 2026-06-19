import os
import sys
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage
from app.external.llm_client import get_planning_llm, get_fast_llm, get_reasoning_llm, analyze_image


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


def test_gemini_vision():
    """Test with a real image file — place any .jpg in the tests/ folder."""
    import os
    test_image = Path(__file__).parent / "sample.jpg"
    if not test_image.exists():
        print("[SKIP] No sample.jpg found in tests/ - skipping vision test.")
        return

    with open(test_image, "rb") as f:
        image_bytes = f.read()

    result = analyze_image(image_bytes, 
                           """
                            You are an image analysis engine for a travel planning app.

                            Return your response as VALID JSON only. No explanation, no extra text.

                            Schema:
                            {
                            "destination_type": string,         // one word (e.g. beach, city, desert, mountain, historical)
                            "atmosphere": [string],             // 2-4 tags
                            "best_for": [string],               // 2-4 traveler types
                            "activities": [string],             // 2-5 activities
                            "best_season": string,              // one of: summer, winter, spring, autumn, all_year
                            "budget": string,                   // one of: budget, mid_range, luxury
                            "trip_tags": [string]               // exactly 5 hashtags, lowercase, no spaces
                            }

                            Rules:
                            - Output MUST be valid JSON.
                            - Do not include markdown or code blocks.
                            - Use lowercase for all values.
                            - Keep answers concise.
                            - If unsure, make a reasonable guess.

                            Output:
    """)
    print(f"[OK] Vision response: {result}")
    assert result and len(result) > 0

if __name__ == "__main__":
    test_gemini_text()
    test_gemini_fast()
    test_gemini_vision()