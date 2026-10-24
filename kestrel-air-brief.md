# TALP Simulation Lab: Kestrel Air Brief

Working notes on the challenge and our client. Decisions are intentionally not covered here yet.

Sources: `yeni-case-5-sirket/02-challenge.md`, `yeni-case-5-sirket/03-audience-attributes.md`, `13-kestrel-air.md`, `yeni-case-5-sirket/check.py`.

---

## 1. The challenge in one paragraph

We are a simulation lab. Five US companies came to us because the next ten weeks will be hard and they do not know their customers well enough to choose what to do. Each lab works for one company (drawn at 10:30, two labs per company). We build the company's people as LLM personas, live through the ten weeks with them, and make exactly two decisions on the company's behalf. At 18:30 we present to the company's board.

**What is scored:** reasoning, an idea of our own, how we compared approaches and what we learned, a working example, and what the simulation cannot tell yet plus what we would do next. The simulated company result is not scored. Model brand, number of personas and polished slides earn nothing extra. The board will pick one of our personas and ask it a question live.

**Hard rule:** the LLM must produce what personas say, do and decide. A script that writes the outcome is not a simulation, and the checks will show it.

---

## 2. Calendar

Ten weeks, Monday Nov 2 to Sunday Jan 10. From 13:00 the calendar runs in real time: every 30 minutes is one week.

| Week | Dates | Starts at |
|---|---|---|
| 1 | Nov 2-8 | 13:00 |
| 2 | Nov 9-15 | 13:30 |
| 3 | Nov 16-22 | 14:00 |
| 4 | Nov 23-29 (Thanksgiving, Black Friday) | 14:30 |
| 5 | Nov 30-Dec 6 | 15:00 |
| 6 | Dec 7-13 | 15:30 |
| 7 | Dec 14-20 | 16:00 |
| 8 | Dec 21-27 (Christmas) | 16:30 |
| 9 | Dec 28-Jan 3 (New Year) | 17:00 |
| 10 | Jan 4-10 | 17:30 (ends 18:00) |

Submission deadline is 18:00. Board presentations start at 18:30.

---

## 3. How decisions work (mechanics only)

- Exactly **two** decisions, in any weeks we choose. Both in the same week is allowed.
- A decision is locked on the dashboard. It takes effect at the **start of the week named** and must be locked **before** that week starts.
- Cannot decide in the past: a decision locked after its week has started moves to the next week that has not started. **After 17:30 no decision can be locked.**
- Until its week starts we may replace a decision. The last version before the start counts.
- Each decision has:
  - the week
  - who it is for: everyone, or a group we describe
  - one to three actions from the dossier menu, each at one of the listed levels
  - the message the company sends: exact words, **max 600 characters**, plus channels
  - why, in three lines
- The cost of all actions in both decisions together (paid messages included) must fit the budget. Costs are the CFO's estimates and are used as given.
- A decision must be one a real board would approve: inside the menu, inside the budget, inside the red lines.
- Outside our two decisions the company does "business as usual".
- Personas read our message word for word from its week on; the company sends it only to the decision's target.

---

## 4. Crises

- **One we know about:** in the dossier (see section 7).
- **Others we do not know:** arrive as dashboard announcements at the start of a week; some get an update a week later. We will not know when, what, or how many.
- Crisis texts are deliberately vague. How big it is, who hears about it, how people feel and what they do is our simulation's job. **We must write down how we read each crisis.**
- A crisis announced at the start of week N is already happening in week N. The earliest decision that can answer it is in week N+1.
- Crises are serious but survivable. If the simulation says half the customers leave in a week, check the simulation.

---

## 5. What we build

- **Personas:** at least 24, covering at least 3 groups from the dossier, at least 4 personas per group used. Attributes come from the audience catalog plus dossier sector attributes. Nobody gives us distributions; we may ground them in public data (e.g. Census ACS) and must say which. We choose and explain why.
- **A world over ten weeks:** what personas see (company messages, news, social media, friends, support), what they can do (complain, post, ask a friend, call support, switch, wait...), and how the world state changes week to week.
- **Crises and decisions as inputs:** same code with a different decision file, or with surprises switched off, must give a different run.
- **Metrics:** how persona behavior becomes the board's goals, and how many real customers each persona stands for.
- **Experiments:** which decisions we tried, in which weeks, how many times.

### Audience attribute catalog (summary)

