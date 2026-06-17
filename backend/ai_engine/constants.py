# backend/ai_engine/constants.py

# === Gemini Model Names (Free Tier) ===
# gemini-2.5-flash: best price-performance, handles reasoning + vision
# gemini-2.5-flash-lite: fastest, cheapest, great for classification
GEMINI_PLANNING_MODEL     = "gemini-2.5-flash"
GEMINI_OPTIMIZATION_MODEL = "gemini-2.5-flash"
GEMINI_FAST_MODEL         = "gemini-2.5-flash-lite"
GEMINI_VISION_MODEL       = "gemini-2.5-flash"

# === Shared Settings ===
GEMINI_TEMPERATURE  = 0.7
GEMINI_MAX_TOKENS   = 8192

# === Session Management (Redis) ===
# How long a conversation session lives in Redis (1 hour)
SESSION_TTL_SECONDS  = 3600
# Max messages kept in the rolling history window
SESSION_HISTORY_MAX  = 20
# Redis key prefixes for session storage
REDIS_SESSION_PREFIX         = "session:"
REDIS_USER_SESSIONS_PREFIX   = "user_sessions:"
REDIS_ACTIVE_SESSION_PREFIX  = "user_active_session:"