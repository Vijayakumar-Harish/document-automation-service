from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://localhost:27017/assignment"
    DB_NAME: str = "assignment"
    JWT_SECRET: str
    JWT_ALGO: str = "HS256"
    CREDITS_PER_ACTION: int = 5

    OPENAI_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_case_sensitive=False
    )

settings = Settings()