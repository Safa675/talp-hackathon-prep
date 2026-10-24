---
name: persona-card
description: Show Kestrel Air personas as profile cards (name, tagline, quote, tags, wins over, breaks at, trip, would-book-again bar). Use when asked to show, summarize, compare or present a persona or a persona test run, or to prepare persona visuals for the board.
---

# Persona card

Personas live in `data/personas/personas.json` (archetype -> members). Test results live in
`outputs/persona_tests/<timestamp>-<variant>/results.jsonl`.

## In chat: one card per persona

Render each persona as this block, filled from personas.json and, if a run is given, from results.jsonl:

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

- Name is the first name only; tagline and city come from the member.
- Quote: the member's `quote`, or a line it actually said in the run if the user asks for live output.
- Tags: the member's `tags` (max 3).
- WOULD BOOK AGAIN = `intent` from results (from check-in items 2a and reversed 2b). Leave the bar out if there is no run.
- Never invent scores: a value that is not in the files is left out.

## As a page

```bash
python scripts/render_cards.py                                          # personas only
python scripts/render_cards.py outputs/persona_tests/<run>/results.jsonl # with test results
```

This writes a self-contained `cards.html` (light and dark themes, grouped by archetype, with each persona's interview and week 8 reaction in a collapsible section).
