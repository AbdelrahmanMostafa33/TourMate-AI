# backend/ai_engine/constants.py

# ══════════════════════════════════════════════════════════════════════════════
# Model configuration is now in ``ai_engine/llm/config.py`` (AGENT_LLM_REGISTRY).
# New code should use ``get_llm_for_agent(role)`` instead of hard-coding models.
# ══════════════════════════════════════════════════════════════════════════════

# === Conversation Agent ===
# Timeout for PLAN_GENERATION phase — if exceeded, session resets to SLOT_FILLING
PLAN_GENERATION_TIMEOUT_MINUTES = 5

# === Candidate Pool ===
# Minimum unused places before triggering a DB refresh during edits
POOL_REFRESH_THRESHOLD = 20
# Max places shown to the delta modifier LLM (unused pool slice)
MODIFIER_POOL_DISPLAY = 60
# Max ranked candidates sent to the planning agent
MAX_TOTAL_CANDIDATES = 70

# === Session Management (Redis) ===
# How long a conversation session lives in Redis (1 hour)
SESSION_TTL_SECONDS  = 3600
# Max messages kept in the rolling history window
SESSION_HISTORY_MAX  = 20
# Redis key prefixes for session storage
REDIS_SESSION_PREFIX         = "session:"
REDIS_USER_SESSIONS_PREFIX   = "user_sessions:"
REDIS_ACTIVE_SESSION_PREFIX  = "user_active_session:"