Categories A-I. For each attribute we use, decide its values, its distribution and why, and its form (fixed field, narrative line, memory, or changing over time).

- **A. Demographic:** age, gender, state, urbanicity, household size, marital status, children, education, occupation, employment, employer type, income band, rent/own, car.
- **B. Life story:** tenure as customer, past bad experience, recent life event, moved from elsewhere, family far away, online history, first-gen college, military.
- **C. Values and attitudes:** what they value most, risk attitude, trust in institutions, brand loyalty, price consciousness, sense of fairness, need for control, etc.
- **D. Behavior:** usage frequency, spend, preferred channel, coupons, complaint history, reviews, social media, uses a rival, payment method, planning style.
- **E. Emotions and reactions:** baseline anxiety, anger speed, patience, forgiveness, embarrassed to complain, FOMO, mood this week.
- **F. Social and information:** news sources, circle size, opinion leader vs follower, rumor belief, who they ask.
- **G. Money pressure:** savings, card debt, student loans, credit band, paycheck to paycheck, price worry, who pays.
- **H. What they can do:** complain in app, call support, post a review, regulator/BBB complaint, social post, tell friends, dispute a charge, use less, pause, switch, wait, refund/credit request, small claims, recommend, do nothing.
- **I. Lifestyle and personal details:** zodiac, favorite color, team, pet, music, coffee, etc. (mostly noise; use only with a reason).

**Fairness note:** sensitive traits (race/ethnicity, religion, health, political views, immigration status) are not in the catalog. If added, say why the client's question needs it. Do not build stereotypes; the board will ask.

`TEAM_DOC.md` must say what we used, what we left out, and why.

---

## 6. Check-in questions (probe)

Ask every persona all eight questions twice: before week 1 (`start`, call week 0) and after week 10 (`end`, call week 11), only in runs `plan_1` and `nodecision_1`. Put "Kestrel Air" in place of {company}. Answers are whole numbers 1-5. Store scores as given; **2b and 4b are worded the other way round on purpose.**

| | Wording a | Wording b |
|---|---|---|
| 1 Trust | How much do you trust {company}? 1 = not at all, 5 = completely. | "I can count on {company} to treat me right." 1 = strongly disagree, 5 = strongly agree. |
| 2 Staying | How likely are you to keep using {company} over the next three months? 1 = very unlikely, 5 = very likely. | "I am thinking about leaving {company}." 1 = strongly disagree, 5 = strongly agree. |
| 3 Recommending | How likely are you to recommend {company} to a friend or colleague? 1 = very unlikely, 5 = very likely. | If a friend asked you about {company} today, what would you tell them? 1 = stay away, 5 = go for it. |
| 4 Fairness | How fairly has {company} treated you? 1 = very unfairly, 5 = very fairly. | "{company} takes advantage of people like me." 1 = strongly disagree, 5 = strongly agree. |

---

## 7. Client dossier: Kestrel Air

Fictional company. Sector: aviation (low-cost airline).

### Who they are

- Founded 2011, bases in **Orlando** and **Philadelphia**.
- 36 aircraft of one family.
- Flights: US domestic 75%, Mexico and Caribbean 25%.
- 11 million passengers a year, 3,400 staff.
- Ground handling at both bases (baggage, cabin cleaning, wheelchair assistance, fueling) is done by a **contractor**.

### CEO letter (Marcus Hale), key points

- The holidays are when the airline earns its reputation, not its money.
- Christmas week is the busiest of the year (families going home, students flying back, everyone heading south).
- The contractor's workers announced a **48-hour strike at both bases on December 22-23**.
- "What passengers remember is not the delay; it is how we treated them."
- The board reminds him every week what a spare aircraft costs.

### State on November 2

- 210,000 passengers a week; seats 86% full; 79% of flights on time.
- Average fare: within the US **$120**, Mexico and Caribbean **$210**.
- **6 in 10** Kestrel flights start or end in Orlando or Philadelphia.
- Flights in **week 8 are 97% booked**.
- About 2,500 complaints a month, about 150 of them to the Department of Transportation (DOT). Net promoter score **+12**.
- DOT rules on refunds for canceled or significantly delayed flights are always followed. They are not our decision.

### Customers

Price-conscious travelers: families visiting relatives, students, vacationers, and some small business travelers. Many fly with Kestrel twice a year and with someone else the rest of the time.

**Groups we can simulate:** vacationers, families visiting relatives, students, business travelers, travel agencies that book group tickets.

