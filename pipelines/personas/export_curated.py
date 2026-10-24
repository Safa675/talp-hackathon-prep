"""Flatten the curated library (data/personas/curated/personas.json) into personas.jsonl.

    python pipelines/personas/export_curated.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from kestrel_sim import config  # noqa: E402
from kestrel_sim.personas import export_jsonl, load_personas  # noqa: E402

if __name__ == "__main__":
    personas = load_personas("curated")
    target = config.PERSONA_SETS["curated"].with_suffix(".jsonl")
    export_jsonl(personas, target)
    print(f"{len(personas)} personas -> {target}")
