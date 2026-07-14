"""Configuration loading from YAML and environment."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv


class Config:
    """Load and access holos configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        load_dotenv()
        self.config_path = config_path or Path("config")
        self._data = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all YAML files from config directory."""
        if self.config_path.exists():
            for yaml_file in self.config_path.glob("*.yaml"):
                with open(yaml_file) as f:
                    self._data[yaml_file.stem] = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dot-notation key (e.g., 'sources.chicago.socrata_base')."""
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    @property
    def db_url(self) -> str:
        """PostgreSQL connection string from environment."""
        # Railway provides DATABASE_URL; fallback to individual vars
        if database_url := os.getenv("DATABASE_URL"):
            return database_url

        user = os.getenv("POSTGRES_USER", "holos")
        password = os.getenv("POSTGRES_PASSWORD", "holos_dev_only")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "holos")
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    @property
    def api_key_anthropic(self) -> str:
        """Anthropic API key from environment."""
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set in .env")
        return key
