"""Application settings and project paths.

All paths are built with pathlib from the repository root, so the same code
works on macOS and Windows. Settings can be overridden with environment
variables (prefixed SIC_), but the defaults keep every service on this
computer only (127.0.0.1).
"""

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
DATA_DIR = PROJECT_ROOT / "data"
EVALUATION_DIR = PROJECT_ROOT / "evaluation"

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    ollama_url: str = "http://127.0.0.1:11434"
    # Chosen after the Milestone 1 feasibility test: non-thinking, ~8x faster than
    # qwen3:4b with thinking, and it never puts reasoning in the visible answer.
    ollama_model: str = "qwen3:4b-instruct-2507-q4_K_M"


def get_settings() -> Settings:
    return Settings(
        host=os.environ.get("SIC_HOST", Settings.host),
        port=int(os.environ.get("SIC_PORT", Settings.port)),
        ollama_url=os.environ.get("SIC_OLLAMA_URL", Settings.ollama_url).rstrip("/"),
        ollama_model=os.environ.get("SIC_OLLAMA_MODEL", Settings.ollama_model),
    )
