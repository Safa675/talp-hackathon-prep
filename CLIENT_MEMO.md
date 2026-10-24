# Kestrel Air: memo to the board (Team 09)

## What we decided

| | When, for whom | Actions | Cost |
|---|---|---|---:|
| 1 | Week 4 (Thanksgiving, during the engine inspections), all customers | Lease 1 aircraft with crew for two weeks · extra airport and call-center staff · free changes and cancellations Nov 23–Dec 6 | $1.05M |
| 2 | Week 8 (strike week), all customers | Backup ground handling at both bases on Dec 22–23 · partner-airline rebooking for weeks 8–9 · free changes and cancellations Dec 21–Jan 3 | $0.95M |
| | | **Both decisions** | **$2.00M of $3M** |

**Why.** The grounding took 3 of 36 aircraft out over Thanksgiving, and the lease replaces one of them. The strike hits the busiest days of the year. Backup crews keep the bases turning aircraft around, and the partner deal gets a stranded family home the same day instead of three days later. Free changes until Jan 3 protected travelers in case the union extended the strike. In the end it did not; the strike lasted 48 hours.

## What the simulation says

66 customer personas stand for 2.17 million trips over the ten weeks. Each week they react to what happens to their flights, our messages, the news and their friends' posts. Two seeds per scenario on gemini-3.7-flash, checked again on a second model. These are simulated results, not forecasts.

| Board goal | Target | Our plan | No decision |
|---|---|---:|---:|
| 1 Flights operated (strike days left out) | ≥98% | 96.9% (missed) | 95.1% |
| 2 Disrupted passengers rebooked or refunded within 24h | ≥90% | 100% | 95–99% |
| 3 Complaints | no worse than last winter* | fewer than no decision (10–13 vs 12–19 per 660 customer-weeks) | — |
| 3b NPS (+12 today) | no worse than last winter* | +20 | −15 |
| 4 Revenue, weeks 5–10 | ≥96% of plan | 100% | 99.1–99.6% |
| 5 Budget | ≤$3M | $2.00M | $0 |

\* Last winter's figures are not given; we use today's (2,500 complaints a month, NPS +12). NPS is from the check-in questions, asked in the seed-1 runs.

The plan does better in both seeds. In week 10, trust is 4.1 out of 5 against 3.7–3.8. Customers' willingness to recommend rises 8 points under the plan and falls by 27 points with no decision. On the strike days, cancellations among our customers' 16 flights fall from 3 to 0–1. The second model (gemini-3.5-flash-lite) shows the same direction with bigger gaps: a third to half fewer complaints, and 60–69% would book again against 37–62%.

## What it cannot tell

- **Goal 1 depends on how many flights the grounding really cancels.** Under our reading the plan operates 96.9%; under milder readings of the grounding it reaches 97–98.4%. We would not promise 98%.
- **Goal 2 assumes the partner airline has free seats** in a week that is 97% booked.
- **Sizes.** Simulated customers get the direction right more often than the size, and the two models disagree on how forgiving customers are. Without the surprises the plan pushes NPS to +42 on the second model, which real customers would not do in a strike week.
- **Complaint counts are not calibrated to Kestrel's data**, so we report the direction only.
- **Not simulated:** controllers calling in sick once the Dec 30 paycheck is missed.

## What the company should watch next

1. **Partner seats for Dec 21–Jan 3.** Confirm capacity in writing; Goal 2 rests on it.
2. **The strike's after-effects.** It ended after 48 hours with half the shifts covered. Check bag deliveries and wheelchair complaints from Dec 22–23, and settle the contractor contract before the next peak.
3. **The shutdown.** The House votes after Christmas, and federal workers may miss their Dec 30 paycheck; the FAA says it may slow traffic at busy airports if more controllers call in sick. In 2025 the FAA ordered flight cuts at 40 airports five weeks into the shutdown. Watch New Year week, and plan for capacity cuts if it lasts into January.
4. **The week-4 message.** It said no Kestrel aircraft had a problem with the part, and the update the same week found worn parts on three. Correct the record with the customers who received it.
5. **January complaints and NPS by customer group**, against these simulated directions, to calibrate the next simulation.
