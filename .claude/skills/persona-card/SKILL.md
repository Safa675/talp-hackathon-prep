---
name: persona-card
description: Show Kestrel Air personas as profile cards (name, tagline, quote, tags, wins over, breaks at, trip, would-book-again bar). Use when asked to show, summarize, compare or present a persona or a persona test run, or to prepare persona visuals for the board.
---

# Persona card

Load personas with `kestrel_sim.personas.load_personas("clusters" | "curated")`: both sets come back in
one shape (see CLAUDE.md). Test results live in `outputs/persona_tests/<timestamp>-<set>-<variant>/results.jsonl`.

## In chat: one card per persona

Render each persona as this block, filled from the loaded persona and, if a run is given, from results.jsonl:

```
┌──────────────────────────────────────────────┐
│ [B]  Berat, 22                               │
│      Drexel EE student · Philadelphia, PA    │
│ ┃ "Tell me the real numbers and I'll plan    │
│ ┃  around them."                             │
│ (fixed date) (checks rumors) (Reddit)        │
│ WINS OVER   clear facts, concrete rebooking  │
│ BREAKS AT   next free seat after Christmas   │
│ TRIP        Dec 23 · PHL-MCO · strike-exposed│
│ W8 TEST     rebooked · again: maybe          │
│ WOULD BOOK AGAIN                        75%  │
│ ███████████████░░░░░                         │
│ ● SIMULATED PERSONA · S-A-2                  │
└──────────────────────────────────────────────┘
```

- Name is the first name only; the second line is `tagline · home`.
- Quote: `quote` (curated set only). Cluster personas have none: leave the line out, or use a line the
  persona actually said in the run if the user asks for live output.
- Tags: `tags` (max 3).
- The two labelled rows are `card_rows`: WINS OVER / BREAKS AT for curated, VALUES / WHEN IT GOES WRONG
  for clusters. Add TRIPS from `trips` and STANDS FOR from `weight` (passenger trips over ten weeks).
- WOULD BOOK AGAIN = `intent` from results (from check-in items 2a and reversed 2b). Leave the bar out if there is no run.
- Never invent scores: a value that is not in the files is left out.

## As a page

```bash
python scripts/render_cards.py --personas clusters                                  # personas only
python scripts/render_cards.py --personas curated outputs/persona_tests/<run>/results.jsonl  # with results
```

This writes a self-contained `cards.html` (light and dark themes, grouped by archetype or segment, with each persona's interview and week 8 reaction in a collapsible section).
