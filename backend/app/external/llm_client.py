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

from ai_engine.llm import get_llm_for_agent


# ── Backward-compatible wrappers ──────────────────────────────────────────────

def get_planning_llm() -> BaseChatModel:
    """Gemini 2.5 Flash for itinerary generation."""
    return get_llm_for_agent("planner")


def get_vision_llm() -> BaseChatModel:
    """Gemini 2.5 Flash for image understanding (native multimodal)."""
    return get_llm_for_agent("vision")


def get_fast_llm() -> BaseChatModel:
    """Groq Llama 3.1 8B for preference extraction and validation."""
    return get_llm_for_agent("preference_reranker")


def get_reasoning_llm() -> BaseChatModel:
    """Groq Llama 3.3 70B for itinerary review Q&A."""
    return get_llm_for_agent("review_qa")


# ── Shared utilities ──────────────────────────────────────────────────────────

def analyze_image(image_bytes: bytes, prompt: str) -> str:
    """
    Send an image + text prompt to Gemini 2.5 Flash (native multimodal).

    .. deprecated::
       Use ``ai_engine.vision.image_analyzer.analyze_travel_image`` instead,
       which is async, runs through ``invoke_with_fallback`` (key rotation,
       rate-limit backoff), and returns a typed ``VisionFeatures`` model.

    Args:
        image_bytes: raw image bytes (JPEG or PNG)
        prompt: instruction for what to extract from the image
    """
    import warnings
    warnings.warn(
        "analyze_image is deprecated — use "
        "ai_engine.vision.image_analyzer.analyze_travel_image instead. "
        "It is async, uses invoke_with_fallback, and returns VisionFeatures.",
        DeprecationWarning,
        stacklevel=2,
    )

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
