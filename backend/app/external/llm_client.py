from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import base64

from ai_engine.constants import (
    GEMINI_VISION_MODEL,
    GEMINI_PLANNING_MODEL,
    GEMINI_FAST_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_MAX_TOKENS,
)
from app.core.config import settings

GOOGLE_API_KEY = settings.google_api_key


def get_planning_llm() -> ChatGoogleGenerativeAI:
    """Gemini 2.5 Flash for itinerary generation (reasoning + large prompts)."""
    return ChatGoogleGenerativeAI(
        model=GEMINI_PLANNING_MODEL,
        temperature=GEMINI_TEMPERATURE,
        max_tokens=GEMINI_MAX_TOKENS,
        google_api_key=GOOGLE_API_KEY,
    )


def get_fast_llm() -> ChatGoogleGenerativeAI:
    """Gemini 2.5 Flash Lite for intent parsing and validation (fast + cheap)."""
    return ChatGoogleGenerativeAI(
        model=GEMINI_FAST_MODEL,
        temperature=0.2,         # lower temp for classification tasks
        max_tokens=2048,
        google_api_key=GOOGLE_API_KEY,
    )


def get_vision_llm() -> ChatGoogleGenerativeAI:
    """Gemini 2.5 Flash for image understanding (native multimodal)."""
    return ChatGoogleGenerativeAI(
        model=GEMINI_VISION_MODEL,
        temperature=GEMINI_TEMPERATURE,
        max_tokens=GEMINI_MAX_TOKENS,
        google_api_key=GOOGLE_API_KEY,
    )


def analyze_image(image_bytes: bytes, prompt: str) -> str:
    """
    Send an image + text prompt to Gemini 2.5 Flash (native multimodal).

    Args:
        image_bytes: raw image bytes (JPEG or PNG)
        prompt: instruction for what to extract from the image
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    message = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        },
        {
            "type": "text",
            "text": prompt,
        },
    ])

    llm = get_vision_llm()
    response = llm.invoke([message])
    return response.content
