"""Interactive Chat Loop for TourMate AI Pipeline

Usage:
    python chat.py

Commands:
    /quit, /exit   — Exit the chat
    /reset          — Start a new conversation (new session)
    /debug          — Toggle verbose debug output
    /history        — Show conversation history
    /slots          — Show collected trip slots
    /session        — Show session info (ID, phase, turn count)
    /export         — Export itinerary + pipeline trace to JSON file
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

# Add the current directory to sys.path to allow imports from ai_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# Load .env BEFORE any ai_engine imports so LangSmith env vars are available
# when @traced decorators are applied at import time.
from dotenv import load_dotenv
load_dotenv()

# Suppress noisy SQLAlchemy engine query logs from cluttering chat output.
# Use basicConfig at WARNING so all INFO-level library logs are silenced,
# then allow specific loggers (like our own) to opt back to INFO if needed.
logging.basicConfig(level=logging.WARNING)
# Also explicitly squelch the SQLAlchemy engine logger (belt + suspenders).
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Initialize LangSmith tracing status
from ai_engine.observability import setup_langsmith
setup_langsmith()

from ai_engine.chat.conversation_agent import handle_chat
from ai_engine.memory.redis_memory import get_session_manager
from ai_engine.llm_config import token_tracker


# ── Formatting helpers ─────────────────────────────────────────────────────

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════╗
║                  🌍 TourMate AI — Interactive Chat           ║
║                                                              ║
║  Type your travel request and I'll plan your trip!           ║
║  Commands: /quit  /reset  /debug  /history  /usage  /help   ║
╚══════════════════════════════════════════════════════════════╝{RESET}
""")


def print_user_msg(msg: str):
    print(f"\n{GREEN}{BOLD}You:{RESET} {msg}")


def print_bot_msg(msg: str):
    print(f"\n{CYAN}{BOLD}TourMate:{RESET} {msg}")



def print_debug(result: dict):
    """Print debug info about the response."""
    print(f"\n{DIM}── Debug ──{RESET}")
    print(f"{DIM}  response_type: {result.get('response_type')}{RESET}")
    print(f"{DIM}  phase:         {result.get('phase')}{RESET}")
    print(f"{DIM}  session_id:    {result.get('session_id', 'N/A')[:16]}...{RESET}")
    if result.get("itinerary"):
        days = len(result["itinerary"].get("days", []))
        total_stops = sum(len(d.get("stops", [])) for d in result["itinerary"].get("days", []))
        hotels = len(result["itinerary"].get("accommodation_suggestions", []))
        print(f"{DIM}  itinerary:     {days} days, {total_stops} stops, {hotels} hotels{RESET}")
    else:
        print(f"{DIM}  itinerary:     None{RESET}")

    # ── Agent Pipeline Trace ──
    agent_messages = result.get("agent_messages", [])
    if agent_messages:
        print(f"\n{BOLD}  Pipeline Trace:{RESET}")
        for msg in agent_messages:
            # Color-code by agent name
            if "[LoadProfile]" in msg:
                color = CYAN
            elif "[PreferenceAgent]" in msg:
                color = GREEN
            elif "[RetrievalAgent]" in msg:
                color = YELLOW
            elif "[RankingAgent]" in msg:
                color = YELLOW
            elif "[Planner]" in msg:
                color = GREEN
            elif "[Optimizer]" in msg:
                color = GREEN
            elif "[Validator]" in msg:
                color = CYAN
            else:
                color = DIM
            print(f"{color}    {msg}{RESET}")

    # ── Validation Results ──
    validation = result.get("validation")
    if validation:
        score = validation.get("score", "?")
        is_valid = validation.get("is_valid", False)
        issues = validation.get("issues", [])
        status_color = GREEN if is_valid else RED
        print(f"\n{BOLD}  Validation:{RESET} {status_color}score={score}{RESET}")
        if issues:
            for issue in issues:
                print(f"{RED}    ⚠ {issue}{RESET}")

    print(f"{DIM}{'─'*30}{RESET}")


# ── Export ──────────────────────────────────────────────────────────────────


async def _handle_export(session_id: str | None, last_result: dict | None):
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

    # Build export payload
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
        "conversation_history": [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in (state.history or [])
        ],
    }

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"tourmate_export_{timestamp}.json"
    filepath = os.path.join(os.getcwd(), filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2, ensure_ascii=False, default=str)
        print(f"{GREEN}✅ Exported to {filepath}{RESET}")
        print(f"{DIM}   Contains: session info, slots, itinerary, pipeline trace, validation, history{RESET}")
    except Exception as e:
        print(f"{RED}Error writing export file: {e}{RESET}")


# ── Main chat loop ─────────────────────────────────────────────────────────

async def chat_loop():
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

    user_id = "interactive_user"
    session_id = None
    debug_mode = False
    turn = 0
    last_result = None

    # ── Check for existing session to resume ──────────────────────────
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

                # Show what's already filled
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
        pass  # Non-fatal — just proceed without resume context

    print(f"{DIM}Start chatting! (Type /help for commands){RESET}\n")

    while True:
        try:
            # Get user input
            user_input = await asyncio.get_running_loop().run_in_executor(
                None, lambda: input(f"{GREEN}{BOLD}You ▸ {RESET}")
            )
        except (EOFError, KeyboardInterrupt):
            token_tracker.print_summary()
            print(f"\n{DIM}Goodbye! 👋{RESET}")
            break

        user_input = user_input.strip()

        # Skip empty input
        if not user_input:
            continue

        # ── Handle commands ──────────────────────────────────────────
        cmd = user_input.lower()

        if cmd in ("/quit", "/exit", "/q"):
            token_tracker.print_summary()
            print(f"{DIM}Goodbye! 👋{RESET}")
            break

        elif cmd == "/reset":
            session_id = None
            turn = 0
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
                        for msg in state.history[-10:]:  # Show last 10
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
            await _handle_export(session_id, last_result)
            continue

        elif cmd == "/usage":
            token_tracker.print_summary()
            continue

        elif cmd in ("/help", "/h", "?"):
            print(f"""
{BOLD}Commands:{RESET}
  /quit, /exit   Exit the chat
  /reset         Start a new conversation
  /debug         Toggle verbose debug output
  /history       Show conversation history
  /slots         Show collected trip slots
  /session       Show session info (ID, phase, turns)
  /export        Export itinerary + trace to JSON file
  /usage         Show token usage summary
  /help          Show this help message
""")
            continue

        # ── Send message to AI ───────────────────────────────────────
        turn += 1
        print(f"{DIM}(Turn {turn}){RESET}", end="")

        try:
            result = await handle_chat(
                user_id=user_id,
                user_message=user_input,
                session_id=session_id,
            )
        except Exception as e:
            print(f"\n{RED}Error: {e}{RESET}\n")
            continue

        # Update session tracking
        session_id = result.get("session_id", session_id)

        # Print response
        message = result.get("message", "")
        response_type = result.get("response_type", "")
        phase = result.get("phase", "")

        if response_type == "itinerary":
            print_bot_msg(message)
        elif response_type == "clarification":
            print_bot_msg(message)
        elif response_type == "chat":
            print_bot_msg(message)
        else:
            print_bot_msg(message or "(empty response)")

        # Track last result for /export
        last_result = result

        # Debug output
        if debug_mode:
            print_debug(result)

    # Cleanup
    try:
        manager = await get_session_manager()
        await manager.close()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        print(f"\n{DIM}Goodbye! 👋{RESET}")
