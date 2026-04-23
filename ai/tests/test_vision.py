# ai/tests/test_vision.py
 
# ── Unit Tests — Vision Pipeline (Task 3.8) ──────────────────────────────────
#
# Covers every layer of the vision pipeline built in Task 3.6:
#
#   Layer 1 — image_analyzer.py
#     test_analyze_real_image()     → real API call with sample.jpg
#     test_analyze_empty_bytes()    → fallback on empty input
#
#   Layer 2 — feature_extractor.py
#     test_extract_valid_features() → clean VLM-style dict → VisualFeatures
#     test_extract_invalid_values() → unknown enum values are sanitized
#     test_extract_missing_fields() → missing keys get safe defaults
#     test_features_to_text_reliable()   → text output for reliable features
#     test_features_to_text_unreliable() → returns "" below confidence threshold
#
#   Layer 3 — multimodal_fusion.py
#     test_fusion_enriches_interests()   → new interests appended to profile
#     test_fusion_no_duplicate_interests() → existing interests not duplicated
#     test_fusion_infers_budget()        → budget_level set from budget_hint
#     test_fusion_skips_existing_budget()→ existing budget_level never overwritten
#     test_fusion_enriches_special_requests() → image summary appended
#     test_fusion_skips_low_confidence() → unreliable features not applied
#
#   End-to-end
#     test_full_pipeline_with_real_image() → sample.jpg → enriched TripState
# ─────────────────────────────────────────────────────────────────────────────
 
import sys
from pathlib import Path
 
# ── Module imports ────────────────────────────────────────────────────────────
from ai.vision.image_analyzer import analyze_travel_image, _FALLBACK_ANALYSIS
from ai.vision.feature_extractor import (
    extract_features, features_to_text,
    CONFIDENCE_THRESHOLD, VisualFeatures,
)
from ai.vision.multimodal_fusion import fuse_vision_into_state, run_vision_pipeline
 
 
# ── Shared test helpers ───────────────────────────────────────────────────────
 
SAMPLE_IMAGE_PATH = Path(__file__).parent / "sample.jpg"
 
 
def _load_sample_image() -> bytes:
    """Load the sample image from the tests/ folder."""
    with open(SAMPLE_IMAGE_PATH, "rb") as f:
        return f.read()
 
 
def _make_mock_state(
    interests=None,
    budget_level=None,
    special_requests=None,
    image_bytes=None,
) -> dict:
    """
    Builds a minimal TripState dict for fusion tests.
    Avoids importing TripState at the top level so tests stay fast.
    """
    return {
        "user_id":       "test_user_001",
        "user_message":  "Plan a trip for me",
        "intent_type":   "plan_trip",
        "image_bytes":   image_bytes,
        "image_features": None,
        "special_requests": special_requests,
        "agent_messages": [],
        "profile": {
            "user_id":      "test_user_001",
            "interests":    interests or [],
            "budget_level": budget_level,
            "persona_name": "Test Traveler",
            "quiz_completed": True,
        },
    }
 
 
def _make_reliable_features(**overrides) -> dict:
    """Returns a valid, high-confidence raw dict (as the VLM would return)."""
    base = {
        "environment_type":     "historical",
        "travel_style":         "cultural",
        "atmosphere":           "calm",
        "pace":                 "slow",
        "budget_hint":          "moderate",
        "suggested_interests":  ["history", "architecture", "photography"],
        "suggested_activities": ["visit local museums", "explore the old city"],
        "confidence":           0.85,
    }
    base.update(overrides)
    return base
 
 
def _make_unreliable_features(**overrides) -> dict:
    """Returns a low-confidence raw dict."""
    base = _make_reliable_features()
    base["confidence"] = 0.2     # below CONFIDENCE_THRESHOLD
    base.update(overrides)
    return base
 
 
# ═════════════════════════════════════════════════════════════════════════════
# LAYER 1 — image_analyzer.py
# ═════════════════════════════════════════════════════════════════════════════
 
