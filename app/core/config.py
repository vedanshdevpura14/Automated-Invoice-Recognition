import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "CacheFlow AI - Automated Invoice Reconciliation"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Storage & Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'cacheflow.db'}"
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_FILE_SIZE_MB: int = 15
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".png", ".jpg", ".jpeg", ".txt"]

    # AI Configuration (Google Gemini)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL_EXTRACTION: str = "gemini-1.5-flash"
    GEMINI_MODEL_ARBITRATION: str = "gemini-1.5-pro"

    # Financial Reconciliation Tolerances
    # Small rounding differences shouldn't trigger false alarms
    AMOUNT_TOLERANCE: float = 1.0     # Currency units (e.g. ₹1.00 rounding diff)
    TAX_TOLERANCE: float = 1.0        # Currency units
    PRICE_TOLERANCE: float = 0.01     # Unit price variance tolerance

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
