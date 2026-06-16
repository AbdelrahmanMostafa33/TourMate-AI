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