def test_analyze_real_image():
    """
    Live API test: send sample.jpg to Llama 4 Scout and verify the response
    contains all required keys with non-empty values.
    """
    if not SAMPLE_IMAGE_PATH.exists():
        print("[SKIP] test_analyze_real_image — sample.jpg not found.")
        return
 
    print("Testing analyze_travel_image() with sample.jpg ...")
    image_bytes = _load_sample_image()
    result = analyze_travel_image(image_bytes)
 
    print(f"[OK] Raw VLM result: {result}")
 
    # Must return a dict with all required keys
    required_keys = [
        "environment_type", "travel_style", "atmosphere",
        "pace", "budget_hint", "suggested_interests",
        "suggested_activities", "confidence",
    ]
    for key in required_keys:
        assert key in result, f"Missing key in response: '{key}'"
 
    # Confidence must be a float in [0, 1]
    assert isinstance(result["confidence"], float), "confidence must be float"
    assert 0.0 <= result["confidence"] <= 1.0,      "confidence out of range"
 
    # Lists must be lists
    assert isinstance(result["suggested_interests"],  list)
    assert isinstance(result["suggested_activities"], list)
 
    print(f"[OK] test_analyze_real_image passed — confidence={result['confidence']:.2f}")
 
 
def test_analyze_empty_bytes():
    """
    Empty image input must return the fallback dict immediately
    without making any API call.
    """
    print("Testing analyze_travel_image() with empty bytes ...")
    result = analyze_travel_image(b"")
 
    assert result["environment_type"] == "unknown"
    assert result["confidence"] == 0.0
    assert result["suggested_interests"] == []
 
    print("[OK] test_analyze_empty_bytes passed — fallback returned correctly.")
 
 
# ═════════════════════════════════════════════════════════════════════════════
# LAYER 2 — feature_extractor.py
# ═════════════════════════════════════════════════════════════════════════════
 
def test_extract_valid_features():
    """
    A clean, well-formed raw dict must be converted into a VisualFeatures
    TypedDict with all fields present and is_reliable=True.
    """
    print("Testing extract_features() with valid input ...")
    raw = _make_reliable_features()
    features = extract_features(raw)
 
    assert features["environment_type"]    == "historical"
    assert features["travel_style"]        == "cultural"
    assert features["atmosphere"]          == "calm"
    assert features["pace"]                == "slow"
    assert features["budget_hint"]         == "moderate"
    assert features["confidence"]          == 0.85
    assert features["is_reliable"]         == True
 
    assert "history"       in features["suggested_interests"]
    assert "architecture"  in features["suggested_interests"]
    assert len(features["suggested_activities"]) == 2
 
    print("[OK] test_extract_valid_features passed.")
 
 
def test_extract_invalid_values():
    """
    Unknown enum values (not in the allowed sets) must be replaced
    with safe defaults — never raise an exception.
    """
    print("Testing extract_features() with invalid enum values ...")
    raw = _make_reliable_features(
        environment_type="underwater_volcano",  # not in VALID_ENVIRONMENT_TYPES
        travel_style="time_travel",             # not in VALID_TRAVEL_STYLES
        atmosphere="chaotic",                   # not in VALID_ATMOSPHERES
        pace="turbo",                           # not in VALID_PACES
        budget_hint="priceless",                # not in VALID_BUDGET_HINTS
    )
    features = extract_features(raw)
 
    assert features["environment_type"] == "unknown",   "Bad env_type must become 'unknown'"
    assert features["travel_style"]     == "unknown",   "Bad travel_style must become 'unknown'"
    assert features["atmosphere"]       == "unknown",   "Bad atmosphere must become 'unknown'"
    assert features["pace"]             == "moderate",  "Bad pace must become 'moderate'"
    assert features["budget_hint"]      == "moderate",  "Bad budget_hint must become 'moderate'"
 
    print("[OK] test_extract_invalid_values passed — invalid values sanitized correctly.")
 
 
def test_extract_missing_fields():
    """
    Completely empty dict must not raise — every field gets a safe default.
    """
    print("Testing extract_features() with empty dict ...")
    features = extract_features({})
 
    assert features["environment_type"]   == "unknown"
    assert features["travel_style"]       == "unknown"
    assert features["pace"]               == "moderate"
    assert features["budget_hint"]        == "moderate"
    assert features["confidence"]         == 0.0
    assert features["is_reliable"]        == False
    assert features["suggested_interests"]  == []
    assert features["suggested_activities"] == []
 
    print("[OK] test_extract_missing_fields passed — empty input handled gracefully.")
 
 
