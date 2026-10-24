# Team 09 simulation engine validation, 24 October 2026

All runs below use the same 66-person v2 panel, seed 1, social graph, and Gemini 3.5 Flash Lite. The ordinary timeline has the week-3 inspection, week-4 aircraft update, week-7 shutdown and update, and week-8 known strike. The original week-4 decision remains in every action comparison. All model calls in the completed comparisons succeeded. The full call, prompt, response, event, decision, and checkpoint record for each run is in `code/logs/runs/<run>/<log_id>/` on this machine; `engine.json` in `code/runs/<run>/` records the log ID.

## Causal controls

| Change to the same timeline | Identical prefix | First affected week and observed result |
| --- | --- | --- |
| Remove week-3/4 announcements | Weeks 1–2 | Week 3 trust 3.85 versus 3.56; 52 versus 41 would book again |
| Remove week-4 decision | Weeks 1–3 | Week 4 trust 3.21 versus 3.42; 26 versus 38 would book again |
| Remove week-7 shutdown news and update | Weeks 1–6 | Week 7 trust 3.68 versus 3.67; 46 versus 47 would book again. Nine individual trust answers changed; the effect is behavioral news, not a fabricated flight cancelation |
| Remove week-8 strike | Weeks 1–7 | Week 8 has 1 versus 13 affected itineraries, 1 versus 12 complaints, and 26 versus 23 operated itineraries |
| Add week-8 backup handling, partner rebooking, and double points | Weeks 1–7 | Week 8 has 4 versus 13 affected itineraries, 4 versus 12 complaints, and 26 versus 23 operated itineraries; trust 3.52 versus 3.20 |

The full ten-week runs have 660 weekly persona records each. Relative to no week-8 action, the points package changes week-8/9 complaints from 18 to 5, week-10 trust from 3.41 to 3.76, and direct end-survey NPS from -31.8 to -3.0. Without double points, the package's direct end NPS is -6.1. The week-8 action costs $0.85M, within the stated $1M remaining; the two decisions cost $1.90M combined. These are one-seed panel experiments, not a guaranteed optimum. This seed's points package still misses the +12 NPS and 98% flight-operation board targets.

## Measurement and fixes

- Announcements enter the prompt and flight world in their stated week, and decisions enter only from their own week. Altering a played week's input invalidates that week and later; the live run replays them while preserving earlier checkpoints.
- The `within_24h` world field says a timely option was available. It does **not** by itself prove the traveler accepted rebooking or received a refund. The displayed and saved 24-hour recovery metric now counts only a recorded `rebooked` status with a timely option. Refund completion time is not modeled, so its cases stay unknown. This produces conservative modeled recovery estimates of 19.1% without the week-8 action and 26.5% with it, rather than previously inflated values.
- The modeled monthly complaint estimate now uses the same pre-event weeks 1–2 comparator across variants. Otherwise an intervention that reduced later complaints could perversely raise its own estimate by lowering its denominator. The new estimates are 2,619 without the week-8 action and 2,156 with the points package. The UI also shows each week's raw complaint count; neither number is an observed Kestrel network total.
- The UI's weekly cards use the individual weekly records. Network flight rate and monthly complaints in `metrics.json` are scenario estimates, with their units and assumptions stated. NPS is calculated directly from the recorded end survey, never by adding a dossier baseline.
- Every run keeps its own append-only event history and a complete `week-NN.json` record, even when a checkpoint is shared. The batch CLI no longer loads or rewrites a live session while another process plays it. Checkpoints use cross-process locks, so parallel runs cannot race to create the same week or start survey.

Validation: `code/.venv/bin/python -m unittest discover -s code -p 'test_engine_consistency.py' -v` (7 passing tests), `py_compile`, and real model control runs with zero errors.
