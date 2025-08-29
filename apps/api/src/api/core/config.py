"""Application configuration."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Environment
    environment: str = Field(default="development", alias="ENV")
    debug: bool = Field(default=False)
    
    # API
    api_title: str = "AI Venture Architect API"
    api_version: str = "0.1.0"
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"]
    )
    
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
    
    # OpenSearch
    opensearch_url: str = Field(
        default="http://localhost:9200",
        alias="OPENSEARCH_URL"
    )
    
    # NATS
    nats_url: str = Field(
        default="nats://localhost:4222",
        alias="NATS_URL"
    )
    
    # S3/R2 Storage
    s3_endpoint: str = Field(default="", alias="S3_ENDPOINT")
    s3_access_key: str = Field(default="", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="", alias="S3_SECRET_KEY")
    s3_bucket: str = Field(default="ai-venture-architect", alias="S3_BUCKET")
    
    # JWT
    jwt_secret_key: str = Field(
        default="your-secret-key-change-in-production",
        alias="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    
    # OpenTelemetry
    otel_service_name: str = "ai-venture-architect-api"
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    
    # Feature Flags
    enable_auth: bool = Field(default=True)
    enable_metrics: bool = Field(default=True)
    enable_tracing: bool = Field(default=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
