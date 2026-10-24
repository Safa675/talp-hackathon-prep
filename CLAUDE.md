# CLAUDE.md

Team-09 "Pegasus" at the TALP Simulation Lab (24 October 2026). Our client is **Kestrel Air**, a fictional US low-cost airline. We simulate its passengers as Gemini personas over ten company weeks, make two decisions for it, and hand in five runs that pass `tools/check.py`. Remote: github.com/Safa675/talp-hackathon-prep.

## Read first
- `docs/brief/02-challenge.md`: rules, run format and the check-in questions.
- `docs/brief/13-kestrel-air.md`: our dossier: goals, budget ($3M), decision menu, red lines, the week 8 strike.
- `docs/brief/03-audience-attributes.md`: the persona attribute catalog.
- `docs/announcements/`: dashboard announcements (export them again after each one).

## Layout
```
docs/brief/                      organizers' brief (challenge, catalog, dossier)
docs/announcements/              exported dashboard announcements
data/personas/clusters/          66 cluster personas (default set) + clusters.json + generation calls
data/personas/curated/           30 curated personas: personas.json (edit) -> personas.jsonl (export)
data/decisions/plan.json         our two decisions (must match the dashboard lock) + target_rule per decision
data/crises/                     readings.json (how we read each real surprise), test_announcements.json (TEST ONLY)
data/us/                         NHTS 2022 public files and the air-trip profile (grounding)
data/tr/                         Turkish data package from the general prep (not used for Kestrel)
pipelines/personas/              make_clusters -> gen_personas (Gemini, run once), export_curated
pipelines/grounding/             nhts_air_profile.py
pipelines/tr_data/               Eurostat / TUIK fetchers
src/kestrel_sim/                 config, llm, personas, prompts, decisions, crises, world, engine, metrics
scripts/                         run_sim, build_submission, test_personas, render_cards, chat
tools/check.py                   organizers' submission checker (do not edit)
outputs/                         generated, git-ignored
```

## Commands
```bash
python scripts/build_submission.py                 # the five hand-in runs in parallel (~4 min) -> ZIP -> check.py
python scripts/build_submission.py --announcements data/crises/test_announcements.json --tag test   # dry run
python scripts/run_sim.py --type plan --seed 1 --probe --out outputs/experiments/x   # one run / experiment
python scripts/test_personas.py --personas clusters --variant nodecision   # or curated / plan, --only <ids>
python scripts/render_cards.py --personas curated outputs/persona_tests/<run>/results.jsonl
python scripts/chat.py V-park-strike                                       # --personas curated S-A-2
python pipelines/personas/make_clusters.py                                 # deterministic; must reproduce clusters.json
python pipelines/personas/export_curated.py                                # after editing curated/personas.json
python tools/check.py team-09_submission.zip
```
Python 3.9+ with the standard library only.

## Persona sets
Both load through `kestrel_sim.personas.load_personas(set)` into one shape: `id, group, name, age, home, tagline, tags, quote, card_rows, trips[{date, week, from, to}], strike_exposed, weight, connections, profile`. `weight` is in passenger trips over the ten weeks (about 2.17M in total for either set); `profile` is the "who you are" text the model reads.
- **clusters** (default): 17 segments × 4 travel windows, raked (IPF) to the NHTS 2022 air-trip mix and the dossier calendar. Strike-exposed passengers are oversampled and corrected by weight. Names and behaviour traits are assigned in code because the model collapsed them. **Do not regenerate**: the personas must stay the same across all five runs.
- **curated**: 10 archetypes × 3 members, with social `connections`, "wins over" and "breaks at". Their reactions are sharper than the clusters'; we use them for social-network experiments and the board demo.

## Simulation engine
- Each week, code sets the events (world.py: flight outcomes from seed+persona+leg, offers, wait times; crises.py: strike news timeline and surprises) and Gemini plays every persona (one JSON call per persona-week, status traced to that call). State carries memory, lost/moved bookings and posts; posts reach connections and, for influencers, everyone as trending, the next week.
- Decisions take effect from their week; two-week actions last the decision week and the next. `target_rule` selects who gets the message (`weeks`, `strike_exposed`, `groups`, `disrupted`, `all`).
- Surprises: the dashboard export goes to docs/announcements/team-09_announcements.json. Each new announcement is read once by the model into data/crises/readings.json; **review and edit those readings** (they are our reading of the crisis), then rerun. `plan_nosurprises` drops them; the strike stays.
- Metrics (metrics.py): goal_1 network model; goal_2 disrupted legs resolved within 24h; goal_3 NPS calibrated to +12; goal_3b complaints calibrated to 2,500/month; goal_4 revenue weeks 5-10. Weighted by trips, so heavy ordinary-week personas dominate and single answers can move goal_3b: compare plan vs nodecision across both seeds.
- Until a real surprise is announced, plan_1 and plan_nosurprises send identical prompts and check.py flags it.

## Rules that bite
- **Secrets:** the Vertex key is read from `TALP_KEY`, falling back to the git-ignored `.env`. Never write it anywhere else; `check.py` fails the ZIP if a string matching `AQ.` plus 40 characters appears in any file.
- **The LLM decides behavior.** Code sets events (which flights are canceled, wait times). Gemini decides what each persona thinks, does and their status. Never script outcomes.
- **Statuses** must be the dossier's words: `flies as planned`, `rebooked`, `moved to another airline`, `canceled the trip`; book-again (`yes|maybe|no`) goes in its own field. The scenario prompt defines each status: without the definitions, the model called a Kestrel-arranged partner seat `moved to another airline`.
- **Decision messages** must appear word for word in the targeted personas' prompts from their week on, and never earlier or in `nodecision` runs.
- Every call gets the run's `seed` and temperature 1.0. Model: `gemini-3.5-flash-lite` (about 1 s per call), 30 parallel threads. `parse_json` repairs broken `\u` escapes the model sometimes writes.
- Calendar: week N starts at 13:00 + 30 min × (N-1); decisions must be locked before their week starts, none after 17:30, and the ZIP is due by 18:01.

## Git
- Branches are lowercase with hyphens. Never push to `main` or someone else's branch without asking; open a new branch.
- Commit messages follow the team guideline (docs/guidelines, PDF not in git): imperative mood, present tense, capital first letter, **end with a full stop**. Small change: one line. Medium change: title, blank line, a short why/how paragraph. Large change: summary plus what, why, how, and caveats (NOTE:/TODO). Squash merges start with `[Merge squash commit from branch:X]`. No "oops" commits.

## Persona card skill
`.claude/skills/persona-card/` shows personas as profile cards in chat or as HTML.
