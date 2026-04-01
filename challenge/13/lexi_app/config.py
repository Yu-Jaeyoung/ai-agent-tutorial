from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model


def find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    raise RuntimeError("Could not locate the project root for LeXi.")


PACKAGE_DIR = Path(__file__).resolve().parent
CHALLENGE_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = find_project_root(CHALLENGE_DIR)
MEMORY_DB_PATH = CHALLENGE_DIR / "lexi_memory.db"

_ENV_LOADED = False


def load_environment() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    load_dotenv(PROJECT_ROOT / ".env")
    _ENV_LOADED = True


def get_model_name() -> str:
    load_environment()
    return os.getenv("GOOGLE_GENAI_MODEL", "gemini-3-flash-preview")


@lru_cache(maxsize=1)
def get_llm():
    load_environment()
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY must be set in the project .env file.")
    return init_chat_model(
        model=get_model_name(),
        model_provider="google_genai",
        temperature=0,
    )
