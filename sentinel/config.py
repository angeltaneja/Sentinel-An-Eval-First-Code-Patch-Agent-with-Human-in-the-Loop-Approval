"""
Configuration management for Sentinel using Pydantic Settings.
Centralizes environment variables, model specifications, thresholds, and guardrails.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for Sentinel."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core LLM Configurations
    OPENAI_API_KEY: str | None = Field(default=None, description="OpenAI or compatible API Key")
    OPENAI_BASE_URL: str | None = Field(default=None, description="Custom base URL for LLM provider")
    LLM_MODEL: str = Field(default="gpt-4o", description="Primary model for planning, generation, and repair")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", description="Model for dense code retrieval")

    # Observability (Langfuse)
    LANGFUSE_PUBLIC_KEY: str | None = Field(default=None, description="Langfuse public API key")
    LANGFUSE_SECRET_KEY: str | None = Field(default=None, description="Langfuse secret key")
    LANGFUSE_HOST: str = Field(default="https://cloud.langfuse.com", description="Langfuse host URL")
    LANGFUSE_ENABLED: bool = Field(default=True, description="Enable or disable Langfuse tracing")

    # State Persistence (Postgres Checkpointer for LangGraph)
    POSTGRES_URI: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/sentinel",
        description="PostgreSQL connection string for durable LangGraph checkpointing",
    )
    USE_SQLITE_FALLBACK: bool = Field(
        default=True,
        description="Fallback to SQLite checkpointer if Postgres connection is not available in local dev",
    )
    SQLITE_DB_PATH: str = Field(
        default="sentinel_checkpoints.db",
        description="SQLite database path for local checkpointing fallback",
    )

    # GitHub Integration
    GITHUB_TOKEN: str | None = Field(default=None, description="GitHub personal access token")

    # Guardrails & Sandbox Limits
    MAX_REPAIR_RETRIES: int = Field(default=3, description="Hard cap on repair attempts")
    SANDBOX_BACKEND: Literal["docker", "local", "auto"] = Field(
        default="auto",
        description="Sandbox execution backend: 'docker', 'local' isolated process, or 'auto'",
    )
    SANDBOX_DOCKER_IMAGE: str = Field(
        default="python:3.12-slim",
        description="Base Docker image for isolated testing",
    )
    SANDBOX_TIMEOUT_SECONDS: int = Field(
        default=120,
        description="Timeout per test run in seconds inside sandbox",
    )
    SANDBOX_MEMORY_LIMIT: str = Field(
        default="2g",
        description="Memory limit for Docker container (e.g., '2g', '1024m')",
    )
    SANDBOX_CPU_LIMIT: float = Field(
        default=2.0,
        description="Max CPU cores assigned to sandbox container",
    )

    # Retrieval Configurations
    TOP_K_CHUNKS: int = Field(default=8, description="Number of context chunks to retrieve")
    AST_LANGUAGES: list[str] = Field(
        default_factory=lambda: ["python", "javascript", "typescript", "go", "java"],
        description="Languages supported by AST chunker",
    )

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Standard logging level")
    STRUCTURED_LOGGING: bool = Field(default=True, description="Output structured JSON logs")


# Singleton instance
settings = Settings()
