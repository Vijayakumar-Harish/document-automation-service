from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://localhost:27017/assignment"
    DB_NAME: str = "assignment"
    JWT_SECRET: str = "KUHE(*kljdfljw30942lakd)"
    JWT_ALGO: str = "HS256"
    CREDITS_PER_ACTION: int = 5

settings = Settings()