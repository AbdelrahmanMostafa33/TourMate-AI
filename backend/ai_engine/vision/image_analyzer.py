# backend/ai_engine/vision/image_analyzer.py
"""Multimodal image analysis — extracts travel preferences from user-uploaded images.

Uses ``invoke_with_fallback`` (``ai_engine.llm.invoke``) with the ``vision``
agent role, which resolves to **Gemini 2.5 Flash** via the shared LLM registry.

This module implements FR #08 — multimodal input support.
"""

from __future__ import annotations

import json
import logging

import base64
from langchain_core.messages import HumanMessage

from ai_engine.llm.invoke import invoke_with_fallback
from ai_engine.prompts.vision_prompt import VISION_EXTRACTION_PROMPT
from ai_engine.schemas.vision_schema import VisionFeatures
from ai_engine.tools.json_utils import extract_json_from_llm_output
from ai_engine.vision.feature_extractor import extract_and_validate

from ai_engine.observability import traced

logger = logging.getLogger(__name__)


@traced(name="vision_analyze_image", tags=["vision", "image_analysis"], metadata={"component": "image_analyzer"})
async def analyze_travel_image(image_bytes: bytes) -> VisionFeatures:
    """Analyse a travel-related image and extract structured preferences.

    Sends the image to Gemini 2.5 Flash via ``invoke_with_fallback`` (which
    handles key rotation, rate-limit backoff, and transient-error retry) and
    returns a validated ``VisionFeatures`` instance.

    The caller (orchestrator) merges the result into the user's trip profile
    via ``multimodal_fusion.fuse_image_with_profile()`` before the itinerary
    pipeline runs.

    Args:
        image_bytes: Raw image bytes (JPEG or PNG) from the upload request.

    Returns:
        A validated ``VisionFeatures`` model.  On any failure, returns the
        zero-signal fallback (``confidence="low"``) so the chat flow never
        crashes because of a bad image.
    """
    try:
        raw_response: str = await _call_vision_llm(image_bytes)

        # Extract JSON from LLM output (handles preamble, markdown fences,
        # trailing commentary).
        cleaned = extract_json_from_llm_output(raw_response)
        parsed = json.loads(cleaned)
        return extract_and_validate(parsed)

    except (json.JSONDecodeError, ValueError, AttributeError, Exception) as exc:
        logger.warning(
            "[Vision] Image analysis failed (falling back to low-confidence): %s",
            exc,
        )
        return VisionFeatures.fallback()


async def _call_vision_llm(image_bytes: bytes) -> str:
    """Build a multimodal message and invoke the vision LLM.

    Uses ``invoke_with_fallback`` so the call is automatically retried across
    available API keys with exponential backoff on transients.
    """
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

    response = await invoke_with_fallback(
        agent_role="vision",
        messages=[message],
    )
    return response.content