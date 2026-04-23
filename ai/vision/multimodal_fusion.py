# ai/vision/multimodal_fusion.py

# ── Multimodal Fusion — Merges Vision Features into TripState ────────────────
#
# This module is the final step of the vision pipeline.
# It takes the validated VisualFeatures and writes them into TripState so
# that every downstream agent (planner, optimizer, validator) can use the
# image context automatically — without knowing anything about vision.
#
# What it merges:
#   - image_features  → stored in state for traceability/debugging
#   - suggested_interests → appended to profile.interests (deduplicated)
#   - budget_hint     → sets profile.budget_level if profile has no value yet
#   - special_requests → enriched with a plain-text image summary
#   - agent_messages  → logs what the fusion did (for the audit trail)
#
# Call order:
#   image_analyzer.py    → raw dict from Groq
#   feature_extractor.py → validated VisualFeatures
#   multimodal_fusion.py ← YOU ARE HERE  → enriched TripState
# ─────────────────────────────────────────────────────────────────────────────

from ai.graph.state import TripState
from ai.vision.feature_extractor import VisualFeatures, features_to_text


# ── Budget hint → numeric budget_level mapping ────────────────────────────────
# Mirrors the budget scale used in BehavioralProfile (0–100 slider).
# Only applied when the profile has no budget set (budget_level is None).
_BUDGET_HINT_TO_LEVEL = {
    "budget":   25,   # budget-conscious end of the slider
    "moderate": 50,   # middle of the scale
    "luxury":   80,   # luxury end of the scale
}


def fuse_vision_into_state(state: TripState, features: VisualFeatures) -> TripState:
    """
    Merge visual features from a user-uploaded image into the shared TripState.

    This is the ONLY function that should write vision data into TripState.
    It is called from the vision_node in graph/nodes.py after the full
    image analysis pipeline (analyzer → extractor) has run.

    Merge strategy:
      1. Always store raw features in state["image_features"] for traceability.
      2. Only enrich profile and special_requests if features are reliable
         (confidence >= CONFIDENCE_THRESHOLD, i.e. is_reliable == True).
      3. Never overwrite existing profile data — only fill in gaps or append.

    Args:
        state:    The current TripState shared across all LangGraph nodes.
        features: Validated VisualFeatures from feature_extractor.extract_features().

    Returns:
        The same TripState dict with vision data merged in.
    """

    # ── 1. Always store the raw features regardless of reliability ────────────
    # This ensures the features are available for debugging and logging
    # even if they are not reliable enough to influence planning.
    state["image_features"] = dict(features)

    print(
        f"[MultimodalFusion] Merging vision features — "
        f"reliable={features.get('is_reliable')}, "
        f"confidence={features.get('confidence', 0.0):.2f}"
    )

    # ── 2. Skip enrichment for low-confidence analyses ────────────────────────
    # If the image was blurry, off-topic, or ambiguous, don't pollute the state.
    if not features.get("is_reliable"):
        print(
            "[MultimodalFusion] Confidence below threshold — "
            "image features stored but NOT applied to profile."
        )
        state["agent_messages"] = [
            "VisionFusion: image received but confidence too low to influence planning."
        ]
        return state

    # ── 3. Enrich profile interests ───────────────────────────────────────────
    # Append visual interests to the profile without duplicating existing ones.
    profile = state.get("profile") or {}
    existing_interests: list = list(profile.get("interests") or [])
    new_interests = features.get("suggested_interests", [])

    # Merge: keep existing order, append new ones that aren't already present
    merged_interests = existing_interests + [
        i for i in new_interests if i not in existing_interests
    ]

    # Write back into profile
    if profile:
        profile["interests"] = merged_interests
        state["profile"] = profile

    # ── 4. Apply budget hint to profile if budget is not already set ──────────
    # Only fills in the gap — never overwrites a value the user already gave.
    if profile and profile.get("budget_level") is None:
        budget_hint = features.get("budget_hint", "moderate")
        inferred_level = _BUDGET_HINT_TO_LEVEL.get(budget_hint, 50)
        profile["budget_level"] = inferred_level
        state["profile"] = profile
        print(
            f"[MultimodalFusion] Budget inferred from image: "
            f"'{budget_hint}' → budget_level={inferred_level}"
        )

    # ── 5. Enrich special_requests with image context ─────────────────────────
    # Converts the visual features into a readable sentence and appends it
    # to any special_requests the user already typed.
    # The planner agent will read special_requests as part of its prompt.
    image_summary = features_to_text(features)
    if image_summary:
        existing_requests = state.get("special_requests") or ""
        if existing_requests:
            # Append after a separator so both text and image hints are visible
            state["special_requests"] = f"{existing_requests}\n[From image] {image_summary}"
        else:
            state["special_requests"] = f"[From image] {image_summary}"

    # ── 6. Log what was done ──────────────────────────────────────────────────
    # agent_messages uses Annotated[List, operator.add] — append, never replace.
    fused_interests = [i for i in new_interests if i not in existing_interests]
    log_parts = [
        f"VisionFusion: applied image features "
        f"(env={features.get('environment_type')}, "
        f"style={features.get('travel_style')}, "
        f"confidence={features.get('confidence', 0.0):.2f})."
    ]
    if fused_interests:
        log_parts.append(
            f"Added interests from image: {', '.join(fused_interests)}."
        )

    state["agent_messages"] = [" ".join(log_parts)]

    print(
        f"[MultimodalFusion] Done — "
        f"interests now: {merged_interests}, "
        f"budget_level: {profile.get('budget_level') if profile else 'N/A'}"
    )
    return state


def run_vision_pipeline(state: TripState, image_bytes: bytes) -> TripState:
    """
    Convenience function that runs the full vision pipeline in one call.

    Chains: analyze_travel_image → extract_features → fuse_vision_into_state

    Used by vision_node in graph/nodes.py so the node only needs one import.

    Args:
        state:       Current TripState.
        image_bytes: Raw image bytes from the user upload.

    Returns:
        Enriched TripState with image_features written in and profile updated.
    """
    # Import here to avoid circular imports at module load time
    from ai.vision.image_analyzer import analyze_travel_image
    from ai.vision.feature_extractor import extract_features

    # Step 1 — Call Groq Vision API
    raw = analyze_travel_image(image_bytes)

    # Step 2 — Validate and type the response
    features = extract_features(raw)

    # Step 3 — Merge into TripState
    return fuse_vision_into_state(state, features)