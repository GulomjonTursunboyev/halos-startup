"""
API Configuration
Environment variables and settings
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # JWT Settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days
    
    # OTP Settings
    OTP_EXPIRE_MINUTES: int = 5
    OTP_LENGTH: int = 6
    
    # SMS Provider (Eskiz.uz)
    ESKIZ_EMAIL: str = os.getenv("ESKIZ_EMAIL", "")
    ESKIZ_PASSWORD: str = os.getenv("ESKIZ_PASSWORD", "")
    
    # Telegram Bot (for linking accounts)
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Kotib.ai
    KOTIB_API_KEY: str = os.getenv("KOTIB_API_KEY", "")
    
    # App Settings
    APP_NAME: str = "HALOS"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    class Config:
        env_file = ".env"


settings = Settings()
