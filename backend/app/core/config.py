from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Rihla"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Database
    DB_ENGINE: str = "mongodb"  # or "postgresql"
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "rihla"
    DATABASE_URL: str = ""  # PostgreSQL optional

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # AI Models
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_AI_API_KEY: str = ""
    XAI_API_KEY: str = ""
    VERTEX_AI_PROJECT: str = ""
    VERTEX_AI_LOCATION: str = "us-central1"

    # Maps
    MAPBOX_TOKEN: str = ""
    GOOGLE_MAPS_API_KEY: str = ""

    # Storage
    CLOUDINARY_URL: str = ""

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
