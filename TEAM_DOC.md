# Team 09 · Kestrel Air: how we built the simulation

66 LLM personas live through the ten weeks, one model call per persona per week. Code builds the world each persona sees: what happened to its flights, the recovery options that exist for it, the company's message, the news and its friends' posts. The model decides what the person says, does and reports. The hand-in runs use gemini-3.7-flash, a thinking model; we checked every result again with gemini-3.5-flash-lite. Code:
- `code/sim.py`: world and prompts.
- `code/engine.py`: runs, checkpoints, metrics, interviews.
- `code/server.py` and `code/ui/simple.html`: a one-page control room.
- `code/personas_build/`: how the 66 personas were made (segments, raking, LLM fill-in, frozen output).
- `code/experiments/`: the decision experiments behind section 6.

Inputs: `code/personas_66.jsonl`, `code/decisions_team09_fresh.json` and `code/exp/d2_free.json` (the locked decisions), and `code/surprises_team09_week9.json` (the events). The five hand-in runs are in `runs/`.

## 1. Personas: who and why

**How we chose them.** We cut Kestrel's customers into 17 segments across all five dossier groups (for example "Northeast/Midwest families on a Florida theme-park trip", "families visiting relatives in Mexico or the Caribbean", "children flying alone between separated parents"). We crossed them with 4 travel windows: the strike days at a base, the holidays after the strike, Thanksgiving, and ordinary weeks. That gives 68 cells. Agencies booking corporate groups have no strike-day or Thanksgiving trips, which leaves 66 cells, and each cell is one persona.

| Group | Personas | Share of trips they stand for |
|---|---:|---:|
| Vacationers | 16 | 40% |
| Families visiting relatives | 20 | 35% |
| Students | 8 | 10% |
| Business travelers | 12 | 10% |
| Travel agencies (group coordinator speaks for the group) | 10 | 5% |

**Grounding and weights.**
- Segment shares come from the NHTS 2022 air-trip purpose mix (public US data), adjusted for a low-cost carrier.
- The calendar comes from the dossier: 210,000 passengers a week. Week 8 is 97% booked against 86% normally, about 237,000 passengers. The strike days are 2 of week 8's 7 days, and 60% of flights touch a base, about 41,000 trips.
- Thanksgiving and New Year at 230,000 passengers a week are our own assumption.
- We raked (IPF) the segment × window table so it matches both the segment shares and the calendar. Each persona's `represents_trips` is the number of passenger trips its cell stands for: 2,166,863 over the ten weeks, from 3,968 (V-park-strike) to 234,735 (V-park-ordinary).
- Strike-day travelers are oversampled (16 of 66 personas), and the weights correct for that in the metrics.

**What we fixed and what the LLM wrote.**
- We fixed: segment, window, weight, trips (dates and routes), age range, gender and home area.
- gemini-3.5-flash (seed 2026, run once and frozen) wrote the name, occupation, household, income band and a short story.
- The LLM put almost everyone at "medium" on behaviour, so we assigned the behaviour drivers ourselves from stated distributions:
  - date flexibility by segment, with flexibility halved in peak windows;
  - money pressure and knowledge of refund rights by group;
  - loyalty none / member / gold 55 / 38 / 7%;
  - 70% also fly rivals (dossier: "many fly with us twice a year and with someone else the rest of the time");
  - booking channel and social-media activity by age;
  - complaint tendency low / medium / high 50 / 35 / 15%, because most people never complain (2,500 complaints a month on roughly 900,000 passengers);
  - patience and forgiveness 25 / 50 / 25%.

**Why these attributes.** Each crisis reaches people through specific attributes:
- The strike hurts those who need a wheelchair, check bags, fly from a base, or cannot move their dates.
- The grounding hurts fixed-date and international travelers.
- Messages reach people through their channel and social media.
- Leaving depends on whether they also fly rivals, their loyalty tier and money pressure.
- Complaints depend on complaint tendency and knowledge of refund rights.

The persona never sees its simulation labels (segment, window, weight, strike exposure).

## 2. The world

