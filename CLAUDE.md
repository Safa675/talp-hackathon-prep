# CLAUDE.md

Team-09 "Pegasus" at the TALP Simulation Lab (24 October 2026). Our client is **Kestrel Air**, a fictional US low-cost airline. We simulate its passengers as Gemini personas over ten company weeks, make two decisions for it, and hand in five runs that pass `tools/check.py`.

## Read first
- `docs/brief/02-challenge.md`: rules, run format and the check-in questions.
- `docs/brief/13-kestrel-air.md`: our dossier: goals, budget ($3M), decision menu, red lines, the week 8 strike.
- `docs/brief/03-audience-attributes.md`: the persona attribute catalog.

## Layout
```
data/personas/personas.json    source of truth: 5 groups -> 10 archetypes -> 30 members (edit this)
data/personas/personas.jsonl   generated flat export (same file goes into every run folder)
data/decisions/                decision files as locked on the dashboard
src/kestrel_sim/               package: config, llm (Gemini + call log), personas, prompts
scripts/test_personas.py       talk to all personas: check-in, interview, strike scenario
scripts/render_cards.py        persona cards as HTML
scripts/chat.py                interactive chat with one persona (board rehearsal)
tools/check.py                 organizers' submission checker (do not edit)
outputs/                       generated, git-ignored
```

## Commands
```bash
pip install -r requirements.txt
python scripts/test_personas.py --seed 1 --variant nodecision   # or --variant plan, --only S-A-2
python scripts/render_cards.py outputs/persona_tests/<run>/results.jsonl
python scripts/chat.py S-A-2
python tools/check.py team-09_submission.zip
```

## Rules that bite
- **Secrets:** the Vertex key is read from `TALP_KEY`, falling back to the git-ignored `.env`. Never write it into code, docs, outputs or the ZIP; `check.py` fails the submission if a string matching `AQ.` plus 40 characters appears anywhere.
- **The LLM decides behavior.** Code sets events (which flights are canceled, wait times). Gemini decides what each persona thinks, does and their status. Never script outcomes.
- **Statuses** must be the dossier's words: `flies as planned`, `rebooked`, `moved to another airline`, `canceled the trip`. Book-again (`yes|maybe|no`) goes in its own field. A partner-airline seat that Kestrel arranges counts as `rebooked`; the prompt defines this explicitly because without it the model reported `moved to another airline`.
- **Decision messages** must appear word for word in the targeted personas' prompts from their week on, and never earlier or in `nodecision` runs.
- **Same personas in all five runs.** Edit `personas.json`, then regenerate the `.jsonl`; do not hand-edit the export.
- Every call gets the run's `seed` and temperature 1.0. Model: `gemini-3.5-flash-lite` (about 1 s per call); calls run in 30 parallel threads.
- Calendar: week N starts at 13:00 + 30 min × (N-1); decisions must be locked before their week starts, none after 17:30, and the ZIP is due by 18:01.

## Commit messages (team guideline: docs/guidelines, PDF not in git)
- Imperative mood, present tense, capital first letter, **end with a full stop**: `Add persona test harness.`
- Small change: one line. Medium change: title, blank line, a short paragraph on why and how. Large change: summary, then paragraphs covering what changed, why, how, and any caveats or TODOs.
- Branches are lowercase with hyphens. Squash merges start with `[Merge squash commit from branch:X]`.
- No "oops" commits: amend or squash fixes into the commit they belong to before sharing.

## Persona card skill
`.claude/skills/persona-card/` renders personas in the card format (name, tagline, quote, tags, wins over, breaks at, would-book-again bar).
