import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    GEMINI_API_KEY: str
    FIREBASE_CREDENTIALS: str = "firebase-credentials.json"
    groq_api_key: str
    
    class Config:
        env_file = ".env"
        extra = "ignore"
        
settings = Settings()