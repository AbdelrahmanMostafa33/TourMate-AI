# backend/app/core/config.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # === Database ===
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    # === Firebase ===
    FIREBASE_CREDENTIALS: str = "firebase-credentials.json"

    # === Security ===
    SECRET_KEY: str

    # === AI (Gemini) ===
    # Comma-separated for multiple keys: key1,key2,key3
    google_api_key: str = ""

    # === AI (Groq) ===
    # Comma-separated for multiple keys: key1,key2,key3
    groq_api_key: str = ""

    backend_base_url: str = "http://localhost:8000"

    # === Stripe (Sandbox Payments) ===
    STRIPE_SECRET_KEY: str = "sk_test_51Sug26AirNZX1E8p0iAsyZmazRSg1tePIS1Nfcrm656s6BWp5xfECQ6xqMzanFIXPGJYnMRqHy2v4mMGV37fMAZD00bWGF1RED"
    STRIPE_PUBLISHABLE_KEY: str = "pk_test_51Sug26AirNZX1E8p5g6fVMcFYxsTSu77v2GNSQ4fzcPwtIBdMFxdEqKAqYAsdD9ZSUFfWz65buMkngDCoCqQmlVC008tqZjMVo"
    STRIPE_WEBHOOK_SECRET: str = "whsec_0634fe269ef52d414dcd737485324c56b4f99170b995305a31505f804b15c997"

    # === Amadeus (Flight Booking Simulation) ===
    AMADEUS_CLIENT_ID: str = "mLjsVmui1JG5cVkLkjfeW6UrhSs8Fpue"
    AMADEUS_CLIENT_SECRET: str = "FAeo2yaQAaNEPrKj"

    # === Expedia Rapid API (Hotel Booking) ===
    # Get credentials at https://developers.expediagroup.com/
    EXPEDIA_API_KEY: str = ""
    EXPEDIA_API_SECRET: str = ""

    # === LangSmith (Observability) ===
    # Set these in your .env to enable tracing:
    #   LANGCHAIN_TRACING_V2=true
    #   LANGCHAIN_API_KEY=ls_...
    #   LANGCHAIN_PROJECT=tourmate-ai

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()