### Sector attributes (in addition to the catalog)

how often they fly - reason for the trip - fixed date or flexible - travels with children or elderly parents - needs help at the airport (wheelchair, child flying alone) - loyalty tier - afraid of flying - knows their refund rights - has TSA PreCheck - books through an agency or online - checks a bag - how they get to the airport - tolerance for connections - window or aisle - buys snacks on board - favorite destination - the employer pays for the ticket

### Board goals by January 10

1. At least **98% of planned flights operated** over the ten weeks, not counting the strike days.
2. On disrupted days, at least **90% of affected passengers rebooked or refunded within 24 hours**.
3. **Complaints and net promoter score no worse** than last winter.
4. **Revenue from week 5 to week 10: at least 96% of plan.**
5. Both decisions together within **$3 million** (budget goal; not reported in `metrics.json`).

### Red lines

- Safety is never traded for anything.
- No false or misleading statement.
- Refunds the rules require are always paid; they are not a decision.
- No canceling all flights at a base.

### Business as usual (what happens if we do nothing)

- A canceled flight is rebooked on the next Kestrel flight with a free seat, or refunded.
- Call center and app; normal wait is 9 minutes, much longer on disruption days.
- Meal vouchers for Kestrel-caused delays over 3 hours; hotels only for overnight delays Kestrel causes.
- Fares follow the normal pricing system.

### Decision menu (budget $3 million for both decisions)

| Action | Levels and cost (CFO estimate) |
|---|---|
| Lease an aircraft with crew for 2 weeks | 1 aircraft: $0.7M, 2 aircraft: $1.4M |
| Backup ground handling contract at both bases for the strike days | $0.5M |
| Free changes and cancellations for bookings in a 2-week window | $0.2M |
| Goodwill for affected passengers, up to 10,000 passengers | $75 travel credit: $0.3M (most credits are used on seats that would fly empty); $50 cash: $0.5M |
| Rebooking deal with a partner airline for 2 disrupted weeks | $0.25M |
| Hotel rooms held for stranded passengers, whatever the cause | $0.2M |
| Extra airport and call-center staff for 2 weeks | $0.15M |
| Fare cap on the busiest routes for 2 weeks | $0.5M (lost revenue) |
| Fare sale on quiet routes for 2 weeks | $0.3M |
| Double loyalty points for affected passengers | $0.1M |
| Merge low-load flights, announced at least 7 days ahead (passengers moved to other flights) | saves $0.25M (adds to the budget) |

Messages: app, email and text messages to booked passengers are free; social media posts are free.

### The crisis we know is coming

**Week 8, Tuesday Dec 22 and Wednesday Dec 23: 48-hour strike by the ground handling contractor's workers in Orlando and Philadelphia.**

- Baggage handlers, cabin cleaners, wheelchair agents and fuelers employed by the contractor plan to walk out for 48 hours.
- The contractor says it will bring in replacement staff "where it can". Turnarounds will be slower; some flights may be late or canceled.
- The union says the strike "may be extended". Talks continue.
- It is the busiest holiday week of the year.

### What each persona reports every week

- Passenger: `flies as planned` / `rebooked` / `moved to another airline` / `canceled the trip`.
- Would book Kestrel again: `yes` / `maybe` / `no` (goes in a field of our own, e.g. `"rebook_intent": "maybe"`).
- Anything else our metrics need.

---

## 8. What we hand in by 18:00

One ZIP on the dashboard: `team-NN_submission.zip`

- our code
- five runs, all with the same personas and every announcement made before 18:00:
  - `plan_1`, `plan_2`: our plan (the two locked decisions), two seeds
  - `nodecision_1`, `nodecision_2`: no decisions (business as usual only), two seeds
  - `plan_nosurprises`: our plan with every surprise and its updates switched off (the known strike stays), one seed
- `CLIENT_MEMO.md`: one page for the board (what we decided and why, what the simulation says, what it cannot tell, what to watch next)
- `TEAM_DOC.md`: how we built it (personas and why those attributes, the world, how we read each crisis, experiments, problems and fixes, what we would do with more time)

Runs must be fast enough to repeat, because we will need to re-run after a late announcement.

### ZIP layout

```
team-NN_submission.zip
  CLIENT_MEMO.md
  TEAM_DOC.md
  code/
  runs/
    plan_1/  plan_2/  nodecision_1/  nodecision_2/  plan_nosurprises/
      run.json  personas.jsonl  calls.jsonl  weekly.jsonl  metrics.json
      probe.jsonl       (plan_1 and nodecision_1 only)
```

