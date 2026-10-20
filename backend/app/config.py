from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data"
    model_profile: Literal["local", "hybrid", "cloud"] = "hybrid"
    ollama_base_url: str = "http://localhost:11434/v1"
    phoenix_endpoint: str = "http://localhost:6006/v1/traces"
    trace_content: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
