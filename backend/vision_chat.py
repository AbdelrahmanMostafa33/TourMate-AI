"""
Interactive Chat Loop with Image Support — TourMate AI Pipeline

Extends ``chat.py`` by adding image-upload support so you can test how
uploaded images affect the conversation flow, slot filling, and itinerary
generation.

Usage:
    python vision_chat.py                                   # No image
    python vision_chat.py --image path/to/photo.jpg         # Start with image
    python vision_chat.py -i path/to/photo.jpg              # Short form

In-chat commands:
    /image <path>          — Load and analyse an image
    /features              — Show extracted image features (from last upload)
    /clear_image           — Clear the current image
    /trace                 — Show LangSmith tracing status
    /quit, /exit           — Exit the chat
    /reset                 — Start a new conversation (new session)
    /debug                 — Toggle verbose debug output
    /history               — Show conversation history
    /slots                 — Show collected trip slots
    /session               — Show session info (ID, phase, turn count)
    /export                — Export itinerary + pipeline trace to JSON file
    /usage                 — Show token usage summary
"""

import io
import sys as _sys

# ── Force UTF-8 for stdout/stderr ────────────────────────────────────────────
# Fixes UnicodeEncodeError on Windows terminals (cp1252) where emoji,
# box-drawing characters (╔═╗), and other non-ASCII chars can't be printed.
# This works for both interactive terminals and piped/redirected output.
if hasattr(_sys.stdout, "buffer"):
    _sys.stdout = io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(_sys.stderr, "buffer"):
    _sys.stderr = io.TextIOWrapper(_sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(_sys.stdin, "buffer"):
    _sys.stdin = io.TextIOWrapper(_sys.stdin.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add the current directory to sys.path to allow imports from ai_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# Load .env BEFORE any ai_engine imports so LangSmith env vars are available
from dotenv import load_dotenv
load_dotenv()

# Suppress noisy logs
logging.basicConfig(level=logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Initialize LangSmith tracing status
from ai_engine.observability import setup_langsmith, get_tracing_enabled
setup_langsmith()

from ai_engine.conversation.orchestrator import handle_chat_stream
from ai_engine.conversation.redis_memory import get_session_manager
from ai_engine.llm import token_tracker
from ai_engine.vision.image_analyzer import analyze_travel_image
from ai_engine.schemas.vision_schema import VisionFeatures


# ── Terminal colours ──────────────────────────────────────────────────────

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ── Banner ────────────────────────────────────────────────────────────────

def print_header():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════╗
║         🌍 TourMate AI — Vision-Enabled Interactive Chat     ║
║                                                              ║
║  Tell me your destination, duration, and interests —         ║
║  or upload a photo to show what you like!                    ║
║                                                              ║
║  Commands: /image /features /clear_image /trace /help        ║
╚══════════════════════════════════════════════════════════════╝{RESET}
""")


_ARROW = f"{CYAN}{BOLD}> {RESET}"


# ── Image helpers ─────────────────────────────────────────────────────────

def _load_image_bytes(path: str) -> Optional[bytes]:
    """Load image bytes from a file path. Returns None on failure."""
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            print(f"  {RED}File not found: {p}{RESET}")
            return None
        data = p.read_bytes()
        print(f"  {GREEN}✓ Loaded{RESET} {p.name} ({len(data):,} bytes)")
        return data
    except Exception as e:
        print(f"  {RED}Error loading image: {e}{RESET}")
        return None


def _print_image_features(features: VisionFeatures, label: str = "Image Features"):
    """Pretty-print extracted VisionFeatures."""
    if not features:
        print(f"  {DIM}No image features available.{RESET}")
        return

    confidence_colour = (
        GREEN if features.confidence == "high"
        else YELLOW if features.confidence == "medium"
        else RED
    )

    print(f"\n  {BOLD}{label}:{RESET}")
    print(f"  {DIM}{'─'*50}{RESET}")
    print(f"  {BOLD}Confidence:{RESET}    {confidence_colour}{features.confidence.upper()}{RESET}")
    if features.interests:
        print(f"  {BOLD}Interests:{RESET}     {', '.join(features.interests)}")
    if features.travel_style:
        print(f"  {BOLD}Travel Style:{RESET}  {features.travel_style}")
    if features.pace:
        print(f"  {BOLD}Pace:{RESET}          {features.pace}")
    if features.budget_level:
        print(f"  {BOLD}Budget:{RESET}        {features.budget_level}")
    if features.food_preferences:
        print(f"  {BOLD}Food:{RESET}          {', '.join(features.food_preferences)}")
    if features.environment_type:
        print(f"  {BOLD}Environment:{RESET}   {features.environment_type}")
    if features.vibe:
        print(f"  {BOLD}Vibe:{RESET}          {features.vibe}")
    print(f"  {DIM}{'─'*50}{RESET}")
    if features.has_signal:
        print(f"  {GREEN}→ This image provides useful travel signals!{RESET}")
    else:
        print(f"  {YELLOW}→ Low-confidence signal — image may not be clearly travel-related.{RESET}")
    print()





def _print_trace_status():
    """Show LangSmith tracing status in a readable format."""
    enabled = get_tracing_enabled()
    api_key = os.environ.get("LANGCHAIN_API_KEY", "")
    project = os.environ.get("LANGCHAIN_PROJECT", "default")

    if enabled and api_key:
        status_colour = GREEN
        status_text = "ENABLED"
        detail = f"Project: {project} | View traces at: https://smith.langchain.com"
    elif enabled and not api_key:
        status_colour = RED
        status_text = "MISCONFIGURED"
        detail = "LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY is not set."
    else:
        status_colour = YELLOW
        status_text = "DISABLED"
        detail = "Set LANGCHAIN_TRACING_V2=true + LANGCHAIN_API_KEY in .env to enable."

    print(f"\n  {BOLD}LangSmith Tracing:{RESET}  {status_colour}{status_text}{RESET}")
    print(f"  {DIM}{detail}{RESET}\n")


# ── Debug output ──────────────────────────────────────────────────────────

def print_debug(result: dict, image_features: Optional[VisionFeatures] = None):
    """Print debug info about the response."""
    print(f"\n{DIM}── Debug ──{RESET}")
    print(f"{DIM}  response_type: {result.get('response_type')}{RESET}")
    print(f"{DIM}  phase:         {result.get('phase')}{RESET}")
    print(f"{DIM}  session_id:    {result.get('session_id', 'N/A')[:16]}...{RESET}")

    # Show image_features in result
    result_img = result.get("image_features")
    if result_img:
        print(f"  {GREEN}  image_features: confidence={result_img.get('confidence', '?')}, "
              f"interests={result_img.get('interests', [])}{RESET}")
    if image_features:
        print(f"  {GREEN}  active_image:   confidence={image_features.confidence}, "
              f"interests={image_features.interests}{RESET}")

    if result.get("itinerary"):
        days = len(result["itinerary"].get("days", []))
        total_stops = sum(len(d.get("stops", [])) for d in result["itinerary"].get("days", []))
        hotels = len(result["itinerary"].get("accommodation_suggestions", []))
        print(f"{DIM}  itinerary:     {days} days, {total_stops} stops, {hotels} hotels{RESET}")
    else:
        print(f"{DIM}  itinerary:     None{RESET}")

    # Agent Pipeline Trace
    agent_messages = result.get("agent_messages", [])
    if agent_messages:
        print(f"\n{BOLD}  Pipeline Trace:{RESET}")
        for msg in agent_messages:
            if "[Vision]" in msg or "[VisionFusion]" in msg:
                color = MAGENTA
            elif "[LoadProfile]" in msg:
                color = CYAN
            elif "[PreferenceAgent]" in msg or "[Planner]" in msg:
                color = GREEN
            elif "[PlaceRetriever]" in msg or "[CandidateScorer]" in msg:
                color = YELLOW
            elif "[Optimizer]" in msg:
                color = GREEN
            elif "[Validator]" in msg:
                color = CYAN
            else:
                color = DIM
            print(f"{color}    {msg}{RESET}")

    # Validation
    validation = result.get("validation")
    if validation:
        score = validation.get("score", "?")
        is_valid = validation.get("is_valid", False)
        issue = validation.get("issue", "")
        status_color = GREEN if is_valid else RED
        print(f"\n{BOLD}  Validation:{RESET} {status_color}score={score}{RESET}")
        if issue:
            print(f"{RED}    ⚠ {issue}{RESET}")

    print(f"{DIM}{'─'*30}{RESET}")


# ── Export ────────────────────────────────────────────────────────────────

async def _handle_export(session_id: str | None, last_result: dict | None,
                         image_features: Optional[VisionFeatures] = None):
    """Export itinerary, pipeline trace, and debug info to a JSON file."""
    if not session_id:
        print(f"{RED}No active session. Start a conversation first.{RESET}")
        return

    try:
        manager = await get_session_manager()
        state = await manager.load(session_id)
    except Exception as e:
        print(f"{RED}Error loading session: {e}{RESET}")
        return

    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "session": {
            "session_id": session_id,
            "user_id": state.user_id,
            "phase": state.phase.value,
            "turn_count": state.turn_count,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
        },
        "slots": state.slots.to_dict(),
        "itinerary": state.itinerary,
        "agent_messages": (
            last_result.get("agent_messages", []) if last_result else []
        ),
        "validation": (
            last_result.get("validation") if last_result else None
        ),
        "image_features": (
            image_features.model_dump() if image_features else None
        ),
        "conversation_history": [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in (state.history or [])
        ],
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"tourmate_vision_export_{timestamp}.json"
    filepath = os.path.join(os.getcwd(), filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2, ensure_ascii=False, default=str)
        print(f"{GREEN}✅ Exported to {filepath}{RESET}")
        print(f"{DIM}   Contains: session, slots, itinerary, pipeline trace, image features{RESET}")
    except Exception as e:
        print(f"{RED}Error writing export file: {e}{RESET}")


# ── Main chat loop ────────────────────────────────────────────────────────

async def chat_loop(initial_image_path: Optional[str] = None):
    print_header()

    # Check for API key
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        try:
            from app.core.config import settings
            api_key = settings.google_api_key
        except Exception:
            api_key = None

    if not api_key:
        print(f"{RED}⚠ No API key found. Set GOOGLE_API_KEY in .env or as env var.{RESET}")
        print(f"{DIM}  You can still test general chat, but itinerary generation will fail.{RESET}\n")

    # Check Redis
    try:
        manager = await get_session_manager()
        if manager.is_connected:
            print(f"{GREEN}✓ Redis connected{RESET}")
        else:
            print(f"{YELLOW}⚠ Redis not connected — sessions won't persist between restarts{RESET}")
    except Exception as e:
        print(f"{YELLOW}⚠ Redis error: {e}{RESET}")

    # Show LangSmith trace status
    _print_trace_status()

    user_id = "interactive_user"
    session_id = None
    debug_mode = False
    turn = 0
    last_result = None
    current_image_bytes: Optional[bytes] = None
    current_image_features: Optional[VisionFeatures] = None

    # ── Load initial image if provided ──────────────────────────────────
    auto_proceed_image = False  # flag for auto-sending after /image command

    if initial_image_path:
        current_image_bytes = _load_image_bytes(initial_image_path)
        if current_image_bytes:
            print(f"\n  {YELLOW}Analysing initial image...{RESET}")
            current_image_features = await analyze_travel_image(current_image_bytes)
            _print_image_features(current_image_features, "Initial Image Analysis")
            print(f"  {DIM}Image will be sent with your first message.{RESET}\n")

    # ── Check for existing session to resume ────────────────────────────
    try:
        state = await manager.get_active_session(user_id)
        if state and state.turn_count > 0:
            slots = state.slots
            has_data = any([
                slots.destination_city,
                slots.duration_days,
                slots.budget_level,
                slots.travel_style,
                slots.interests,
            ])
            if has_data:
                session_id = state.session_id
                turn = state.turn_count
                print(f"\n{YELLOW}{BOLD}↻ Resuming previous session{RESET}")
                print(f"{DIM}  session: {session_id[:16]}... | phase: {state.phase.value} | turn: {turn}{RESET}")

                if slots.destination_city:
                    dur = f" ({slots.duration_days} days)" if slots.duration_days else ""
                    print(f"  📍 Destination: {slots.destination_city}{dur}")
                if slots.budget_level:
                    print(f"  💰 Budget:      {slots.budget_level}")
                if slots.travel_style:
                    print(f"  🎯 Style:       {slots.travel_style}")
                if slots.interests:
                    print(f"  🎨 Interests:   {', '.join(slots.interests[:5])}")
                if slots.food_preferences:
                    print(f"  🍽️  Food:        {', '.join(slots.food_preferences[:3])}")

                missing = slots.missing_required()
                if missing:
                    print(f"{YELLOW}  ⚠ Still need: {', '.join(missing)}{RESET}")
                elif state.phase in ("plan_generation", "itinerary_review", "completed"):
                    print(f"{GREEN}  ✅ All trip info collected — ready to generate/modify!{RESET}")
                else:
                    print(f"{GREEN}  ✅ All required info collected{RESET}")

                print(f"{DIM}  Type /reset to start fresh /history to see full history{RESET}\n")
    except Exception:
        pass

    print(f"{DIM}Start chatting! (Type /help for commands){RESET}\n")
    if current_image_features:
        print(f"{GREEN}📷 Image loaded — will be sent with next message.{RESET}\n")

    while True:
        try:
            user_input = await asyncio.get_running_loop().run_in_executor(
                None, lambda: input(f"{GREEN}{BOLD}You ▸ {RESET}")
            )
        except (EOFError, KeyboardInterrupt):
            token_tracker.print_summary()
            print(f"\n{DIM}Goodbye! 👋{RESET}")
            break

        user_input = user_input.strip()

        # Allow empty input only when auto-proceeding with a freshly loaded image
        if not user_input and not auto_proceed_image:
            continue

        # ── Handle commands ────────────────────────────────────────────
        cmd = user_input.lower()

        if cmd in ("/quit", "/exit", "/q"):
            token_tracker.print_summary()
            print(f"{DIM}Goodbye! 👋{RESET}")
            break

        elif cmd == "/reset":
            session_id = None
            turn = 0
            current_image_bytes = None
            current_image_features = None
            print(f"{YELLOW}🔄 Session reset. Starting fresh conversation.{RESET}\n")
            continue

        elif cmd == "/debug":
            debug_mode = not debug_mode
            status = f"{GREEN}ON{RESET}" if debug_mode else f"{RED}OFF{RESET}"
            print(f"{YELLOW}🔧 Debug mode: {status}{RESET}\n")
            continue

        elif cmd == "/history":
            if session_id:
                try:
                    manager = await get_session_manager()
                    state = await manager.load(session_id)
                    if state and state.history:
                        print(f"\n{DIM}── Conversation History ({len(state.history)} messages) ──{RESET}")
                        for msg in state.history[-10:]:
                            role_color = GREEN if msg.role == "user" else CYAN
                            print(f"  {role_color}[{msg.role}]{RESET} {msg.content[:100]}")
                        print(f"{DIM}{'─'*40}{RESET}\n")
                    else:
                        print(f"{DIM}No history yet.{RESET}\n")
                except Exception as e:
                    print(f"{RED}Error loading history: {e}{RESET}\n")
            else:
                print(f"{DIM}No active session yet.{RESET}\n")
            continue

        elif cmd == "/slots":
            if session_id:
                try:
                    manager = await get_session_manager()
                    state = await manager.load(session_id)
                    if state:
                        slots = state.slots
                        print(f"\n{DIM}── Trip Slots ──{RESET}")
                        print(f"  destination:     {slots.destination_city or '—'}")
                        print(f"  duration:        {slots.duration_days or '—'} days")
                        print(f"  budget:          {slots.budget_level or '—'}")
                        print(f"  style:           {slots.travel_style or '—'}")
                        print(f"  pace:            {slots.pace or '—'}")
                        print(f"  interests:       {', '.join(slots.interests) if slots.interests else '—'}")
                        print(f"  food:            {', '.join(slots.food_preferences) if slots.food_preferences else '—'}")
                        print(f"  accommodation:   {', '.join(slots.accommodation_preferences) if slots.accommodation_preferences else '—'}")
                        missing = slots.missing_required()
                        status = f"{GREEN}COMPLETE ✓{RESET}" if not missing else f"{YELLOW}Missing: {', '.join(missing)}{RESET}"
                        print(f"  status:          {status}")
                        print(f"{DIM}{'─'*40}{RESET}\n")
                    else:
                        print(f"{DIM}No session data.{RESET}\n")
                except Exception as e:
                    print(f"{RED}Error loading slots: {e}{RESET}\n")
            else:
                print(f"{DIM}No active session yet.{RESET}\n")
            continue

        elif cmd == "/session":
            if session_id:
                try:
                    manager = await get_session_manager()
                    state = await manager.load(session_id)
                    if state:
                        print(f"\n{DIM}── Session Info ──{RESET}")
                        print(f"  session_id:  {state.session_id}")
                        print(f"  phase:       {state.phase.value}")
                        print(f"  turn_count:  {state.turn_count}")
                        print(f"  created_at:  {state.created_at[:19]}")
                        print(f"  updated_at:  {state.updated_at[:19]}")
                        print(f"{DIM}{'─'*40}{RESET}\n")
                    else:
                        print(f"{DIM}Session not found in Redis.{RESET}\n")
                except Exception as e:
                    print(f"{RED}Error: {e}{RESET}\n")
            else:
                print(f"{DIM}No active session yet.{RESET}\n")
            continue

        elif cmd == "/export":
            await _handle_export(session_id, last_result, current_image_features)
            continue

        elif cmd == "/usage":
            token_tracker.print_summary()
            continue

        elif cmd == "/features":
            if current_image_features:
                _print_image_features(current_image_features, "Current Image Features")
            else:
                print(f"{YELLOW}No image loaded. Use /image <path> to load one.{RESET}\n")
            continue

        elif cmd == "/clear_image":
            if current_image_bytes or current_image_features:
                current_image_bytes = None
                current_image_features = None
                print(f"{YELLOW}📷 Image cleared.{RESET}\n")
            else:
                print(f"{DIM}No image to clear.{RESET}\n")
            continue

        elif cmd == "/trace":
            _print_trace_status()
            continue

        elif cmd.startswith("/image "):
            img_path = user_input[7:].strip()
            if not img_path:
                print(f"{RED}Usage: /image <path-to-image>{RESET}\n")
                continue
            new_bytes = _load_image_bytes(img_path)
            if new_bytes:
                print(f"  {YELLOW}Analysing image...{RESET}")
                current_image_features = await analyze_travel_image(new_bytes)
                current_image_bytes = new_bytes
                _print_image_features(current_image_features, "Image Analysis")
                # Auto-proceed: send image to AI immediately without waiting
                # for another text message.
                if current_image_features and current_image_features.has_signal:
                    img_interests = current_image_features.interests or []
                    interest_str = ", ".join(img_interests[:4])
                    print(f"  {GREEN}📷 I can see you're interested in "
                          f"{interest_str}. Processing your photo...{RESET}\n")
                    auto_proceed_image = True
                    user_input = ""  # _prepare_message will auto-generate description
                    # Don't continue — fall through to message sending
                else:
                    print(f"  {YELLOW}⚠ Low-confidence image — "
                          f"will be sent with your next message.{RESET}\n")
                    continue
            else:
                continue

        elif cmd in ("/help", "/h", "?"):
            print(f"""
{BOLD}Vision-Specific Commands:{RESET}
  /image <path>      Load and analyse an image from file.
                     Use this when the AI asks about your interests —
                     upload a photo instead of typing them!
  /features          Show extracted image features from the last upload
  /clear_image       Clear the currently loaded image
  /trace             Show LangSmith tracing status

{BOLD}Standard Commands:{RESET}
  /quit, /exit       Exit the chat
  /reset             Start a new conversation
  /debug             Toggle verbose debug output
  /history           Show conversation history
  /slots             Show collected trip slots
  /session           Show session info (ID, phase, turns)
  /export            Export itinerary + trace to JSON file
  /usage             Show token usage summary
  /help              Show this help message

{BOLD}Tip:{RESET} When the AI asks "What are your interests?", you can either:
  • Type them:  history, food, architecture
  • Upload a photo:  /image path/to/photo.jpg
  • Skip:  no preference  (the AI will proceed with defaults)
""")
            continue

        # ── Detect if the input looks like a file path instead of /image ─
        # Only checks inputs that weren't caught by the command chain above.
        _IS_IMG_PATH = any(user_input.lower().endswith(ext) for ext in
                          (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))
        if _IS_IMG_PATH:
            if cmd.startswith("/") and not cmd.startswith("/image "):
                # Unrecognized /command that looks like a file path
                print(f"  {YELLOW}💡 To upload a photo, use {BOLD}/image <path>{RESET}")
                print(f"     Example: {BOLD}/image {user_input.lstrip('/')}{RESET}\n")
                continue
            elif not cmd.startswith("/"):
                # Plain text that looks like a file path
                print(f"  {YELLOW}💡 Tip: You can upload photos with {BOLD}/image <path>{RESET}")
                print(f"     Example: {BOLD}/image {user_input}{RESET}\n")

        # ── Send message to AI (streaming) ────────────────────────────
        turn += 1
        print(f"{DIM}(Turn {turn}){RESET}")

        text_printed = False
        last_result = None

        # Show image context only once — right after the image was loaded
        # and sent to the AI. Skip on subsequent turns (auto_proceed_image
        # is False but current_image_bytes was already cleared).
        if current_image_features and current_image_features.has_signal \
                and not auto_proceed_image and current_image_bytes is not None:
            print(f"{MAGENTA}  📷 Including image analysis: "
                  f"interests={current_image_features.interests}, "
                  f"style={current_image_features.travel_style}, "
                  f"pace={current_image_features.pace}{RESET}")

        try:
            streamed_text = ""
            async for chunk in handle_chat_stream(
                user_id=user_id,
                user_message=user_input,
                image_bytes=current_image_bytes,
                session_id=session_id,
            ):
                event_type = chunk.get("type")

                if event_type == "session":
                    session_id = chunk["data"]["session_id"]

                elif event_type == "progress":
                    msg = chunk["data"].get("message", "")
                    print(f"  {YELLOW}⏳ {msg}{RESET}")

                elif event_type == "phase":
                    new_phase = chunk["data"].get("phase")
                    if debug_mode:
                        print(f"  {DIM}→ Phase: {new_phase}{RESET}")

                elif event_type == "text":
                    if not text_printed:
                        print(f"\n{_ARROW}", end="", flush=True)
                        text_printed = True
                    content = chunk.get("content", "")
                    streamed_text += content
                    print(content, end="", flush=True)

                elif event_type == "result":
                    last_result = chunk.get("data")
                    # Show image features from the result if present
                    result_img = last_result.get("image_features") if last_result else None
                    if result_img and result_img.has_signal and debug_mode:
                        print(f"\n  {MAGENTA}[Result includes image features: "
                              f"confidence={result_img.confidence}]{RESET}")

                elif event_type == "done":
                    if text_printed:
                        print()  # newline after streaming

            # ── Suggest /image if the AI asked about interests ────────
            if streamed_text and not current_image_bytes and (
                "your interests" in streamed_text.lower() or
                any(kw in streamed_text.lower() for kw in (
                    "upload a photo", "upload an image",
                    "no preference", "surprise me",
                ))
            ):
                print(f"\n  {DIM}💡 Tip: You can also upload a photo instead of typing!")
                print(f"     Use {BOLD}/image <path>{RESET}{DIM} to show what you like.{RESET}\n")

        except Exception as e:
            print(f"\n{RED}Error: {e}{RESET}\n")
            continue

        # Reset auto-proceed flag after sending and clear image bytes so the
        # "Including image analysis" message isn't shown on every subsequent turn.
        # The image features have already been fused into the conversation state.
        # Keep current_image_features so /features command still works.
        auto_proceed_image = False
        current_image_bytes = None

        # Debug output
        if debug_mode and last_result:
            print_debug(last_result, current_image_features)

    # Cleanup
    try:
        manager = await get_session_manager()
        await manager.close()
    except Exception:
        pass


# ── CLI entry point ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="TourMate AI — Vision-Enabled Interactive Chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vision_chat.py
  python vision_chat.py --image my_photo.jpg
  python vision_chat.py -i ~/Pictures/beach.jpg
        """
    )
    parser.add_argument(
        "-i", "--image",
        type=str,
        default=None,
        help="Path to an image file to analyse at startup"
    )

    args = parser.parse_args()

    try:
        asyncio.run(chat_loop(initial_image_path=args.image))
    except KeyboardInterrupt:
        print(f"\n{DIM}Goodbye! 👋{RESET}")


if __name__ == "__main__":
    main()
