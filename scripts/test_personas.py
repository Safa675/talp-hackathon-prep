"""Talk to every persona through Gemini and check that they behave like people.

For each persona, three calls run in parallel:
  1. check-in questions (the challenge's eight 1-5 items) before week 1;
  2. a board-style interview question;
  3. a strike-week scenario that must end in a dossier status.

Writes outputs/persona_tests/<timestamp>-<set>-<variant>/ with results.jsonl,
calls.jsonl, summary.json and cards.html, and prints a consistency report.
Status shares are given per persona and weighted by the trips each one stands for.

    python scripts/test_personas.py [--personas clusters|curated] [--seed 1] [--variant nodecision|plan]
                                    [--only S-A-2,F-B-1]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kestrel_sim import config, prompts  # noqa: E402
from kestrel_sim.llm import Gemini  # noqa: E402
from kestrel_sim.personas import load_personas  # noqa: E402

from render_cards import render_cards  # noqa: E402

INTERVIEW_Q = "Tell us who you are and what your next Kestrel trip means to you."


def test_one(llm, p, variant="nodecision"):
    probe, _, probe_call = llm.generate_json(prompts.probe_prompt(p), persona=p["id"], week=0)
    interview, _ = llm.generate(prompts.interview_prompt(p, INTERVIEW_Q), persona=p["id"], week=0)
    message = prompts.TEST_PLAN_MESSAGE if variant == "plan" and p["strike_exposed"] else None
    scen, raw, scen_call = llm.generate_json(
        prompts.scenario_prompt(p, prompts.strike_scenario(p, variant), message), persona=p["id"], week=8)
    scen = scen or {}
    return {
        "persona": p["id"], "name": p["name"], "group": p["group"], "archetype": p["archetype"],
        "strike_exposed": p["strike_exposed"], "weight": p["weight"],
        "probe": {k: (probe or {}).get(k) for k in prompts.PROBE_QUESTIONS},
        "probe_comment": (probe or {}).get("comment"), "probe_call": probe_call,
        "interview": interview,
        "strike": {"thoughts": scen.get("thoughts"), "actions": scen.get("actions"), "post": scen.get("post"),
                   "trust": scen.get("trust_1to5"), "book_again": scen.get("book_again"),
                   "status": prompts.parse_status(scen.get("status_line") or raw), "call": scen_call},
    }


def book_again_intent(probe):
    """0-100 from 'keep using' (2a) and the reversed 'thinking about leaving' (2b)."""
    a, b = probe.get("2a"), probe.get("2b")
    if not all(isinstance(x, int) for x in (a, b)):
        return None
    return round(((a + (6 - b)) / 2 - 1) / 4 * 100)


def consistency(probe):
    """Pairs that should agree once 2b and 4b are reversed. Returns max gap (0 = perfect)."""
    pairs = [("1a", "1b", False), ("2a", "2b", True), ("3a", "3b", False), ("4a", "4b", True)]
    gaps = []
    for x, y, rev in pairs:
        a, b = probe.get(x), probe.get(y)
        if isinstance(a, int) and isinstance(b, int):
            gaps.append(abs(a - ((6 - b) if rev else b)))
    return max(gaps) if gaps else None


def weighted_shares(results):
    """Status shares (%) weighted by the passenger trips each persona stands for."""
    total = sum(r["weight"] for r in results) or 1
    return {s: round(100 * sum(r["weight"] for r in results if r["strike"]["status"] == s) / total, 1)
            for s in config.PASSENGER_STATUSES}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", choices=sorted(config.PERSONA_SETS), default=config.DEFAULT_PERSONA_SET)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--model", default=config.DEFAULT_MODEL)
    ap.add_argument("--only", default="", help="comma-separated persona ids")
    ap.add_argument("--variant", choices=["nodecision", "plan"], default="nodecision",
                    help="strike scenario without or with the test plan (partner rebooking, hotel, message)")
    args = ap.parse_args()

    all_personas = load_personas(args.personas)
    personas = all_personas
    if args.only:
        keep = set(args.only.split(","))
        personas = [p for p in personas if p["id"] in keep]

    llm = Gemini(model=args.model, seed=args.seed)
    results = llm.map(lambda p: test_one(llm, p, args.variant), personas)

    out = config.OUTPUT_DIR / "persona_tests" / f'{datetime.now().strftime("%Y%m%d-%H%M%S")}-{args.personas}-{args.variant}'
    out.mkdir(parents=True, exist_ok=True)
    llm.log.write_jsonl(out / "calls.jsonl")
    with open(out / "results.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            r["intent"] = book_again_intent(r["probe"])
            r["consistency_gap"] = consistency(r["probe"])
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    bad_probe = [r["persona"] for r in results if not all(isinstance(v, int) and 1 <= v <= 5 for v in r["probe"].values())]
    bad_status = [r["persona"] for r in results if r["strike"]["status"] is None]
    errors = [c["id"] for c in llm.log.calls if c["response"].startswith("ERROR")]
    inconsistent = [r["persona"] for r in results if (r["consistency_gap"] or 0) >= 2]
    exposed = [r for r in results if r["strike_exposed"]]
    summary = {
        "persona_set": args.personas, "variant": args.variant, "seed": args.seed, "personas": len(results), "calls": len(llm.log.calls), "api_errors": len(errors),
        "invalid_probe": bad_probe, "missing_status": bad_status, "inconsistent_reversed_items": inconsistent,
        "strike_exposed": len(exposed),
        "strike_status_counts": {s: sum(r["strike"]["status"] == s for r in exposed) for s in config.PASSENGER_STATUSES},
        "strike_status_weighted_pct": weighted_shares(exposed),
        "book_again_counts": {b: sum(r["strike"]["book_again"] == b for r in results) for b in config.BOOK_AGAIN},
        "mean_start_trust_1a": round(sum(r["probe"]["1a"] or 0 for r in results) / max(len(results), 1), 2),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    render_cards(all_personas, results, out / "cards.html")

    print(json.dumps(summary, indent=2))
    print(f"\nSaved to {out}")
    for r in results:
        s = r["strike"]
        print(f"{r['persona']:26} {r['name']:20} trust0={r['probe']['1a']} intent={r['intent']}% "
              f"gap={r['consistency_gap']} | W8 {'EXPOSED' if r['strike_exposed'] else 'news   '} -> "
              f"{s['status']} / again={s['book_again']}")


if __name__ == "__main__":
    main()
