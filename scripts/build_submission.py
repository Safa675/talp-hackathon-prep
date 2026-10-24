"""Run the five hand-in runs in parallel, assemble team-09_submission.zip and run check.py on it.

    python scripts/build_submission.py                      # all five runs, then ZIP + check
    python scripts/build_submission.py --skip-runs          # re-pack existing runs only
    python scripts/build_submission.py --announcements data/crises/test_announcements.json --tag test

Runs go to submission/runs/<name>/. CLIENT_MEMO.md and TEAM_DOC.md are taken from docs/ (placeholders
are written if missing). Code is copied from src/, scripts/, pipelines/ and data/ (no outputs, no .env).
"""
import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = [("plan_1", "plan", 1, True), ("plan_2", "plan", 2, False), ("nodecision_1", "nodecision", 1, True),
        ("nodecision_2", "nodecision", 2, False), ("plan_nosurprises", "plan_nosurprises", 1, False)]
CODE_DIRS = ["src", "scripts", "pipelines", "tools"]
CODE_DATA = ["data/personas", "data/decisions", "data/crises", "docs/announcements"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-runs", action="store_true")
    ap.add_argument("--announcements", default=None)
    ap.add_argument("--decisions", default=None)
    ap.add_argument("--personas", default=None)
    ap.add_argument("--tag", default="", help="suffix for the submission folder (e.g. test)")
    args = ap.parse_args()

    sub = ROOT / ("submission" + (f"-{args.tag}" if args.tag else ""))
    if not args.skip_runs:
        procs = []
        for name, typ, seed, probe in RUNS:
            cmd = [sys.executable, str(ROOT / "scripts" / "run_sim.py"), "--type", typ, "--seed", str(seed),
                   "--out", str(sub / "runs" / name)]
            cmd += ["--probe"] if probe else []
            for flag in ("announcements", "decisions", "personas"):
                if getattr(args, flag):
                    cmd += [f"--{flag}", getattr(args, flag)]
            procs.append((name, subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                                 encoding="utf-8")))
        failed = []
        for name, p in procs:  # wait for all five before deciding anything
            out, _ = p.communicate()
            print(f"===== {name} (exit {p.returncode})\n{out[-1500:]}")
            if p.returncode:
                failed.append(name)
        if failed:
            sys.exit(f"failed runs: {', '.join(failed)}")

    for doc in ("CLIENT_MEMO.md", "TEAM_DOC.md"):
        src = ROOT / "docs" / doc
        if not src.exists():
            src.parent.mkdir(exist_ok=True)
            src.write_text(f"# {doc[:-3].replace('_', ' ').title()}\n\nTODO: write before 18:00.\n", encoding="utf-8")
        shutil.copy(src, sub / doc)
    code = sub / "code"
    if code.exists():
        shutil.rmtree(code)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".env", "*.env", "nhts2022", "tr")
    for d in CODE_DIRS + CODE_DATA:
        if (ROOT / d).exists():
            shutil.copytree(ROOT / d, code / d, ignore=ignore)
    for f in ("README.md", "CLAUDE.md"):
        shutil.copy(ROOT / f, code / f)

    zip_path = ROOT / ("team-09_submission.zip" if not args.tag else f"team-09_submission-{args.tag}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(sub.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(sub).as_posix())
    print(f"\nZIP: {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB)\n")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "check.py"), str(zip_path)], text=True,
                       capture_output=True, encoding="utf-8")
    print(r.stdout[-6000:])
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
