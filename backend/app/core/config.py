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
    google_api_key: str
    backend_base_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()