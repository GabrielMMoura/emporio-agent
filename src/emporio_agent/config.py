"""Paths and runtime settings read from the environment (.env supported)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
POLICIES_PATH = DATA_DIR / "processed" / "policies.json"
STORE_TIMEZONE = "America/Campo_Grande"

DEFAULT_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str | None
    model: str


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        api_key=os.getenv("OPENAI_API_KEY") or None,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
        model=os.getenv("MODEL") or DEFAULT_MODEL,
    )
