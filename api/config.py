import os
from pydantic_settings import BaseSettings # pyre-ignore[21]

class Settings(BaseSettings):
    # API Security
    SECRET_KEY: str = os.getenv("JARVIS_SECRET_KEY", "your-super-secret-key-change-this")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Database Configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///./jarvis.db"
    
    # JARVIS Core Integration
    PIN_HASH: str = os.getenv("JARVIS_PIN_HASH", "")  # Initialized during first setup
    
    # WebSocket Configuration
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHUNK_SIZE: int = 4096

    class Config:
        env_file = ".env"

settings = Settings()
