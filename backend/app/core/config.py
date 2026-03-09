from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    FIREBASE_CREDENTIALS: str = "firebase-credentials.json"

    class Config:
        env_file = ".env"

settings = Settings()