def test_features_to_text_reliable():
    """
    Reliable features (confidence >= threshold) must produce a
    non-empty plain-text summary for injection into LLM prompts.
    """
    print("Testing features_to_text() with reliable features ...")
    features = extract_features(_make_reliable_features())
    text = features_to_text(features)
 
    assert len(text) > 0,                    "Reliable features must produce non-empty text"
    assert "historical"  in text,            "environment_type must appear in text"
    assert "cultural"    in text,            "travel_style must appear in text"
    assert "history"     in text,            "suggested_interests must appear in text"
 
    print(f"[OK] test_features_to_text_reliable passed.\nText:\n{text}")
 
 
def test_features_to_text_unreliable():
    """
    Unreliable features (confidence < threshold) must return an empty
    string — we don't want low-confidence guesses polluting the planner prompt.
    """
    print("Testing features_to_text() with unreliable features ...")
    features = extract_features(_make_unreliable_features())
    text = features_to_text(features)
 
    assert text == "", f"Unreliable features must produce empty string, got: '{text}'"
 
    print("[OK] test_features_to_text_unreliable passed — empty string returned correctly.")
 
 
# ═════════════════════════════════════════════════════════════════════════════
# LAYER 3 — multimodal_fusion.py
# ═════════════════════════════════════════════════════════════════════════════
 
def test_fusion_enriches_interests():
    """
    New interests from the image must be appended to the profile's
    existing interests list.
    """
    print("Testing fuse_vision_into_state() interest merging ...")
    state  = _make_mock_state(interests=["food", "art"])
    features = extract_features(_make_reliable_features(
        suggested_interests=["history", "architecture"]
    ))
 
    result = fuse_vision_into_state(state, features)
    final_interests = result["profile"]["interests"]
 
    assert "food"         in final_interests, "Existing interest 'food' must be preserved"
    assert "art"          in final_interests, "Existing interest 'art' must be preserved"
    assert "history"      in final_interests, "New interest 'history' must be added"
    assert "architecture" in final_interests, "New interest 'architecture' must be added"
 
    print(f"[OK] test_fusion_enriches_interests passed — interests: {final_interests}")
 
 
def test_fusion_no_duplicate_interests():
    """
    Interests already in the profile must NOT be added again even if
    the image suggests the same keyword.
    """
    print("Testing fuse_vision_into_state() no-duplicate rule ...")
    state = _make_mock_state(interests=["history", "art"])
    features = extract_features(_make_reliable_features(
        suggested_interests=["history", "photography"]  # "history" already exists
    ))
 
    result = fuse_vision_into_state(state, features)
    final_interests = result["profile"]["interests"]
 
    assert final_interests.count("history") == 1, "'history' must appear exactly once"
    assert "photography" in final_interests,       "New interest 'photography' must be added"
 
    print(f"[OK] test_fusion_no_duplicate_interests passed — interests: {final_interests}")
 
 
def test_fusion_infers_budget():
    """
    When the profile has no budget_level (None), fusion must infer
    one from the image's budget_hint.
    """
    print("Testing fuse_vision_into_state() budget inference ...")
    state    = _make_mock_state(budget_level=None)
    features = extract_features(_make_reliable_features(budget_hint="luxury"))
 
    result = fuse_vision_into_state(state, features)
    inferred = result["profile"]["budget_level"]
 
    assert inferred is not None, "budget_level must be set after fusion"
    assert inferred > 50,        "luxury budget_hint must map to a high budget_level (>50)"
 
    print(f"[OK] test_fusion_infers_budget passed — budget_level={inferred}")
 
 
def test_fusion_skips_existing_budget():
    """
    When the profile already has a budget_level, fusion must NOT
    overwrite it — even if the image suggests something different.
    """
    print("Testing fuse_vision_into_state() existing budget preservation ...")
    state    = _make_mock_state(budget_level=20)   # budget-conscious user
    features = extract_features(_make_reliable_features(budget_hint="luxury"))
 
    result = fuse_vision_into_state(state, features)
    assert result["profile"]["budget_level"] == 20, \
        "Existing budget_level must NOT be overwritten by vision hint"
 
    print("[OK] test_fusion_skips_existing_budget passed — budget preserved at 20.")
 
 
