# Import Path to work with file paths
from pathlib import Path

# Import BaseSettings to create a settings/config class
from pydantic_settings import BaseSettings

# Import ConfigDict to configure Pydantic v2 settings
from pydantic import ConfigDict

# Define the base directory of the project (two levels up from this file)
BASE_DIR = Path(__file__).resolve().parent.parent


# Create a Settings class to manage environment variables
class Settings(BaseSettings):
    # Required API key, must be provided in environment or .env
    gemini_api_key: str
    
    # Optional environment name, default is "development"
    app_env: str = "development"

    # Configure where to load environment variables from
    model_config = ConfigDict(
        env_file=str(BASE_DIR / ".env"),  # Path to .env file
        env_file_encoding="utf-8"         # File encoding
    )

    backend_base_url: str = "http://localhost:8000"


# Create an instance of Settings; loads variables automatically
settings = Settings()

# Print the loaded values
# print(settings.gemini_api_key)
# print(settings.app_env)