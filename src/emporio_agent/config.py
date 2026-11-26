"""Runtime configuration, read from environment variables (and an optional .env file)."""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
STORE_TZ = ZoneInfo("America/Campo_Grande")  # the store is in Campo Grande/MS (UTC-4)

DEFAULT_MODEL = "ollama:gemma4:12b"


@dataclass(frozen=True)
class Settings:
    llm_model: str = DEFAULT_MODEL
    ollama_base_url: str = "http://localhost:11434"
    database_url: str | None = None
    agent_now: datetime | None = None  # frozen clock for evals / examples (SPEC I4)

    def now(self) -> datetime:
        """Current time in the store's timezone, unless the clock is frozen."""
        return self.agent_now or datetime.now(STORE_TZ)


def _parse_now(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=STORE_TZ)


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        llm_model=os.getenv("LLM_MODEL") or DEFAULT_MODEL,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434",
        database_url=os.getenv("DATABASE_URL") or None,
        agent_now=_parse_now(os.getenv("AGENT_NOW")),
    )
