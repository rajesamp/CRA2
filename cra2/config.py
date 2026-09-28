"""Validated process settings; opt in to a dotenv file with CRA2_ENV_FILE.

Settings are captured when this module is first imported. Export variables before
starting CRA2. An explicitly selected dotenv file never overrides exported values.
"""

import math
import os
from pathlib import Path

from dotenv import load_dotenv

from cra2.secrets import reject_credentials

PKG_DIR = Path(__file__).resolve().parent
# Wheels bundle resources inside the package; editable checkouts use source data.
DATA_DIR = PKG_DIR / "data" if (PKG_DIR / "data").is_dir() else PKG_DIR.parent / "data"
EVALS_DIR = (
    PKG_DIR / "evals" if (PKG_DIR / "evals").is_dir() else PKG_DIR.parent / "evals"
)


def _load_environment() -> None:
    selected = os.environ.get("CRA2_ENV_FILE")
    if selected is None:
        return
    if not selected.strip():
        raise ValueError("CRA2_ENV_FILE must name a readable dotenv file")
    try:
        with Path(selected).expanduser().open(encoding="utf-8") as stream:
            load_dotenv(stream=stream, override=False)
    except (OSError, UnicodeError) as exc:
        raise ValueError(
            "CRA2_ENV_FILE must name a readable UTF-8 dotenv file"
        ) from exc


def _integer(name: str, default: int, *, positive: bool = False) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if positive and value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _timeout() -> float:
    try:
        value = float(os.environ.get("CRA2_TIMEOUT_S", "10"))
    except ValueError as exc:
        raise ValueError("CRA2_TIMEOUT_S must be a finite positive number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError("CRA2_TIMEOUT_S must be a finite positive number")
    return value


_load_environment()
MODEL = os.environ.get("CRA2_MODEL", "openai/gpt-oss-20b").strip()
reject_credentials(MODEL)
if not MODEL:
    raise ValueError("CRA2_MODEL must be a nonempty model ID")
SEED = _integer("CRA2_SEED", 7)
TEMPERATURE = 0.0
MAX_TOKENS = _integer("CRA2_MAX_TOKENS", 1024, positive=True)
TIMEOUT_S = _timeout()
MODE = os.environ.get("CRA2_MODE", "auto")
if MODE not in {"fast", "auto", "deep"}:
    raise ValueError("CRA2_MODE must be fast, auto, or deep")
REASONING = (
    {"reasoning_effort": "low", "include_reasoning": False}
    if MODEL.startswith("openai/gpt-oss")
    else {}
)
