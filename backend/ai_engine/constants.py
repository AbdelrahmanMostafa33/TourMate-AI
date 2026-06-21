# backend/ai_engine/constants.py

# ══════════════════════════════════════════════════════════════════════════════
# Gemini Models — used ONLY for planning (reasoning) and vision (multimodal)
# Free tier: 20 RPD per model — conserve carefully!
# ══════════════════════════════════════════════════════════════════════════════
GEMINI_PLANNING_MODEL = "gemini-2.5-flash"      # Itinerary generation
GEMINI_VISION_MODEL   = "gemini-2.5-flash"      # Image understanding
GEMINI_TEMPERATURE    = 0.7
GEMINI_MAX_TOKENS     = 8192

# ══════════════════════════════════════════════════════════════════════════════
# Groq Models — used for classification, extraction, validation, general chat
# Free tier: 14.4K RPD (llama-3.1-8b), 1K RPD (llama-3.3-70b) — huge headroom
# ══════════════════════════════════════════════════════════════════════════════
GROQ_FAST_MODEL      = "llama-3.1-8b-instant"    # Intent parse, preference, validation
GROQ_REASONING_MODEL = "llama-3.3-70b-versatile"  # General chat, itinerary review Q&A
GROQ_TEMPERATURE     = 0.2
GROQ_MAX_TOKENS      = 2048

# === Conversation Agent ===
# Timeout for PLAN_GENERATION phase — if exceeded, session resets to SLOT_FILLING
PLAN_GENERATION_TIMEOUT_MINUTES = 5

# === Session Management (Redis) ===
# How long a conversation session lives in Redis (1 hour)
SESSION_TTL_SECONDS  = 3600
# Max messages kept in the rolling history window
SESSION_HISTORY_MAX  = 20
# Redis key prefixes for session storage
REDIS_SESSION_PREFIX         = "session:"
REDIS_USER_SESSIONS_PREFIX   = "user_sessions:"
REDIS_ACTIVE_SESSION_PREFIX  = "user_active_session:"