"""Project paths, model settings and secret loading.

The Vertex key is read from the TALP_KEY environment variable. If it is not
set, the project-root .env file (git-ignored) is read as a fallback. The key
is never written anywhere else.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PERSONA_SOURCE = DATA_DIR / "personas" / "personas.json"
PERSONA_EXPORT = DATA_DIR / "personas" / "personas.jsonl"
OUTPUT_DIR = ROOT / "outputs"

COMPANY = "Kestrel Air"
COMPANY_SLUG = "kestrel"
DEFAULT_MODEL = os.environ.get("TALP_MODEL", "gemini-3.5-flash-lite")
DEFAULT_TEMPERATURE = 1.0
MAX_WORKERS = int(os.environ.get("TALP_WORKERS", "30"))

# Weekly statuses from the dossier ("What each persona reports every week").
PASSENGER_STATUSES = ["flies as planned", "rebooked", "moved to another airline", "canceled the trip"]
BOOK_AGAIN = ["yes", "maybe", "no"]


def load_api_key() -> str:
    key = os.environ.get("TALP_KEY")
    if key:
        return key.strip()
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("TALP_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("TALP_KEY is not set. Export it or add TALP_KEY=... to .env in the project root.")
