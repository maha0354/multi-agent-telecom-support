"""Paths and settings shared by the backend."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = BACKEND_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
DB_PATH = Path(os.getenv("TELECOM_DB_PATH", DATA_DIR / "telecom.db"))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", DATA_DIR / "chroma"))

# Lite model by default: ~2 s per call vs 5-10 s for full Flash, which matters with ~8 sequential calls.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
# Stay just under the free-tier quota; raise it on a paid key.
GEMINI_REQUESTS_PER_MINUTE = float(os.getenv("GEMINI_REQUESTS_PER_MINUTE", "14"))

# Customer used when a caller (e.g. the CLI) does not pick one. The API requires an explicit
# customer; either way code puts it into graph state and the LLM never chooses it.
DEFAULT_CUSTOMER_ID = "C-1001"
