# Team 09: is the week 8 decision robust to the model? (gemini-3.7-flash vs gemini-3.5-flash-lite)

Date: 24 October 2026, 15:38–15:47. Author: Safa (with Claude). Results are simulated, not forecasts.

## Question

All decision experiments so far ran with `gemini-3.5-flash-lite`. The engine notes `gemini-3.7-flash` (a thinking model) as the hand-in model. Two questions:

1. Does the week 8 conclusion still hold with the other model?
2. How long do runs take with 3.7, given that the five hand-in runs must be redone after the 17:30 announcement and uploaded by 18:01?

## Setup

- Engine: `sim-engine-ui` at `588fe38`. `sim.py` is identical to `6665b9a`, which the 3.5-lite comparison runs used, so the prompts are the same.
- 66 personas (`personas_66.jsonl`), social interaction on, seed 1, `--probe`.
- Events: `surprises_team09_clean_week4.json` (week 3 inspection, week 4 worn parts, week 8 strike as the known crisis).
- Decision 1 is the locked week 4 decision from `decisions_team09_fresh.json` ($1.05M), the same in every run.
- Three week 8 options (files in `code/exp/`):
  - `d2_none.json`: no week 8 decision (decision 1 only).
  - `d2_free.json`: backup ground handling + partner airline + free changes ($0.95M).
  - `d2_points.json`: backup ground handling + partner airline + double loyalty points ($0.85M, Mehmet's file).
- 3.5-lite reference: runs `m_b_*_s1` (same inputs, seed 1).

## Runtime and cost

| | gemini-3.7-flash | gemini-3.5-flash-lite |
|---|---|---|
| Three runs in parallel, 30 workers each | **about 9 minutes** (15:38:32 → 15:47:35) | about 1–2 minutes |
| Calls per run (10 weeks + check-ins) | 792 | 792 |
| Tokens per run (`d2_free`) | 1,176,855 in · 107,424 out · 5,680 thinking | — |

Five hand-in runs from scratch with 3.7 after 17:30 would take 10+ minutes before the ZIP and `check.py`. That is tight for an 18:01 upload.

## Results (seed 1)

| Model | Week 8 option | Goal 1 flights | Goal 2 24h | NPS (+12 basis) | Goal 4 revenue | Book again "yes" (weighted) | Trust change | Complaints wk 8–9 | Strike-day cancellations | Resolved wk 8–9 | Lost personas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3.7-flash | none | 96.81% | 93.0% | −6.2 | 99.00% | 85% | −0.29 | 5 | 3 | 11/15 | 3 |
| 3.7-flash | free changes | 96.86% | 100.0% | +19.5 | 98.03% | 87% | 0.00 | 2 | 0 | 6/6 | 1 |
| 3.7-flash | points | 96.86% | 100.0% | +16.5 | 98.03% | 87% | −0.03 | 1 | 0 | 6/6 | 1 |
| 3.5-lite | none | 96.81% | 91.8% | +9.0 | 100.00% | 76% | −0.21 | 9 | 3 | 11/15 | 2 |
| 3.5-lite | free changes | 96.86% | 100.0% | +18.1 | 100.00% | 74% | −0.05 | 3 | 0 | 6/6 | 2 |
| 3.5-lite | points | 96.86% | 100.0% | +22.6 | 98.03% | 72% | +0.06 | 3 | 0 | 6/6 | 1 |

Goal 1 and the strike-day cancellations are the same across models. They come from the world rules in code, not from the model.

## Findings

1. **The week 8 decision holds with both models.** With 3.7, backup ground handling + partner airline vs no week 8 decision moves 24h resolution from 93% to 100%, NPS from −6 to +17/+20, trust from −0.29 to about 0, and complaints in weeks 8–9 from 5 to 1–2. 3.5-lite shows the same direction. We can say the conclusion was checked with a second model.
2. **The third action is noise.** On NPS, 3.7 ranks free changes above points (+19.5 vs +16.5) and 3.5-lite ranks points above free changes (+22.6 vs +18.1). Together with Mehmet's three-seed retest and our two-seed runs, no third action is consistently better. The saved decision (free changes) stays; the choice rests on the union's "may be extended" warning, not on the simulation.
3. **Absolute levels move with the model, comparisons do not.** 3.7 personas start more negative (no-decision NPS −6 vs +9) and say "book again: yes" more often (85% vs 76%). Compare options within one model; do not mix models in one table for the board.

## Bug found: partner-airline rebooking is counted as a lost customer (goal 4)

In both 3.7 plan runs, revenue is **lower** than with no decision (98.03% vs 99.00%). All of the gap comes from one persona, `F-adultkids-holiday` (52,478 trips):

| Run | Week 9 | Persona's action | Status reported |
|---|---|---|---|
| none | canceled, not within 24h | "Accepted rebooking on the next available Kestrel flight 3 days later" | rebooked |
| free changes | canceled, within 24h | "Accepted rebooking on a partner airline via the mobile app … today" | **moved to another airline** |
| points | canceled, within 24h | "Accepted the rebooking on a partner airline for the same day" | **moved to another airline** |

goal_4 counts "moved to another airline" as lost revenue: 52,478 × $120 = **$6,297,360**. So the plan is penalised for working. A seat on a partner that Kestrel arranged is a rebooking, not a lost customer. The same mechanism explains the earlier revenue dips in plan runs (e.g. A2 seed 1); earlier explanations calling them a one-off model choice were wrong.

**Fix before the hand-in runs** (either):
- prompt rule: "a seat on a partner airline that Kestrel arranged for you counts as `rebooked`"; or
- in goal_4, do not count a persona as lost in a week where it accepted Kestrel's partner rebooking.

## Recommendation for the hand-in runs

- **Model: `gemini-3.5-flash-lite`.** Same conclusion as 3.7, every decision experiment used it (consistent numbers for the board), and it reruns in about a minute after 17:30. The jury said the model's brand earns no points.
- If the team prefers 3.7: start the five hand-in runs with 3.7 **now**, so that after 17:30 the checkpoints re-run only the weeks touched by late announcements.
- Either way, fix the partner-rebooking status first, and check the locked decisions JSON from the dashboard (target and exact message) before the official runs.

## Files

- Inputs: `code/exp/d2_none.json`, `code/exp/d2_free.json`, `code/exp/d2_points.json`.
- Runs (local, not tracked): `code/runs/q37_{none,free,points}_s1/` and the 3.5-lite reference `code/runs/m_b_{none,free,points}_s1/`.
- Note: the free-changes message in these runs is the earlier wording; the dashboard message was revised afterwards for accuracy (same actions).
