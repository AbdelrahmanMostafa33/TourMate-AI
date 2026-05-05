# backend/ai_engine/vision/image_analyzer.py

import json

from app.external.groq_client import analyze_image
from ai_engine.prompts.vision_prompt import VISION_EXTRACTION_PROMPT
from ai_engine.vision.feature_extractor import extract_and_validate


def analyze_travel_image(image_bytes: bytes) -> dict:
    """
    Sends an image to Llama 4 Scout (Groq Vision) and extracts
    structured travel preference features.

    This implements FR #08 — multimodal input support.
    Users can upload a travel-style image (e.g., a beach photo,
    a busy market) and the system infers their preferences from it
    without requiring any explicit text input.

    The extracted features are later merged into the user's behavioral
    profile via multimodal_fusion.py before the itinerary pipeline runs.

    Args:
        image_bytes: Raw image bytes (JPEG or PNG). Comes from Firebase
                     Storage download or direct upload in the request.

    Returns:
        A validated feature dict:
            {
                "environment_type": "urban" | "nature" | ... | None,
                "activity_style":   "relaxing" | "adventurous" | ... | None,
                "vibe":             str | None,
                "inferred_interests": list[str],
                "confidence":       "high" | "medium" | "low"
            }
        On any failure, returns the safe fallback (all None/empty, confidence "low").
    """
    try:
        # Call Llama 4 Scout via the already-built groq_client helper.
        # analyze_image() handles base64 encoding internally.
        raw_response: str = analyze_image(image_bytes, VISION_EXTRACTION_PROMPT)

        # Strip markdown fences — same defensive pattern as intent_parser.py
        cleaned = raw_response.strip().strip("```json").strip("```").strip()

        parsed = json.loads(cleaned)
        return extract_and_validate(parsed)

    except (json.JSONDecodeError, ValueError, AttributeError, Exception):
        # Never crash the chat flow because of a bad image.
        # Return a low-confidence empty result — the pipeline continues
        # without image features.
        return _safe_fallback()


def _safe_fallback() -> dict:
    """Returns a zero-signal feature dict used when extraction fails."""
    return {
        "environment_type":   None,
        "activity_style":     None,
        "vibe":               None,
        "inferred_interests": [],
        "confidence":         "low",
    }