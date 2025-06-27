from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Manages application settings using Pydantic.
    It automatically loads variables from a .env file and the environment.
    """
    DATABASE_URL: str
    MONGO_DATABASE: str
    SECRET_KEY: str = Field(..., description="Secret key for JWT token signing")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="Access token expiration time in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiration time in days")
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = Field(default=15, description="Password reset token expiration time in minutes")
    ALGORITHM: str = Field(default="HS256", description="Algorithm for JWT token signing")

    # Enriched JWT Settings
    MAX_JWT_SIZE_BYTES: int = Field(default=8192, description="Maximum JWT token size in bytes (8KB limit)")
    ENABLE_ENRICHED_TOKENS_BY_DEFAULT: bool = Field(default=True, description="Enable enriched tokens by default")
    PERMISSION_CACHE_TTL_SECONDS: int = Field(default=300, description="Permission cache TTL in seconds (5 minutes)")

    # Pydantic-settings configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Create a single instance of the settings to be used throughout the application
settings = Settings() 