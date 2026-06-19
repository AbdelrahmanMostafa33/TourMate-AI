"""
LLM client — thin wrappers around the shared registry.

All agent-specific LLM creation is now driven by ``ai_engine.llm_config``.
The functions here exist for backward compatibility so that existing
callers (``get_fast_llm``, ``get_planning_llm``, etc.) keep working
without changes.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
import base64

from ai_engine.llm_config import get_llm_for_agent


# ── Backward-compatible wrappers ──────────────────────────────────────────────

def get_planning_llm() -> BaseChatModel:
    """Gemini 2.5 Flash for itinerary generation."""
    return get_llm_for_agent("planner")


def get_vision_llm() -> BaseChatModel:
    """Gemini 2.5 Flash for image understanding (native multimodal)."""
    return get_llm_for_agent("vision")


def get_fast_llm() -> BaseChatModel:
    """Groq Llama 3.1 8B for intent parsing, preference, validation."""
    return get_llm_for_agent("intent_parser")


def get_reasoning_llm() -> BaseChatModel:
    """Groq Llama 3.3 70B for general chat and itinerary review Q&A."""
    return get_llm_for_agent("general_chat")


# ── Shared utilities ──────────────────────────────────────────────────────────

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