**What a persona sees each week, in one prompt:**
- Kestrel's business-as-usual rules.
- Its persona card and its memory (its last six weekly notes).
- Last week's booking status.
- What happened to each of its flights.
- The news: every announcement from its week on, with our one-sentence report of it.
- The recovery options that really exist for it.
- The company's message, word for word, if the persona is in the decision's target.
- Last week's posts by its three connections, plus up to two trending posts by very active social-media personas.

**What code decides (the world rules in `sim.py`).**
- Flight outcomes are drawn with fixed probabilities: cancel 1.2%, 3-hour+ delay 4%, short delay 17%.
- On the strike days at a base: cancel 30%, delay 45%, checked bags lost 50%, wheelchair wait 60–90 minutes. With backup ground handling: 7%, 15%, 12% and about 15 minutes.
- On Dec 24 without backup, cancellations at the bases are 6 points higher (knock-on).
- An event adds cancellation or delay probability according to our reading of it.
- The leased aircraft halves cancellation probability.
- The next free Kestrel seat is 1 day later normally and 3 days later in weeks 8–9. The partner deal gives a same-day seat.
- Meal vouchers and hotels follow the dossier: only when Kestrel caused the disruption, unless the hotel action is bought.
- The random draws are seeded per persona and week, so every run with the same seed meets the same flights. Plan and no-decision runs are paired comparisons.

**What the model decides.** It answers in JSON:
- the dossier's status, with each status defined in the prompt;
- would book Kestrel again (yes / maybe / no);
- what they did and what they said;
- whether they contacted support;
- whether they complained;
- an optional public post;
- trust from 1 to 5;
- a memory note for next week.

A check-in with the eight questions runs before week 1 and after week 10, and the scores are stored as given.

## 3. How we read each crisis

The engine's reader (gemini-3.5-flash-lite) turns each announcement into an effect on flights (none / delays / some cancellations / many cancellations), which flights it touches, for how many weeks, whether Kestrel caused it, and a neutral one-sentence report. The reading is saved in the events file (`code/surprises_team09_week9.json`), where we can see it and change it. Personas read the original text and the report from the event's week on.

