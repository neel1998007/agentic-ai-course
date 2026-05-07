"""
Central configuration for the agent.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ───────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / ".env"

# ── Load .env ───────────────────────────────────────
load_dotenv(dotenv_path=dotenv_path)

# ── Ensure logs/ folder exists ──────────────────────
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# ── LLM Settings ────────────────────────────────────
LLM_MODEL       = "llama-3.1-8b-instant"  # Updated model
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS  = 500

# ── Agent Settings ───────────────────────────────────
AGENT_MAX_STEPS   = 8
AGENT_MAX_RETRIES = 3

# ── API Keys ─────────────────────────────────────────
GROQ_API_KEY        = os.environ.get("GROQ_API_KEY")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

# ── Logging ──────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE  = str(LOGS_DIR / "agent.log")

# ── Validation ───────────────────────────────────────
if not GROQ_API_KEY:
    raise EnvironmentError(
        f"\nGROQ_API_KEY not found in .env file at: {dotenv_path}\n"
        f"Get your free key from: https://console.groq.com\n"
    )