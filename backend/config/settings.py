"""
Centralized Settings - Single source of truth for all configuration
Replaces scattered os.environ calls with type-safe Pydantic settings
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """JARVIS Mark-XL configuration with environment variable support"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM API Keys
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model to use")
    nvidia_nim_api_key: str = Field(default="", description="NVIDIA NIM API key")

    # Search API Keys
    serpapi_key: str = Field(default="", description="SerpAPI key for web search")
    tavily_key: str = Field(default="", description="Tavily API key")

    # Database & Services
    postgres_url: str = Field(default="", description="PostgreSQL connection URL")
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")

    # ChromaDB
    chroma_host: str = Field(default="localhost", description="ChromaDB server host")
    chroma_port: int = Field(default=8001, description="ChromaDB server port")

    # App Configuration
    jarvis_url: str = Field(default="http://127.0.0.1:3142", description="JARVIS daemon URL")
    backend_host: str = Field(default="127.0.0.1", description="Backend server host")
    backend_port: int = Field(default=8000, description="Backend server port")

    # Mode flags
    dev_mode: bool = Field(default=True, description="Development mode flag")

    # Telegram Bot (Phase 14)
    telegram_bot_token: str = Field(default="", description="Telegram bot token from @BotFather")
    telegram_chat_id: str = Field(default="", description="Your Telegram chat ID")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance - call once at startup"""
    return Settings()


def reload_settings() -> Settings:
    """Clear cache and reload settings - useful for testing"""
    get_settings.cache_clear()
    return get_settings()