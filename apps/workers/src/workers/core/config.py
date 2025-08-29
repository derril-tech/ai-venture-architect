"""Worker configuration."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Environment
    environment: str = Field(default="development", alias="ENV")
    debug: bool = Field(default=False)
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/ai_venture_architect",
        alias="DATABASE_URL"
    )
    
    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL"
    )
    
    # NATS
    nats_url: str = Field(
        default="nats://localhost:4222",
        alias="NATS_URL"
    )
    
    # OpenSearch
    opensearch_url: str = Field(
        default="http://localhost:9200",
        alias="OPENSEARCH_URL"
    )
    
    # AI Services
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    
    # External APIs
    crunchbase_api_key: str = Field(default="", alias="CRUNCHBASE_API_KEY")
    google_trends_api_key: str = Field(default="", alias="GOOGLE_TRENDS_API_KEY")
    
    # Worker settings
    max_concurrent_tasks: int = Field(default=10)
    task_timeout: int = Field(default=300)  # 5 minutes
    retry_attempts: int = Field(default=3)
    retry_delay: int = Field(default=60)  # 1 minute
    
    # Rate limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_window: int = Field(default=3600)  # 1 hour
    
    # Crawling settings
    user_agent: str = Field(
        default="AI-Venture-Architect/1.0 (+https://ai-venture-architect.com/bot)"
    )
    request_delay: float = Field(default=1.0)  # Delay between requests
    max_retries: int = Field(default=3)
    timeout: int = Field(default=30)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
