"""App settings loaded from the repo-root .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Environment-driven settings. Model names live only here."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # blank values in .env fall back to the defaults below
        extra="ignore",
    )

    GEMINI_API_KEY: str | None = None
    TEXT_MODEL: str = "gemini-2.5-flash"
    FALLBACK_MODEL: str = "gemini-2.5-flash-lite"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


settings = Settings()
