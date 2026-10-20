from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # env_ignore_empty: a blank line like `DATA_DIR=` in .env means "use the default". Without it,
    # DATA_DIR= becomes Path("") = the current directory and the app silently uses another registry.
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", extra="ignore", env_ignore_empty=True
    )

    data_dir: Path = REPO_ROOT / "data"
    # cloud by default: local models run ~4 tokens/s on CPU (ADR-0002). See config/models.yaml.
    model_profile: Literal["local", "hybrid", "cloud"] = "cloud"
    models_config: Path = REPO_ROOT / "config" / "models.yaml"
    ollama_base_url: str = "http://localhost:11434/v1"
    # Provider keys are read from .env here and passed to providers explicitly: pydantic-ai
    # would otherwise only look in the process environment, not in .env.
    gemini_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY")
    )
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    tracing: bool = True  # TRACING=false turns off export (tests)
    phoenix_endpoint: str = "http://localhost:6006/v1/traces"
    trace_content: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]
    embed_model: str = "nomic-embed-text"
    max_upload_mb: int = 25


settings = Settings()
