"""Load the frozen forecasting configuration (configs/forecast.toml)."""

import hashlib
import tomllib
from functools import cache
from pathlib import Path

from sic.config import PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "configs" / "forecast.toml"


@cache
def load(path: Path = CONFIG_PATH) -> dict:
    raw = path.read_bytes()
    config = tomllib.loads(raw.decode("utf-8"))
    config["_sha256"] = hashlib.sha256(raw).hexdigest()
    return config
