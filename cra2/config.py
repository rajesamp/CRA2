"""Settings from the environment or .env; the Groq SDK reads GROQ_API_KEY itself. Risk rules: rules.json."""

import os
from pathlib import Path

from dotenv import load_dotenv

PKG_DIR = Path(__file__).resolve().parent
DATA_DIR = PKG_DIR.parent / "data"
load_dotenv(PKG_DIR.parent / ".env")
MODEL = os.environ.get("CRA2_MODEL", "openai/gpt-oss-20b")  # pinned; change it only with an eval run
SEED, TEMPERATURE = int(os.environ.get("CRA2_SEED", "7")), 0.0
MAX_TOKENS = int(os.environ.get("CRA2_MAX_TOKENS", "1024"))
TIMEOUT_S = float(os.environ.get("CRA2_TIMEOUT_S", "10"))
MODE = os.environ.get("CRA2_MODE", "auto")  # fast: System 1 only · auto: Groq when unsure · deep: always Groq
REASONING = {"reasoning_effort": "low", "include_reasoning": False} if MODEL.startswith("openai/gpt-oss") else {}