| Week | Announcement | Our reading | Doubts |
|---|---|---|---|
| 3 | FAA and the engine maker order inspections of one engine part; TikTok video of mechanics at a gate | some cancellations, all flights, not Kestrel's doing, week 3 | The checks take aircraft out of service, but nobody knows for how long. |
| 4 | Worn parts on three aircraft; grounded about two weeks; some flights canceled or merged, Thanksgiving included | many cancellations, all flights, not Kestrel's doing, weeks 4–5 | Three of 36 aircraft is 8.3% of capacity. With our leased aircraft, two remain out (5.6%). In the engine, "many" with the lease means +7.5 points of cancellation, and "some" means +2.5; capacity arithmetic lies between. Goal 1 hangs on this reading (section 6). We treated the grounding as not Kestrel's own because the FAA ordered the checks. A DOT-style reading would count maintenance as the airline's own, which brings meals and hotels under business as usual. |
| 7 | Government shutdown; air traffic controllers and TSA officers work unpaid; longer security lines at some airports | delays, the two bases, not Kestrel's doing, week 7 (the reader gave this answer 3 times out of 3) | Probably too strong at the start. In the 2025 shutdown (from Oct 1), the FAA ordered flight cuts at 40 airports only on Nov 7, five weeks in (4%, rising to 10%). |
| 8 | Shutdown update: the Senate passed a short-term bill; the House votes after Christmas; the Dec 30 paycheck may be missed; the FAA may slow traffic at busy airports if more controllers call in sick | delays, the two bases, not Kestrel's doing, weeks 8–9 (2 of 2 readings agree) | We treat the update as the same shutdown going on, so its delays replace the week-7 ones instead of adding to them; otherwise strike week would count the shutdown twice. In past shutdowns sick calls rose once paychecks were missed, so week 9 (Dec 30) is the risk. |
| 8 | Known crisis: 48-hour ground handling strike at both bases, Dec 22–23; "may be extended" (the dashboard's text, in every run including `plan_nosurprises`) | the strike rules in section 2, on Dec 22–23 at the bases | We did not simulate an extension. |
| 9 | Known crisis outcome: the strike lasted 48 hours and was not extended; the contractor covered about half its shifts with replacement staff | no flight effect; news from week 9 on; part of the known crisis, so it is in `plan_nosurprises` too | The reader said "some cancellations" in week 9; we overrode it, because the strike was in week 8 and is over. "Half the shifts covered" fits our no-backup strike rules (30% canceled, 45% late). |

## 4. Our two decisions (as locked)

| | Week | Target | Actions | Cost |
|---|---|---|---|---:|
| 1 | 4 | everyone | free changes and cancellations (2 weeks) · lease 1 aircraft with crew (2 weeks) · extra airport and call-center staff (2 weeks) | $1.05M |
| 2 | 8 | everyone | backup ground handling on the strike days · partner-airline rebooking (2 weeks) · free changes and cancellations (2 weeks) | $0.95M |
| | | | **Both decisions** | **$2.00M of $3M** |

The messages are in `runs/*/run.json` word for word. Decision 1's message said "no Kestrel aircraft has had a problem with this part". We wrote it on the week-3 facts, and the week-4 update (worn parts on three aircraft) made it false the week it was sent. We could not change it after week 4 started. The lesson: no absolute claims about a situation that is still unfolding. The personas punished it less than real customers probably would.

## 5. From persona behaviour to the board's goals

Each persona row counts with its `represents_trips` weight. "No worse than last winter" uses the November 2 levels (2,500 complaints a month, NPS +12), because last winter's numbers are not given.

| Goal | How we compute it | Who decides it |
|---|---|---|
| 1 Flights operated ≥98% | Network formula: about 1,355 flights a week × the world's cancellation rates; strike days left out | Code (our assumptions), not the personas |
| 2 Rebooked or refunded within 24h ≥90% | Share of weighted persona flights canceled or 3h+ late that were rebooked within 24h, or whose trip was canceled (refund) | Mostly code: the recovery rules decide when the next seat is |
| 3 Complaints | 2,500 × (this run's complaint rate ÷ its complaint rate in weeks without events) | The personas' complaint flags; only a direction (section 7) |
| 3b NPS | +12 plus the change in check-in question 3a (5 = promoter, 1–3 = detractor) | The personas' check-in answers |
| 4 Revenue weeks 5–10 ≥96% | Weighted trips lost (moved to another airline or canceled the trip) × fare ($120 domestic, $210 international) | The personas' statuses |

## 6. Experiments

**E1. Which week-8 package (gemini-3.5-flash-lite, seeds 1–3, weeks 1–7 identical within each seed; `code/experiments/team09-decision-retest.md`).** Totals over three seeds; 16 persona flights on the strike days per seed.

| Week-8 package | Cost | Strike-day cancellations / 48 | Resolved within 24h, weeks 8–9 | Complaints, weeks 8–9 (of 396 persona-weeks) | "Would book again: yes", week 10 (of 198) |
|---|---:|---:|---:|---:|---:|
| None (decision 1 only) | $0 | 9 | 27/38 | 27 | 143 |
| Backup + partner | $0.75M | 2 | 13/13 | 16 | 154 |
| Backup + partner + points | $0.85M | 2 | 13/13 | 11 | 153 |
| Backup + partner + staff | $0.90M | 2 | 13/13 | 15 | 149 |
| Backup + partner + free changes | $0.95M | 2 | 13/13 | 14 | 154 |

Backup ground handling plus the partner deal does the work. No third action was consistently better, and the gaps between them are a few complaint flags. A week-7 version lost partner cover in week 9 (resolution 3/4 against 4/4), so we chose week 8. We kept free changes as the third action because the union says the strike "may be extended", and free changes until Jan 3 protect travelers if it is. That choice rests on the risk, not on the simulation.

**E2. Second model (seed 1, gemini-3.7-flash against 3.5-flash-lite; `code/experiments/team09-model-check-3.7-flash.md`).** The week-8 conclusion holds with both models.

| Model | Week-8 package | Goal 2 | NPS | Complaints, weeks 8–9 |
|---|---|---:|---:|---:|
| 3.7-flash | none / free changes / points | 93.0% / 100% / 100% | −6.2 / +19.5 / +16.5 | 5 / 2 / 1 |
| 3.5-flash-lite | none / free changes / points | 91.8% / 100% / 100% | +9.0 / +18.1 / +22.6 | 9 / 3 / 3 |

The two models rank the third action in opposite orders, so we read it as noise. Absolute levels move with the model and comparisons do not, so we never mix models in one table for the board. All five hand-in runs on 3.7-flash took 8 minutes. Flash-lite takes about one minute, so it is our fallback if a late announcement leaves too little time.

**E3. How much Goal 1 depends on our crisis reading** (from the engine's formula, any seed):

| Week 3 / week 4 reading | No decision | Our plan |
|---|---:|---:|
| some / many cancellations (our reading) | 95.14% | 96.86% |
| some / some | 97.20% | 97.89% |
| delays / some | 97.72% | 98.41% |
| Capacity arithmetic: 2 of 36 aircraft out in weeks 4–5 with the lease | n/a | about 97.1–97.7% |

The 98% goal is met only under the mildest reading. The plan lands between 96.9% (our reading) and 98.4% (the mildest). Delays do not count against Goal 1, so the shutdown reading does not change these figures.

**E4. The hand-in runs: the plan against no decision, with every announcement** (gemini-3.7-flash, events through the week-9 strike outcome, engine version 3; `runs/`):

| | Plan, seed 1 | Plan, seed 2 | No decision, seed 1 | No decision, seed 2 | Plan, surprises off |
|---|---:|---:|---:|---:|---:|
| Goal 1: flights operated (target ≥98%) | 96.86% | 96.86% | 95.14% | 95.14% | 98.92% |
| Goal 2: resolved within 24h (≥90%) | 100% | 100% | 94.6% | 99.4% | 100% |
| Goal 3: complaints a month (direction only) | 742 | 903 | 1,390 | 971 | 40 |
| Complaint flags (of 660 persona-weeks) | 10 | 13 | 12 | 19 | 1 |
| Goal 3b: NPS (+12 basis; check-ins in seed 1 only) | +19.6 | — | −15.3 | — | — |
| Raw check-in NPS, start → end | +1.5 → +9.1 | — | +1.5 → −25.8 | — | — |
| Goal 4: revenue weeks 5–10 (≥96%) | 100% | 100% | 99.12% | 99.55% | 100% |
| Trust in week 10 (1–5, all 66 answered) | 4.12 | 4.12 | 3.77 | 3.70 | 4.50 |
| "Would book again: yes", week 10 (weighted) | 87% | 91% | 83% | 85% | 100% |
| Strike-day flights (16): canceled / 3h+ late | 0 / 3 | 1 / 1 | 3 / 8 | 3 / 8 | 0 / 3 |

Both messages reached all 66 personas word for word from their weeks (0 before). In both seeds the plan does better on trust, on resolving disruptions within 24h, on strike-day cancellations and on revenue. In seed 1 the check-in NPS rises 7.6 points under the plan and falls 27.3 without decisions. On 3.7-flash the gap in complaints and "would book again" is small: the personas are more forgiving across the board (they start at NPS +1.5, against −26 on flash-lite). The "moved to another airline" rows in the runs are real switches; for example, a corporate agency whose group flight was canceled in week 3 took the refund and booked another airline.

**E4b. The same inputs on the second model** (gemini-3.5-flash-lite, check-ins switched on in every run):

| | Plan, seed 1 | Plan, seed 2 | No decision, seed 1 | No decision, seed 2 | Plan, surprises off |
|---|---:|---:|---:|---:|---:|
| Goal 2: resolved within 24h | 100% | 100% | 95.0% | 99.8% | 100% |
| Complaint flags (of 660) | 21 | 21 | 31 | 42 | 8 |
| Goal 3b: NPS (+12 basis) | +13.6 | +10.5 | −13.7 | −6.2 | +42.3 |
| Raw check-in NPS, start → end | −25.8 → −24.2 | −27.3 → −28.8 | −25.8 → −51.5 | −27.3 → −45.5 | −25.8 → +4.5 |
| Goal 4: revenue weeks 5–10 | 98.03% | 100% | 93.95% | 99.74% | 100% |
| Trust in week 10 (1–5) | 3.48 | 3.59 | 3.14 | 3.09 | 4.14 |
| "Would book again: yes", week 10 | 60% | 69% | 37% | 62% | 99% |

Goals 1 and the strike-day flights are the same as in E4, because code decides them. Flash-lite shows the same direction with bigger gaps: a third to half fewer complaints, and an NPS that holds instead of falling 18–26 points. The plan's revenue loss in seed 1 is one real switch: a persona offered a same-day partner seat "booked a last-minute ticket on a rival airline" instead. No-decision revenue swings between seeds (93.95% against 99.74%), so one seed proves little. With the surprises off, the plan lifts NPS to +42. Real customers would hardly reward a strike week that much, so we treat NPS gains as an upper bound.

**E5. Placebo (an earlier version of the world, before the inspection events).** Two friendly holiday greetings with no actions did not raise the NPS goal against no decision (−42.4 vs −36.4 with seed 1, −37.9 vs −42.4 with seed 2). A plan with real actions did (−22.7 in both seeds). The personas react to what happens to them, not to any message.

## 7. Problems we hit and how we solved them

- **Runs too slow to repeat.** Every week ends in a checkpoint named by a hash of everything that can change it: prompt code, personas, model, seed, the decisions in force and the events announced so far. A late announcement re-runs only the weeks it touches, and runs that share a beginning share those weeks. All 66 personas of a week run in one wave with low thinking; medium thinking doubled the wait. A full flash-lite run takes about two minutes from scratch, and all five hand-in runs on 3.7-flash took 8 minutes.
- **Events added after weeks were played.** A live session keeps played weeks as history, so a late event acts from the next week. The page says so. We make the hand-in runs in batch, from the start, after the last announcement.
- **A partner-airline rebooking was reported as "moved to another airline"**, which Goal 4 counted as lost revenue. In one run, a persona that said "Kestrel successfully rebooked us onto a partner airline the same day" was booked as a lost customer. We now define each status in the prompt. The same persona now reports "rebooked", and that run's Goal 4 went from 98.03% to 100%.
- **The dashboard names the actions differently** ("Lease aircraft with crew", level "Enable"). The engine now matches actions by keyword and stops before any call if an action matches nothing, so no action can silently do nothing.
- **Survey answers bunch at 4.** At the start, 45 of 66 personas answer 4 to "would you recommend", and only 2 answer 5. Raw NPS is therefore −26 with flash-lite, but +1.5 with 3.7-flash for the same personas. We report the change from the start, never the level. One persona is worth 1.5 NPS points.
- **Complaints are rare, which makes Goal 3 fragile.** In weeks without events the personas almost never complain. That rate sits below the 1% floor in the formula, so Goal 3 rests on a handful of complaint flags: 10–19 per 660 persona-weeks on 3.7-flash, 21–42 on flash-lite. The same no-decision run gives 1,390 complaints a month on 3.7-flash and 5,888 on flash-lite. We read it as a direction only.

## 8. What the simulation cannot tell yet, and what we would do with more time

- **Sizes.** LLM personas get the direction of an effect right more often than its size, and their answers are less spread than real people's. Without surprises the plan pushes NPS to +42 on flash-lite, which no real airline would see in a strike week. We report directions and ranges.
- **Goals 1 and 2 are our assumptions.** The strike, backup, lease and partner probabilities are our estimates, not data. The partner airline always has a seat in the engine, in a week that is 97% booked. One leased aircraft and two have the same effect.
- **Real complaint rates.** In December 2022 about 0.4% of stranded passengers filed a DOT complaint (Southwest's meltdown: 8,729 DOT complaints for about 2 million stranded). With Kestrel's complaint data we would calibrate the complaint flag instead of using the floor.
- **A strike extension, or controllers calling in sick after the missed Dec 30 paycheck,** are not in the runs. We would run them as scenarios.
- **With more time:** more seeds per decision; each crisis reading run as its own scenario instead of one choice; personas checked against Kestrel's real survey spread; the social network built from data instead of three links each.
