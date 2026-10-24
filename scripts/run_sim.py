"""Run one ten-week simulation and save it in the challenge's run format.

    python scripts/run_sim.py --type plan --seed 1 --probe
    python scripts/run_sim.py --type nodecision --seed 1 --probe
    python scripts/run_sim.py --type plan_nosurprises --seed 1
    python scripts/run_sim.py --type plan --seed 1 --decisions data/decisions/alt.json --out outputs/experiments/alt
    python scripts/run_sim.py --type plan --seed 1 --weeks 2 --only V-park-strike,S-home-strike   # quick smoke test
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kestrel_sim import config  # noqa: E402
from kestrel_sim.engine import Run  # noqa: E402

ANNOUNCEMENTS = config.ROOT / "docs" / "announcements" / "team-09_announcements.json"
DECISIONS = config.DATA_DIR / "decisions" / "plan.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=["plan", "nodecision", "plan_nosurprises"], required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--personas", choices=sorted(config.PERSONA_SETS), default=config.DEFAULT_PERSONA_SET)
    ap.add_argument("--decisions", default=str(DECISIONS))
    ap.add_argument("--announcements", default=str(ANNOUNCEMENTS))
    ap.add_argument("--probe", action="store_true", help="ask the check-in questions at week 0 and 11")
    ap.add_argument("--model", default=config.DEFAULT_MODEL)
    ap.add_argument("--only", default="", help="comma-separated persona ids (smoke tests)")
    ap.add_argument("--weeks", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    name = args.out or str(config.OUTPUT_DIR / "runs" / f"{args.type}_{args.seed}")
    t0 = time.time()
    run = Run(args.type, args.seed, persona_set=args.personas, decision_file=args.decisions,
              announcements_file=args.announcements, probe=args.probe, model=args.model,
              only=args.only.split(",") if args.only else None, weeks=args.weeks).run()
    metrics = run.save(name)
    errors = sum(c["response"].startswith("ERROR") for c in run.llm.log.calls)
    print(json.dumps({"run": name, "seconds": round(time.time() - t0), "calls": len(run.llm.log.calls),
                      "api_errors": errors, **{k: metrics[k] for k in ("goal_1", "goal_2", "goal_3", "goal_3b", "goal_4")},
                      "final_status_share_pct": metrics["detail"]["final_status_share_pct"]}, indent=1))


if __name__ == "__main__":
    main()
