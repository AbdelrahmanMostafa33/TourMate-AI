from ai.config.settings import settings

# Text & agent models
GROQ_PLANNING_MODEL     = "llama-3.3-70b-versatile"
GROQ_OPTIMIZATION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_FAST_MODEL         = "llama-3.1-8b-instant"
GROQ_AGENT_MODEL        = "groq/compound-mini"

# Vision model (Llama 4 Scout is multimodal)
GROQ_VISION_MODEL       = "meta-llama/llama-4-scout-17b-16e-instruct"

# Shared settings
GROQ_TEMPERATURE  = 0.7
GROQ_MAX_TOKENS   = 8192

# API key
GROQ_API_KEY = settings.groq_api_key