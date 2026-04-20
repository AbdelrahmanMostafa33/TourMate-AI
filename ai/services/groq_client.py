from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import base64

from ai.config.model_config import (
    GROQ_VISION_MODEL,
    GROQ_PLANNING_MODEL,
    GROQ_FAST_MODEL,
    GROQ_TEMPERATURE,
    GROQ_MAX_TOKENS,
    GROQ_API_KEY,
)


def get_planning_llm() -> ChatGroq:
    """70B model for itinerary generation."""
    return ChatGroq(
        model=GROQ_PLANNING_MODEL,
        temperature=GROQ_TEMPERATURE,
        max_tokens=GROQ_MAX_TOKENS,
        api_key=GROQ_API_KEY,
    )


def get_fast_llm() -> ChatGroq:
    """8B model for intent parsing and validation."""
    return ChatGroq(
        model=GROQ_FAST_MODEL,
        temperature=0.2,         # lower temp for classification tasks
        max_tokens=2048,
        api_key=GROQ_API_KEY,
    )


def get_vision_llm() -> ChatGroq:
    """Llama 4 Scout for image understanding."""
    return ChatGroq(
        model=GROQ_VISION_MODEL,
        temperature=GROQ_TEMPERATURE,
        max_tokens=GROQ_MAX_TOKENS,
        api_key=GROQ_API_KEY,
    )


def analyze_image(image_bytes: bytes, prompt: str) -> str:
    """
    Send an image + text prompt to Llama 4 Scout on Groq.
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