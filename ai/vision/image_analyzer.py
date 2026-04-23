# ai/vision/image_analyzer.py

# ── Image Analyzer — Groq Vision (Llama 4 Scout) ────────────────────────────
#
# Entry point for the vision pipeline.
# Accepts raw image bytes, calls the Groq VLM, and returns a parsed dict.
#
# Call order:
#   image_analyzer.py  ← YOU ARE HERE
#   feature_extractor.py → validates & types the raw dict
#   multimodal_fusion.py → merges features into TripState
# ─────────────────────────────────────────────────────────────────────────────

import json
from ai.services.groq_client import analyze_image
from ai.prompts.vision_prompt import VISION_SYSTEM_PROMPT


# ── Fallback returned when VLM response is unreadable ───────────────────────
# Mirrors the "safe default" pattern used in intent_parser.py
_FALLBACK_ANALYSIS = {
    "environment_type":      "unknown",
    "travel_style":          "unknown",
    "atmosphere":            "unknown",
    "pace":                  "moderate",
    "budget_hint":           "moderate",
    "suggested_interests":   [],
    "suggested_activities":  [],
    "confidence":            0.0,
}


def analyze_travel_image(image_bytes: bytes) -> dict:
    """
    Send a user-uploaded image to Llama 4 Scout and extract travel features.

    This is the ONLY function in the vision pipeline that touches the Groq API.
    Everything downstream (feature_extractor, multimodal_fusion) works with
    the structured dict this function returns — no further API calls needed.

    Args:
        image_bytes: Raw bytes of the image (JPEG or PNG).
                     Typically read from Firebase Storage or a file upload.

    Returns:
        A dict with keys:
            environment_type, travel_style, atmosphere, pace,
            budget_hint, suggested_interests, suggested_activities, confidence

        Returns _FALLBACK_ANALYSIS if the image is empty, the API fails,
        or the response cannot be parsed as valid JSON.
    """

    # ── Guard: reject empty input immediately ────────────────────────────────
    if not image_bytes:
        print("[ImageAnalyzer] Empty image bytes received — returning fallback.")
        return _FALLBACK_ANALYSIS.copy()

    print(f"[ImageAnalyzer] Sending image to Llama 4 Scout ({len(image_bytes):,} bytes)...")

    try:
        # ── Call Groq VLM via groq_client.analyze_image() ────────────────────
        # analyze_image() encodes the bytes as base64 and builds the
        # multimodal HumanMessage internally — we only pass bytes + prompt here.
        raw_response: str = analyze_image(
            image_bytes=image_bytes,
            prompt=VISION_SYSTEM_PROMPT,
        )

        # ── Strip markdown fences the model sometimes adds ───────────────────
        # Same defensive cleaning as in intent_parser.py
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        # ── Parse JSON ───────────────────────────────────────────────────────
        result: dict = json.loads(cleaned)

        # ── Validate confidence is a float in [0, 1] ─────────────────────────
        confidence = result.get("confidence", 0.0)
        result["confidence"] = max(0.0, min(1.0, float(confidence)))

        print(
            f"[ImageAnalyzer] Analysis complete — "
            f"environment={result.get('environment_type')}, "
            f"style={result.get('travel_style')}, "
            f"confidence={result['confidence']:.2f}"
        )
        return result

    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        # VLM returned non-JSON or an unexpected format
        print(f"[ImageAnalyzer] Failed to parse VLM response: {e} — returning fallback.")
        return _FALLBACK_ANALYSIS.copy()

    except Exception as e:
        # Network error, API quota, etc.
        print(f"[ImageAnalyzer] Groq API error: {e} — returning fallback.")
        return _FALLBACK_ANALYSIS.copy()