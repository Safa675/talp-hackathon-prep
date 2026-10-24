# TALP Simulation Lab: the challenge

## In one paragraph

You are a simulation lab. Five US companies have come to you because the next ten weeks will be hard and they do not know their customers well enough to choose what to do. Each lab works for one company (drawn at 10:30; two labs per company). You build the company's people as LLM personas, live through the ten weeks with them, and make exactly two decisions on the company's behalf. At 18:30 you present to the company's board.

## The five clients

| Company | Sector | Dossier |
|---|---|---|
| Cobalt Bank | Digital bank | `10-cobalt-bank.md` |
| Aisle | Online marketplace | `11-aisle.md` |
| Morsel | Food delivery | `12-morsel.md` |
| Kestrel Air | Low-cost airline | `13-kestrel-air.md` |
| Quillbook | B2B: cloud bookkeeping and payroll for small businesses | `14-quillbook.md` |

All five are US companies with US customers. All companies, people and numbers are fictional.

## The company calendar

The ten weeks run from Monday, November 2 to Sunday, January 10. From 13:00 the calendar runs in real time: every 30 minutes is one week. The dashboard shows the current week.

| Week | Dates | Starts at |
|---|---|---|
| 1 | Nov 2–8 | 13:00 |
| 2 | Nov 9–15 | 13:30 |
| 3 | Nov 16–22 | 14:00 |
| 4 | Nov 23–29 (Thanksgiving, Black Friday) | 14:30 |
| 5 | Nov 30–Dec 6 | 15:00 |
| 6 | Dec 7–13 | 15:30 |
| 7 | Dec 14–20 | 16:00 |
| 8 | Dec 21–27 (Christmas) | 16:30 |
| 9 | Dec 28–Jan 3 (New Year) | 17:00 |
| 10 | Jan 4–10 | 17:30 (ends 18:00) |

## Your two decisions

- You make exactly two decisions for your client, in any weeks you choose. Both in the same week is allowed.
- You lock a decision on the dashboard. It takes effect at the start of the week you name, and it must be locked before that week starts. You cannot decide in the past: a decision locked after its week has started moves to the next week that has not started. After 17:30 no decision can be locked.
- Until its week starts you may replace a decision. The last version before the start counts.
- Each decision has:
  - the week;
  - who it is for: everyone, or a group you describe;
  - one to three actions from your dossier's decision menu, each at one of the listed levels;
  - the message the company sends: the exact words, up to 600 characters, and the channels;
  - why, in three lines.
- The cost of all actions in both decisions together, paid messages included, must fit the budget in your dossier. Costs are the CFO's estimates; use them as given.
- A decision must be one a real board would approve: inside the menu, inside the budget, inside the red lines.
- Outside your two decisions, the company does "business as usual", as described in your dossier.

## Crises

- **One you know about.** It is in your dossier: what is planned, when, and what nobody knows yet.
- **Others you do not.** They arrive as dashboard announcements at the start of a week; some get an update a week later. You will not know when, what, or how many.
- Crisis texts are deliberately vague. They say what is known and what is not. How big it is, who hears about it, how people feel and what they do: that is your simulation's job. Write down how you read each crisis.
- A crisis announced at the start of week N is already happening in week N. The earliest decision that can answer it is in week N+1.
- Crises are serious but survivable. None of them sinks a company on its own. If your simulation says half the customers leave in a week, check your simulation before you tell the board.

## What you build

