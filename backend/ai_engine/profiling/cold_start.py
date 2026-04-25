# ai/profiling/cold_start.py

from app.external.groq_client import get_fast_llm
from langchain_core.messages import HumanMessage
import json


def generate_persona(quiz_data: dict) -> dict:
    """
    Generates a personalized travel persona using an LLM (Gemini).

    This function transforms structured quiz data into a more human-like
    representation (persona) that can guide tone, recommendations,
    and follow-up interactions in the application.

    It is typically called once after the user completes the onboarding quiz.

    Args:
        quiz_data: Dictionary containing user quiz responses
                   (matches the backend QuizSubmitRequest schema)

    Returns:
        Dictionary with:
        - persona_name: Short label for the user type
        - persona_bio: 2–3 sentence description of preferences
        - suggested_questions: Example queries to guide user interaction
    """
    # Initialize LLM client (Groq via LangChain wrapper)
    llm = get_fast_llm()

    # ── Convert structured quiz data into readable text ─────────────
    # These strings are injected into the prompt to give the LLM context

    interests_str = ", ".join(quiz_data.get("interests", []))
    dining_str = ", ".join(quiz_data.get("dining_preferences", []))
    traveler_types_str = ", ".join(quiz_data.get("traveler_types", []))

    # Fallback to "solo" if not provided
    companion_str = quiz_data.get("travel_companion", "solo")

    # Slider values (default to mid-range if missing)
    budget = quiz_data.get("budget_level", 50)
    adventure = quiz_data.get("adventure_relaxing", 50)
    nature_culture = quiz_data.get("nature_culture", 50)

    # ── Convert numeric sliders into semantic labels ────────────────
    # This makes the prompt more natural and interpretable by the LLM

    budget_label = (
        "luxury" if budget > 66
        else ("moderate" if budget > 33 else "budget-conscious")
    )

    style_label = (
        "adventurous" if adventure > 66
        else ("relaxed" if adventure < 33 else "balanced")
    )

    focus_label = (
        "culture-focused" if nature_culture > 66
        else ("nature-focused" if nature_culture < 33 else "mixed")
    )

    # ── Prompt construction ─────────────────────────────────────────
    # The prompt is carefully structured to:
    # 1. Provide clear user context
    # 2. Constrain output format (strict JSON)
    # 3. Avoid hallucinated structure or extra text

    prompt = f"""You are a travel personality expert. Based on this traveler profile, 
    create a persona name, a short bio, and 3 suggested questions they might ask a travel assistant.

    Traveler Profile:
    - Travel companion: {companion_str}
    - Style: {style_label}, {focus_label}, {budget_label}
    - Interests: {interests_str}
    - Dining preferences: {dining_str}
    - Traveler types: {traveler_types_str}

    Respond ONLY with valid JSON in this exact format, no markdown, no extra text:
    {{
    "persona_name": "The [Adjective] [Noun]",
    "persona_bio": "2-3 sentence description of this traveler's personality and what they love.",
    "suggested_questions": [
        "Question 1 they would ask a travel assistant?",
        "Question 2 they would ask?",
        "Question 3 they would ask?"
    ]
    }}"""

    # Send prompt to LLM
    response = llm.invoke([HumanMessage(content=prompt)])

    # ── Response parsing ────────────────────────────────────────────
    # Gemini may sometimes wrap output in markdown code fences,
    # so we defensively clean the response before parsing JSON

    raw = response.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    # Convert JSON string → Python dict
    result = json.loads(raw.strip())

    return result


def build_default_persona() -> dict:
    """
    Provides a fallback persona for users who skip the onboarding quiz.

    This avoids having an empty state and ensures the system can still:
    - Generate recommendations
    - Provide a consistent user experience

    No LLM call is used here for:
    - Performance (instant response)
    - Cost efficiency
    - Predictability

    Returns:
        Dictionary with default persona fields
    """
    return {
        "persona_name": "The Open Explorer",

        "persona_bio": (
            "You're a free spirit who enjoys discovering new places "
            "without a fixed plan. Every trip is a new adventure!"
        ),

        "suggested_questions": [
            "What's a good place to visit this weekend?",
            "Surprise me with a travel idea!",
            "What are the most popular destinations right now?"
        ]
    }