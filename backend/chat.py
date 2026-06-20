"""
Interactive Chat Loop for TourMate AI Pipeline

Usage:
    python chat.py

Commands:
    /quit, /exit   — Exit the chat
    /reset          — Start a new conversation (new session)
    /debug          — Toggle verbose debug output
    /history        — Show conversation history
    /slots          — Show collected trip slots
    /session        — Show session info (ID, phase, turn count)
"""

import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from ai_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

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


def print_itinerary(itinerary: dict):
    """Pretty-print the generated itinerary."""
    days = itinerary.get("days", [])
    hotels = itinerary.get("accommodation_suggestions", [])

    print(f"\n{YELLOW}{BOLD}{'='*60}")
    print(f"  📋 ITINERARY — {itinerary.get('destination', 'Unknown')} ({len(days)} days)")
    print(f"{'='*60}{RESET}")

    for day in days:
        day_num = day.get("day_number", "?")
        theme = day.get("theme", "")
        stops = day.get("stops", [])

        print(f"\n{YELLOW}{BOLD}  Day {day_num}: {theme}{RESET}")
        print(f"  {'─'*40}")

        for i, stop in enumerate(stops, 1):
            name = stop.get("name", "?")
            category = stop.get("category", "")
            duration = stop.get("estimated_duration_minutes", "")
            time_of_day = stop.get("suggested_time_of_day", "")
            why = stop.get("why_recommended", "")

            time_emoji = {"morning": "🌅", "afternoon": "☀️", "evening": "🌙"}.get(time_of_day, "⏰")
            duration_str = f" ({duration}min)" if duration else ""

            print(f"    {i}. {time_emoji} {name} [{category}]{duration_str}")
            if why:
                print(f"       {DIM}→ {why}{RESET}")

    if hotels:
        print(f"\n{YELLOW}{BOLD}  🏨 Accommodation Suggestions{RESET}")
        print(f"  {'─'*40}")
        for hotel in hotels:
            name = hotel.get("name", "?")
            sub = hotel.get("sub_category", "")
            why = hotel.get("why_recommended", "")
            print(f"    • {name} [{sub}]")
            if why:
                print(f"      {DIM}→ {why}{RESET}")

    print(f"\n{YELLOW}{'='*60}{RESET}")


def print_debug(result: dict):
    """Print debug info about the response."""
    print(f"\n{DIM}── Debug ──{RESET}")
    print(f"{DIM}  response_type: {result.get('response_type')}{RESET}")
    print(f"{DIM}  phase:         {result.get('phase')}{RESET}")
    print(f"{DIM}  session_id:    {result.get('session_id', 'N/A')[:16]}...{RESET}")
    if result.get("itinerary"):
        days = len(result["itinerary"].get("days", []))
        print(f"{DIM}  itinerary:     {days} days{RESET}")
    else:
        print(f"{DIM}  itinerary:     None{RESET}")
    print(f"{DIM}{'─'*30}{RESET}")


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
            itinerary = result.get("itinerary")
            if itinerary:
                print_itinerary(itinerary)
        elif response_type == "clarification":
            print_bot_msg(message)
        elif response_type == "chat":
            print_bot_msg(message)
        else:
            print_bot_msg(message or "(empty response)")

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