- **Personas.** At least 24, covering at least three of the groups named in your dossier, with at least four personas in each group you use. The audience attribute catalog (`03-audience-attributes.md`) and the attributes in your dossier list what a persona could have. Some matter for your company and its crises, many do not, some matter for one crisis only. Nobody tells you which is which, and nobody gives you the distributions. You may ground them in public data (for example the Census Bureau's American Community Survey); say which. Choose, and say why.
- **A world over ten weeks.** What the personas see (company messages, news, social media, friends, support), what they can do (complain, post, ask a friend, call support, switch, wait…), and how the state of the world changes from week to week.
- **Crises and decisions as inputs.** The same code with a different decision file, or with the surprises switched off, must give a different run. Your personas read the message you wrote, word for word, from its week on; the company sends it only to the decision's target.
- **Your metrics.** How you turn persona behavior into the board's goals, and how many real customers each persona stands for.
- **Experiments.** Which decisions you tried, in which weeks, how many times.

The LLM must produce what the personas say, do and decide. A script that writes the outcome is not a simulation, and the checks will show it.

## The check-in questions

Ask every persona these eight questions twice: before week 1 and after week 10, in the runs `plan_1` and `nodecision_1`. Put your client's name in place of {company}. Each answer is a whole number from 1 to 5. You may ask one persona all eight in one call. Store each score as the persona gave it; 2b and 4b are worded the other way round on purpose.

| | Wording a | Wording b |
|---|---|---|
| 1 Trust | How much do you trust {company}? 1 = not at all, 5 = completely. | "I can count on {company} to treat me right." 1 = strongly disagree, 5 = strongly agree. |
| 2 Staying | How likely are you to keep using {company} over the next three months? 1 = very unlikely, 5 = very likely. | "I am thinking about leaving {company}." 1 = strongly disagree, 5 = strongly agree. |
| 3 Recommending | How likely are you to recommend {company} to a friend or colleague? 1 = very unlikely, 5 = very likely. | If a friend asked you about {company} today, what would you tell them? 1 = stay away, 5 = go for it. |
| 4 Fairness | How fairly has {company} treated you? 1 = very unfairly, 5 = very fairly. | "{company} takes advantage of people like me." 1 = strongly disagree, 5 = strongly agree. |

## What you hand in by 18:00

One ZIP on the dashboard, `team-NN_submission.zip`:
- your code;
- five runs, all with the same personas and every announcement made before 18:00:
  - `plan_1`, `plan_2`: your plan (the two decisions you locked on the dashboard), two seeds;
  - `nodecision_1`, `nodecision_2`: no decisions (business as usual only), two seeds;
  - `plan_nosurprises`: your plan with every surprise and its updates switched off (your known crisis stays), one seed;
- `CLIENT_MEMO.md`, one page for the board: what you decided and why, what the simulation says, what it cannot tell, what the company should watch next;
- `TEAM_DOC.md`: how you built it: the personas and why those attributes, the world, how you read each crisis, your experiments, the problems you hit and how you solved them, what you would do with more time.

Make your runs fast enough to repeat. You will need to run them again after a late announcement.

Use the Vertex AI key we gave you for the five runs you hand in.

## Using your Vertex AI key

The key needs no Google login. Keep it in an environment variable, never in your code or your ZIP. If it leaks or stops working, tell us; a new one takes a few minutes.

```python
# pip install google-genai        then: export TALP_KEY=<your key>
import os
from google import genai
from google.genai import types

client = genai.Client(vertexai=True, api_key=os.environ["TALP_KEY"],   # no project, no location
                      http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=5)))
reply = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt,
    config=types.GenerateContentConfig(temperature=1.0, seed=seed),
)
text = reply.text
```

- Do not set `location="us-central1"`: the models are on the global endpoint, and you get a 404. The 2.5 models also give a 404.
- Models that work (one test each on October 24; times are rough):
  - `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`: no thinking, about 1 second a call. The best fit for many persona calls.
  - `gemini-3.5-flash`, `gemini-3.6-flash`, `gemini-3-flash-preview`: think first, about 3 to 5 seconds.
  - `gemini-3.7-flash`, `gemini-3.8-flash`, `gemini-3.1-pro-preview`: the slowest, 5 to 20 seconds.
- This example does not set an additional output-token cap; the selected model's default output limit applies. `thinking_config=types.ThinkingConfig(thinking_budget=0)` turns thinking off on most of them and makes them faster.
- Give every call the run's `seed` and a temperature above 0, so your two seeds really differ.
- To read a status reliably, ask for a last line such as `Status: moved to a rival`, or ask for JSON with `response_mime_type="application/json"` and a `response_schema`.
- Make calls in parallel (threads, or `client.aio.models.generate_content` with asyncio). One after another, five runs will not finish in time.
- macOS with python.org Python: if you get `CERTIFICATE_VERIFY_FAILED`, run `export SSL_CERT_FILE=/etc/ssl/cert.pem`.
- Without Python: the `curl` example on the dashboard.

## How to save your runs

The checks read your saved runs, not your code. Use this layout, at the top of the ZIP or inside one folder (UTF-8; `.jsonl` means one JSON object per line):

```
team-NN_submission.zip
  CLIENT_MEMO.md
  TEAM_DOC.md
  code/                 your code, any layout
  runs/
    plan_1/  plan_2/  nodecision_1/  nodecision_2/  plan_nosurprises/
      run.json  personas.jsonl  calls.jsonl  weekly.jsonl  metrics.json
      probe.jsonl       (plan_1 and nodecision_1 only)
```

- **`run.json`:** `company` (`cobalt`, `aisle`, `morsel`, `kestrel` or `quillbook`), `type` (`plan`, `nodecision` or `plan_nosurprises`), `seed`, `model`, and `decisions`. `decisions` holds your two decisions exactly as locked (a decision that moved to the next week has that week), each with `week`, `target`, `actions` (one to three, each with `action` and `level`; `"level": "on"` for an action with no levels), `message`, `channels` and `why`. In the `nodecision` runs it is an empty list.
- **`personas.jsonl`:** one line per persona with `id`, `group` (a group from your dossier) and anything else you use. The same file in all five runs.
- **`calls.jsonl`:** every LLM call, one line each:
  - `id`;
  - `persona`: the persona's `id`, or `null` if the call is not for one persona;
  - `week`: 1 to 10, or 0 before week 1 and 11 after week 10;
  - `prompt`: the full text you sent, all messages joined;
  - `response`: the full text you got back;
  - `model`.
- **`weekly.jsonl`:** one line per persona per week (1 to 10) with `persona`, `week`, `status` and `call`, plus anything else you like.
  - `status` is one option from the line for that persona's kind under "What each persona reports every week" in your dossier (for example Shopper or Seller), written as there; for example `moved to a rival`. Cobalt and Kestrel: use the first line, and put the second in a field of your own, for example `"money": "moved some"`.
  - `call` is the `id` of the call, for that persona and week, whose response gives that status. The response must contain the status in your dossier's words, so ask the model to end with a line such as `Status: moved to a rival`.
- **`metrics.json`:** `goal_1`, `goal_2` and so on: one number for each board goal in your dossier, leaving out the budget goal; a goal with two parts can add `goal_3b` and so on. Add `units` saying what each number means, for example `"units": {"goal_1": "% of November 2 weekly orders"}`.
- **`probe.jsonl`:** one line per answer to the check-in questions with `persona`, `when` (`start` or `end`), `question` (`1a` to `4b`), `score` (1 to 5) and `call`. The `call` is in week 0 for `start` and week 11 for `end`.

Before you upload, run `python3 check.py team-NN_submission.zip`. It needs no installs, never runs your code, and tells you what is missing.

## Board presentations, from 18:30

5 minutes to present, 3 minutes of questions, 2 minutes to change over. The two labs of each company present back to back. There is no right answer, and the company's simulated result is not what is scored. The board asks why, and will pick one of your personas and ask it a question live.

The jury scores five things: your reasoning, an idea of your own, how you compared approaches and what you learned, a working example, and what your simulation cannot tell yet and what you would do next. The model's brand, the number of personas and polished slides earn no extra points.