### File formats

- **`run.json`:** `company` = `kestrel`, `type` (`plan`, `nodecision`, `plan_nosurprises`), `seed`, `model`, `decisions` (empty list in nodecision runs). Each decision: `week`, `target`, `actions` (1-3, each `action` + `level`; `"level": "on"` if no levels), `message`, `channels`, `why`.
- **`personas.jsonl`:** one line per persona: `id`, `group`, plus anything else. Identical in all five runs.
- **`calls.jsonl`:** every LLM call: `id`, `persona` (id or null), `week` (1-10; 0 before week 1; 11 after week 10), `prompt` (full text), `response` (full text), `model`.
- **`weekly.jsonl`:** one line per persona per week (1-10): `persona`, `week`, `status`, `call`. `status` must be one of the four Kestrel statuses above, and the referenced call's response must contain those words (ask the model to end with e.g. `Status: rebooked`). Second line (would book again) goes in our own field.
- **`metrics.json`:** `goal_1` to `goal_4` (one number per board goal, budget goal excluded; `goal_3b` etc. allowed for two-part goals) plus `units` explaining each number.
- **`probe.jsonl`:** one line per answer: `persona`, `when` (`start`/`end`), `question` (`1a` to `4b`), `score` (1-5), `call`.

Run `python3 check.py team-NN_submission.zip` before uploading. It reads only; it never runs our code.

### What `check.py` verifies (so we do not trip it)

- All five run folders and required files exist; both docs and a `code/` folder exist.
- No Vertex key (pattern `AQ.` + 40 chars) anywhere in the ZIP.
- At least 24 personas, at least 3 groups, at least 4 per group; unique ids; same personas in all runs.
- Exactly 2 decisions in plan runs, 0 in nodecision; message at most 600 chars; plan runs use identical decisions.
- Decision message appears word for word in persona prompts from its week on, **never before**, and never in the nodecision runs.
- Every persona has a weekly status for weeks 1-10, from the allowed list, traceable to a call for that persona and week.
- Probe answers are complete (personas x 2 x 8) and tied to week 0 / week 11 calls.
- Seeds really differ (`plan_1` vs `plan_2`, `nodecision_1` vs `nodecision_2` must not have identical answers).
- `plan_nosurprises` must send different prompts than `plan_1` in weeks 1-10.

---

## 9. Vertex AI usage

- Key goes in an environment variable (`TALP_KEY`), never in code or the ZIP.
- Python: `google-genai`, `genai.Client(vertexai=True, api_key=os.environ["TALP_KEY"], ...)`. **Do not set a location** (global endpoint; location gives 404). 2.5 models also 404.
- Models:
  - `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`: no thinking, ~1 s per call, best for many persona calls
  - `gemini-3.5-flash`, `gemini-3.6-flash`, `gemini-3-flash-preview`: think first, 3-5 s
  - `gemini-3.7-flash`, `gemini-3.8-flash`, `gemini-3.1-pro-preview`: slowest, 5-20 s
- `thinking_config=types.ThinkingConfig(thinking_budget=0)` turns thinking off on most models.
- Give every call the run's `seed` and temperature above 0.
- For reliable status: ask for a last line like `Status: rebooked`, or use JSON with `response_mime_type="application/json"` and a `response_schema`.
- Make calls **in parallel** (threads or asyncio); sequential calls will not finish in time.
- macOS python.org Python `CERTIFICATE_VERIFY_FAILED`: `export SSL_CERT_FILE=/etc/ssl/cert.pem`.

---

## 10. Board presentation (from 18:30)

5 minutes to present, 3 minutes of questions, 2 minutes to change over. The two labs of each company present back to back. There is no right answer. The board asks why, and will pick one of our personas and ask it a question live.

---

## 11. Open items for us

- Confirm that our company is Kestrel Air (only its dossier is in the folder).
- Choose persona groups (at least 3 of: vacationers, families visiting relatives, students, business travelers, travel agencies) and their attribute set.
- Choose grounding data (e.g. ACS) and say which.
- Define how decisions and crises turn into world-state changes (flight operations, rebooking capacity, news, social media).
- Decide metric definitions for goals 1-4 and persona-to-customer weights.
- Decide experiments to compare.
- Decisions: **not yet decided**.
