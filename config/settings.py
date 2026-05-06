"""
Central configuration for the agent.
Change settings here — nowhere else.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ───────────────────────────────────────────
# settings.py is at: agent_project/config/settings.py
# .parent      = agent_project/config/
# .parent.parent = agent_project/        ← this is BASE_DIR
BASE_DIR    = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / ".env"

# ── Load .env ───────────────────────────────────────
load_dotenv(dotenv_path=dotenv_path)

# ── Ensure logs/ folder exists ──────────────────────
# Creates it automatically if missing — no more FileNotFoundError
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# ── LLM Settings ────────────────────────────────────
LLM_MODEL       = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS  = 500

# ── Agent Settings ───────────────────────────────────
AGENT_MAX_STEPS   = 8
AGENT_MAX_RETRIES = 3

# ── API Keys ─────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ── Logging ──────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE  = str(LOGS_DIR / "agent.log")

# ── Validation ───────────────────────────────────────
if not GROQ_API_KEY:
    raise EnvironmentError(
        f"\n\n"
        f"GROQ_API_KEY not found.\n"
        f"Expected .env file at: {dotenv_path}\n"
        f"File exists: {dotenv_path.exists()}\n\n"
        f"Steps to fix:\n"
        f"  1. Open {dotenv_path}\n"
        f"  2. Add: GROQ_API_KEY=your_key_here\n"
        f"  3. Get key from: https://console.groq.com\n"
    )