# app/external/groq_client.py — DEPRECATED, kept for backward compatibility.
# Use app.external.llm_client instead (now powered by Gemini).

from app.external.llm_client import (
    get_planning_llm,
    get_fast_llm,
    get_vision_llm,
    analyze_image,
)

__all__ = ["get_planning_llm", "get_fast_llm", "get_vision_llm", "analyze_image"]
