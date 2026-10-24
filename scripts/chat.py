"""Chat with one persona in the terminal (rehearsal for the board's live question).

    python scripts/chat.py S-A-2
    python scripts/chat.py F-B-1 --memory "Week 8: flight canceled, rebooked on a partner the same night."
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kestrel_sim import config, prompts  # noqa: E402
from kestrel_sim.llm import Gemini  # noqa: E402
from kestrel_sim.personas import load_personas  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("persona")
    ap.add_argument("--memory", default="", help="what this persona lived through, if anything")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    p = next((x for x in load_personas() if x["id"] == args.persona), None)
    if p is None:
        sys.exit(f"Unknown persona {args.persona}")
    llm = Gemini(seed=args.seed)
    history = []
    print(f"Talking to {p['name']} ({p['tagline']}). Empty line to quit.\n")
    while True:
        q = input("Board > ").strip()
        if not q:
            break
        context = "\n".join(f"Board: {a}\n{p['name']}: {b}" for a, b in history)
        memory = f"\nWhat you have lived through: {args.memory}" if args.memory else ""
        prompt = prompts.interview_prompt(p, q) + memory + (f"\n\nConversation so far:\n{context}" if context else "")
        answer, _ = llm.generate(prompt, persona=p["id"], week=11)
        history.append((q, answer.strip()))
        print(f"{p['name']} > {answer.strip()}\n")


if __name__ == "__main__":
    main()