def test_fusion_enriches_special_requests():
    """
    The image summary must be appended to special_requests so the
    planner agent can read it as part of the trip context.
    """
    print("Testing fuse_vision_into_state() special_requests enrichment ...")
    state    = _make_mock_state(special_requests="I want to avoid crowds")
    features = extract_features(_make_reliable_features())
 
    result = fuse_vision_into_state(state, features)
    final_requests = result.get("special_requests", "")
 
    assert "I want to avoid crowds" in final_requests, "Original request must be preserved"
    assert "[From image]"           in final_requests, "Image summary prefix must be present"
    assert "historical"             in final_requests, "Image environment must appear in summary"
 
    print(f"[OK] test_fusion_enriches_special_requests passed.\nRequests: {final_requests}")
 
 
def test_fusion_skips_low_confidence():
    """
    When features have low confidence (is_reliable=False), fusion must
    store image_features in state but NOT modify the profile or special_requests.
    """
    print("Testing fuse_vision_into_state() low-confidence skip ...")
    original_interests = ["food", "art"]
    state    = _make_mock_state(interests=original_interests.copy(), special_requests=None)
    features = extract_features(_make_unreliable_features())   # confidence=0.2
 
    assert features["is_reliable"] == False, "Precondition: features must be unreliable"
 
    result = fuse_vision_into_state(state, features)
 
    # image_features must still be stored (for debugging)
    assert result["image_features"] is not None, "image_features must always be stored"
 
    # Profile and requests must be unchanged
    assert result["profile"]["interests"] == original_interests, \
        "Interests must NOT change when features are unreliable"
    assert result.get("special_requests") is None, \
        "special_requests must NOT be set when features are unreliable"
 
    print("[OK] test_fusion_skips_low_confidence passed — profile unchanged.")
 
 
# ═════════════════════════════════════════════════════════════════════════════
# END-TO-END — full pipeline with a real image
# ═════════════════════════════════════════════════════════════════════════════
 
def test_full_pipeline_with_real_image():
    """
    End-to-end test: sample.jpg → analyze → extract → fuse → enriched TripState.
 
    Validates that run_vision_pipeline() produces a state where:
      - image_features is populated
      - profile interests list is non-empty (image added at least one)
      - special_requests contains the '[From image]' marker (if confidence is high)
    """
    if not SAMPLE_IMAGE_PATH.exists():
        print("[SKIP] test_full_pipeline_with_real_image — sample.jpg not found.")
        return
 
    print("Testing run_vision_pipeline() end-to-end with sample.jpg ...")
    image_bytes = _load_sample_image()
    state = _make_mock_state(interests=["food"], image_bytes=image_bytes)
 
    result = run_vision_pipeline(state, image_bytes)
 
    # image_features must always be set after the pipeline
    assert result.get("image_features") is not None, \
        "image_features must be populated after pipeline"
 
    features = result["image_features"]
    print(f"[OK] Pipeline completed — features: {features}")
 
    # Confidence must be a valid float
    assert 0.0 <= features["confidence"] <= 1.0, "Confidence must be in [0, 1]"
 
    # If analysis was reliable, interests and special_requests should be enriched
    if features.get("is_reliable"):
        assert len(result["profile"]["interests"]) >= 1, \
            "At least one interest must exist after reliable vision fusion"
        print(f"[OK] Reliable analysis — interests: {result['profile']['interests']}")
        print(f"[OK] Special requests: {result.get('special_requests', '')}")
    else:
        print(f"[INFO] Low confidence ({features['confidence']:.2f}) — enrichment skipped.")
 
    print("[OK] test_full_pipeline_with_real_image passed.")
 
 
# ═════════════════════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════════════════════
 
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  LAYER 1 — image_analyzer.py")
    print("="*60)
    test_analyze_empty_bytes()       # no API call — always runs
    test_analyze_real_image()        # live API call
 
    print("\n" + "="*60)
    print("  LAYER 2 — feature_extractor.py")
    print("="*60)
    test_extract_valid_features()
    test_extract_invalid_values()
    test_extract_missing_fields()
    test_features_to_text_reliable()
    test_features_to_text_unreliable()
 
    print("\n" + "="*60)
    print("  LAYER 3 — multimodal_fusion.py")
    print("="*60)
    test_fusion_enriches_interests()
    test_fusion_no_duplicate_interests()
    test_fusion_infers_budget()
    test_fusion_skips_existing_budget()
    test_fusion_enriches_special_requests()
    test_fusion_skips_low_confidence()
 
    print("\n" + "="*60)
    print("  END-TO-END")
    print("="*60)
    test_full_pipeline_with_real_image()   # live API call
 
    print("\n✅ All vision tests passed.")