# Import the Google Gemini chat wrapper from LangChain
from langchain_google_genai import ChatGoogleGenerativeAI

# Import the Gemini model configuration constants from your config module
from ai.config.model_config import (
    GEMINI_MODEL,        # Model name
    GEMINI_TEMPERATURE,  # Controls randomness
    GEMINI_MAX_TOKENS,   # Max tokens to generate
    GEMINI_API_KEY       # API key for authentication
)


# Define a function that returns a configured Gemini LLM instance
def get_gemini_llm() -> ChatGoogleGenerativeAI:
    """
    Creates and returns a ChatGoogleGenerativeAI instance
    using the pre-defined model settings and API key.
    """
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,             # Which model to use
        temperature=GEMINI_TEMPERATURE, # How creative/random the responses are
        max_output_tokens=GEMINI_MAX_TOKENS, # Limit for generated tokens
        google_api_key=GEMINI_API_KEY,  # API key from settings
    )