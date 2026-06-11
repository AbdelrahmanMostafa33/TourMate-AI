# ai_engine/__init__.py

from ai_engine.graph.graph_builder import build_trip_graph

# Guard stubs so the server doesn't crash while they're not yet implemented
try:
    from ai_engine.chat.chat_handler import handle_chat
except ImportError:
    handle_chat = None

try:
    from ai_engine.vision.image_analyzer import analyze_travel_image
except ImportError:
    analyze_travel_image = None

__all__ = [
    "build_trip_graph",
    "handle_chat",
    "analyze_travel_image",
]