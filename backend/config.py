"""
config.py — centralised environment variable loader for RecoverAI.
Raises ConfigurationError at import time when mandatory vars are missing.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when a required environment variable is missing."""


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(
            f"Required environment variable '{name}' is not set. "
            "Check your .env file."
        )
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# ── Razorpay ─────────────────────────────────────────────────────────────────
RAZORPAY_KEY_ID: str = _require("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET: str = _require("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET: str = _require("RAZORPAY_WEBHOOK_SECRET")

# ── LLM (Groq) ───────────────────────────────────────────────────────────────
LLM_API_KEY: str = _require("LLM_API_KEY")
LLM_MODEL: str = _optional("LLM_MODEL", "openai/gpt-oss-20b")

# ── Speech-to-Text (Sarvam AI) ───────────────────────────────────────────────
STT_API_KEY: str = _optional("STT_API_KEY", "")          # warn only — not required
STT_BASE_URL: str = _optional("STT_BASE_URL", "https://api.sarvam.ai")
STT_MODEL: str = _optional("STT_MODEL", "saaras:v3")

# ── Auth ──────────────────────────────────────────────────────────────────────
API_KEY: str = _optional("API_KEY", "")   # if empty, auth is disabled (dev mode)

# ── Recovery guardrail defaults ───────────────────────────────────────────────
try:
    MAX_ATTEMPTS: int = int(_optional("MAX_ATTEMPTS", "5"))
    MAX_ESCALATION_LEVEL: int = int(_optional("MAX_ESCALATION_LEVEL", "3"))
    RECOVERY_WINDOW_DAYS: int = int(_optional("RECOVERY_WINDOW_DAYS", "30"))
    MIN_HOURS_BETWEEN_CONTACTS: int = int(_optional("MIN_HOURS_BETWEEN_CONTACTS", "24"))
except ValueError as exc:
    raise ConfigurationError(f"Numeric env var is not an integer: {exc}") from exc

# ── App ───────────────────────────────────────────────────────────────────────
APP_ENV: str = _optional("APP_ENV", "development")
LOG_LEVEL: str = _optional("LOG_LEVEL", "INFO")

logger.info(
    "RecoverAI config loaded — env=%s, llm_model=%s, stt_model=%s",
    APP_ENV, LLM_MODEL, STT_MODEL,
)
