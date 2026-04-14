# Import the settings object from your config module
# This object already has your environment variables loaded (like gemini_api_key)
from ai.config.settings import settings


# Define constants for your Gemini LLM configuration
GEMINI_MODEL = "gemini-2.5-flash-lite"        # Model name for text tasks
GEMINI_VISION_MODEL = "gemini-2.5-flash-lite" # Model name for vision/multimodal tasks
GEMINI_TEMPERATURE = 0.7                      # Controls randomness in output (0 = deterministic)
GEMINI_MAX_TOKENS = 65536                     # Max tokens the model can generate or process

# Get the API key from your environment via the settings object
# This keeps your real API key secure and separate from your code
GEMINI_API_KEY = settings.gemini_api_key