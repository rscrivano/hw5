"""Shared configuration for the MCP server and the agent backend.

Both point at the WORKING COPY of the database (data/campus_customs_new.db).
The original data/campus_customs.db is never written to; it is only read when the
working copy is reset.
"""
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # optional; PORTKEY_API_KEY may already be in the environment

DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

ORIGINAL_DB = DATA_DIR / "campus_customs.db"      # pristine - never modified
WORKING_DB = Path(os.getenv("CC_WORKING_DB", DATA_DIR / "campus_customs_new.db"))  # all reads/writes go here
# (CC_WORKING_DB / CC_AUDIT_TRAIL only exist so tests can use a scratch copy; leave unset normally.)
AUDIT_TRAIL = Path(os.getenv("CC_AUDIT_TRAIL", OUTPUT_DIR / "audit_trail.json"))  # append-only agent-loop log

# ---------------------------------------------------------------------------
# LLM settings. The assignment allows exactly ONE model, routed through Portkey.
# This is the only place the model name appears in the code.
# ---------------------------------------------------------------------------
MODEL = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Optional: a Portkey provider slug (e.g. "@my-openai") if your Portkey workspace
# needs one to route the model. Leave unset if your key already routes gpt-6-luna.
PORTKEY_PROVIDER = os.getenv("PORTKEY_PROVIDER", "").strip()

# ---------------------------------------------------------------------------
# Token guard rails - multi-agent chats burn tokens fast.
# ---------------------------------------------------------------------------
MAX_OUTPUT_TOKENS = int(os.getenv("CC_MAX_OUTPUT_TOKENS", "6000"))          # per model response (incl. reasoning)
REASONING_EFFORT = os.getenv("CC_REASONING_EFFORT", "low")                  # low keeps reasoning tokens small
MAX_REQUESTS_PER_TICKET = int(os.getenv("CC_MAX_REQUESTS_PER_TICKET", "40"))       # all agents, one ticket
MAX_TOKENS_PER_TICKET = int(os.getenv("CC_MAX_TOKENS_PER_TICKET", "120000"))  # all agents, one ticket
MAX_DELEGATION_DEPTH = int(os.getenv("CC_MAX_DELEGATION_DEPTH", "3"))
MAX_TASKS_PER_AGENT_PER_TICKET = int(os.getenv("CC_MAX_TASKS_PER_AGENT_PER_TICKET", "3"))
