# ai_engine/__init__.py

from ai_engine.graph.graph_builder import build_trip_graph  # ✅ now matches

# Guard stubs so the server doesn't crash while they're not yet implemented
try:
    from ai_engine.chat.chat_handler import process_chat_message
except ImportError:
    process_chat_message = None

try:
    from ai_engine.vision.image_analyzer import analyze_travel_image
except ImportError:
    analyze_travel_image = None

try:
    from ai_engine.profiling.profile_updater import update_behavioral_profile
except ImportError:
    update_behavioral_profile = None

__all__ = [
    "build_trip_graph",
    "process_chat_message",
    "analyze_travel_image",
    "update_behavioral_profile",
]