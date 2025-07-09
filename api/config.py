"""
Configuration settings for outlabsAuth
"""
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "mongodb://localhost:27017"
    MONGO_DATABASE: str = "outlabs_auth"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Redis  
    REDIS_URL: str = "redis://:guest@localhost:6379"
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Account security
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 30
    
    # Email (optional for phase 1)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = "noreply@outlabs.com"
    
    # Environment
    ENVIRONMENT: str = "development"
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra env vars from old system


settings = Settings()