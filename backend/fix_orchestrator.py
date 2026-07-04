"""Apply fixes to orchestrator.py: import, trace metadata, IMAGE_REVIEW handler."""
import re

with open("ai_engine/conversation/orchestrator.py", encoding="utf-8") as f:
    content = f.read()

# 1. Fix the import
old_import = "from ai_engine.observability import traced"
new_import = "from ai_engine.observability import traced, update_trace_metadata"
if old_import in content:
    content = content.replace(old_import, new_import, 1)
    print("Import: FIXED")
else:
    print("Import: ALREADY DONE or NOT FOUND")

# 2. Add update_trace_metadata call inside _process_message
target = (
    '"""Core routing logic shared by handle_chat and handle_chat_stream."""\n'
    "    try:\n"
    "        return await _process_message_inner"
)
replacement = (
    '"""Core routing logic shared by handle_chat and handle_chat_stream."""\n'
    "    # Attach conversation history to LangSmith trace for visibility\n"
    "    try:\n"
    "        if state and hasattr(state, 'history') and state.history:\n"
    "            summary = [\n"
    '                {"role": m.role, "content_snippet": (m.content or "")[:120]}\n'
    "                for m in state.history[-10:]\n"
    "            ]\n"
    "            update_trace_metadata({\n"
    '                "conversation_history": summary,\n'
    '                "phase": state.phase.value if state else "",\n'
    '                "turn_count": state.turn_count,\n'
    "            })\n"
    "    except Exception:\n"
    "        pass\n"
    "    try:\n"
    "        return await _process_message_inner"
)
if target in content:
    content = content.replace(target, replacement, 1)
    print("Trace metadata: FIXED")
else:
    print("Trace metadata: NOT FOUND")
    # Show what's actually at that spot
    idx = content.find('"""Core routing logic')
    if idx >= 0:
        print("  Found docstring at", idx)
        snippet = content[idx : idx + 350]
        print("  Snippet:", repr(snippet))

# 3. Fix the IMAGE_REVIEW confirmation handler
old_review = (
    '        if is_confirmed:\n'
    '            # User confirmed \u2014 fuse pending features into slots\n'
    '            pending = state.pending_image_features\n'
    '            if pending:\n'
    '                _fuse_pending_image_features(state, pending)\n'
    '                logger.info(\n'
    '                    "[ConversationAgent] User confirmed image preferences \u2014 fused into slots"\n'
    '                )\n'
    '            state.pending_image_features = None\n'
    '            state.transition_to(ConversationPhase.SLOT_FILLING)\n'
    '\n'
    '            message = (\n'
    "                \"Great! I've noted your preferences from the photo. \"\n"
    '                "Now, where would you like to go? I can plan a trip to cities like "\n'
    '                "Cairo, Luxor, Aswan, or anywhere else you\'re interested in."\n'
    '            )'
)

new_review = (
    '        if is_confirmed:\n'
    '            # User confirmed \u2014 fuse pending features into slots\n'
    '            pending = state.pending_image_features\n'
    '            if pending:\n'
    '                _fuse_pending_image_features(state, pending)\n'
    '                logger.info(\n'
    '                    "[ConversationAgent] User confirmed image preferences \u2014 fused into slots"\n'
    '                )\n'
    '            state.pending_image_features = None\n'
    '\n'
    '            # \u2500\u2500 Check what slots are already filled \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '            city = state.slots.destination_city\n'
    '            duration = state.slots.duration_days\n'
    '            state.slots.fill_defaults()\n'
    '\n'
    '            if state.slots.is_complete():\n'
    '                # All slots are filled \u2014 proceed directly to plan generation\n'
    '                state.transition_to(ConversationPhase.PLAN_GENERATION)\n'
    '                state.plan_started_at = datetime.now(timezone.utc).isoformat()\n'
    '                response = await _handle_plan_trip(\n'
    '                    user_id, effective_message, {}, image_features, token, state\n'
    '                )\n'
    '                state.add_user_message(effective_message, metadata={"action": "confirm_image"})\n'
    '                if response and response.get("message"):\n'
    '                    state.add_assistant_message(response["message"])\n'
    '                return response\n'
    '\n'
    '            state.transition_to(ConversationPhase.SLOT_FILLING)\n'
    '\n'
    '            if not city:\n'
    '                message = (\n'
    "                    \"Great! I've noted your preferences from the photo. \"\n"
    '                    "Now, where would you like to go? I can plan a trip to cities like "\n'
    '                    "Cairo, Luxor, Aswan, or anywhere else you\'re interested in."\n'
    '                )\n'
    '            elif not duration:\n'
    '                message = (\n'
    "                    \"Great! I've noted your preferences from the photo, and \"\n"
    '                    "I see you\'re interested in visiting " + str(city) + \". \"\n'
    '                    "How many days would you like for your trip?"\n'
    '                )\n'
    '            else:\n'
    '                missing = state.slots.missing_required()\n'
    "                msg_parts = [\"Great! I've noted your preferences from the photo.\"]\n"
    '                msg_parts.append(" Let\'s plan your trip to " + str(city))\n'
    '                if duration:\n'
    '                    day_word = "day" + ("s" if duration != 1 else "")\n'
    '                    msg_parts.append(" for " + str(duration) + " " + day_word)\n'
    '                msg_parts.append("!")\n'
    '                msg_parts.append(" Just a few more details: " + ", ".join(missing) + ".")\n'
    '                message = "".join(msg_parts)'
)

if old_review in content:
    content = content.replace(old_review, new_review, 1)
    print("IMAGE_REVIEW handler: FIXED")
else:
    print("IMAGE_REVIEW handler: NOT FOUND")
    # Show what's actually around line 226-250
    lines = content.split("\n")
    for i, line in enumerate(lines[225:251], start=226):
        print(f"  {i}: {repr(line)}")

with open("ai_engine/conversation/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)

import py_compile

try:
    py_compile.compile(
        "ai_engine/conversation/orchestrator.py", doraise=True
    )
    print("\nCompiles: OK")
except py_compile.PyCompileError as e:
    print(f"\nCompile Error: {e}")
