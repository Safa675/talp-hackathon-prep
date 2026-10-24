# Team 09 — week 8 strike simulation comparison

Date: 24 October 2026. Model: `gemini-3.5-flash-lite`; 66 personas; social effects enabled. Each scenario retains the week 3 and 4 engine inspection events and the week 4 decision. The same week 8 ground handling strike event is applied to every scenario. Weeks 1–7 use matching inputs within each seed; the options diverge at week 8. All scenarios ran through week 10 without errors. Results are simulated estimates, not forecasts.

## Decision timing and cost

The week 8 decision can be entered in week 7 as a **future week 8** decision, or entered before running week 8. The engine activates it from week 8; it must not alter weeks 1–7. The known strike event is likewise configured for week 8. Inspection verified that week 7 persona prompts contain no strike event, while all 66 week 8 prompts do. Both comparison sessions contain events in weeks 3, 4, 8 and decisions in weeks 4, 8.

The original week 4 decision costs **$1.05M**. The recommended week 8 package costs **$0.85M**: backup ground handling ($0.50M), partner airline rebooking ($0.25M), and double loyalty points for affected passengers ($0.10M). Combined cost is $1.90M. An alternative replaces points with extra airport and call-center staff ($0.15M): week 8 cost $0.90M, combined cost $1.95M. Both fit the stated $1M remaining cap for the second decision.

## Results through week 10

| Seed | Week 8 package | Flights operated¹ | 24h resolution | Monthly complaints estimate | NPS² | Revenue vs plan |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | No added action | 96.81% | 93.0% | 4,429 | +12.0 | 99.27% |
| 1 | Backup + partner + staff | 96.86% | 100.0% | 4,331 | +25.6 | 100.00% |
| 1 | Backup + partner + points | 96.86% | 100.0% | 4,291 | +25.6 | 98.03% |
| 2 | No added action | 96.81% | 99.8% | 2,645 | +12.0 | 99.74% |
| 2 | Backup + partner + staff | 96.86% | 100.0% | 2,597 | +19.5 | 99.87% |
| 2 | Backup + partner + points | 96.86% | 100.0% | 2,096 | +22.6 | 99.87% |

¹ Network estimate for weeks 1–10, excluding strike-day flights by the scenario's board metric definition. The 98% board target remains unmet in all six runs, largely because the earlier inspection disruptions remain in the total. ² Start-to-end persona probe, translated onto the board's +12 NPS baseline.

For the **16 personas with strike-day flights in week 8**, the no-action scenario had 3 canceled, 8 delayed, and 5 on time in both seeds. The two backup packages had 0 canceled, 3 delayed, 13 on time in seed 1; and 1 canceled, 1 delayed, 14 on time in seed 2. These counts are observations for this persona sample, not network cancellation rates.

The board targets are 98% flights operated, 90% 24h resolution, at most 2,500 complaints per month, NPS at least +20, and at least 96% revenue. The points package meets resolution and revenue in both seeds. It meets NPS in both seeds and the complaint target in seed 2. It does not meet flights operated; seed 1 complaints remain above target. The staff option has slightly stronger revenue in seed 1, but higher cost and weaker complaints/NPS in seed 2.

## Other week 8 packages screened, seed 1

| Package | Week 8 cost | Flights operated | 24h resolution | Complaints | Revenue |
| --- | ---: | ---: | ---: | ---: | ---: |
| Backup + hotel/meal + staff | $0.85M | 96.86% | 93.2% | 4,976 | 100.00% |
| Backup + partner + hotel/meal | $0.95M | 96.86% | 100.0% | 4,411 | 100.00% |
| Lease + partner | $0.95M | 96.92% | 100.0% | 4,553 | 99.82% |
| Backup + goodwill + staff | $0.95M | 96.86% | 93.2% | 4,291 | 100.00% |

The **backup + partner + points** package is the best balanced option among those tested under the $1M second-decision cap. It prioritizes rapid recovery, fewer complaints, and trust. If maximizing simulated revenue in seed 1 is the sole priority, staff or hotel variants score higher there; the two-seed comparison favors points for the broader goals.

## Live sessions and audit records

- `team09_clean_week4`: preserved at the end of week 4, with its original week 3/4 events and week 4 decision; the week 8 strike is configured as a future event.
- `team09_strike_points_ui`: points option, played through week 10.
- `team09_strike_staff_ui`: staff option, played through week 10.
- Each live session has its own event log, state file, and one full weekly log per played week in `code/logs/runs/<session>/<log_id>/`. The two comparison sessions each have ten weekly logs, including reused checkpoint weeks. Batch scenario outputs are in `code/runs/team09_strike_*`.

Open the [local simulation interface](http://127.0.0.1:8766/) and select one of the named sessions. The API also exposes each session's logs at `/api/logs?name=<session>`.
