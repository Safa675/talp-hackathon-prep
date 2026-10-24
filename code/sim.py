#!/usr/bin/env python3
"""Kestrel Air persona simulation: one Gemini call per persona per week.

    set -a; . ./.env; set +a
    python sim.py plan_1 --type plan --seed 1 --decisions decisions.json
    python sim.py nodecision_1 --type nodecision --seed 1 --probe
    python sim.py plan_nosurprises --type plan_nosurprises --seed 1 --decisions decisions.json

The model decides what each persona says and does; code only builds the world
facts it observes, validates the answer and counts it.
"""
import argparse
import json
import os
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from google import genai
from google.genai import types

HERE = Path(__file__).parent
MODEL = "gemini-3.7-flash"
COMPANY = "Kestrel Air"
STATUSES = ["flies as planned", "rebooked", "moved to another airline", "canceled the trip"]
STRIKE_WEEK = 8
STRIKE_DATES = ("2026-12-22", "2026-12-23")
HIDDEN_FIELDS = ("stratum", "strike_exposed", "touches_base")  # simulation labels, not known to the customer
CRISIS_WEEKS = {7, 8, 9}  # higher thinking level
WORKERS = 12

SYSTEM = (
    "You are simulating one Kestrel Air customer, using only the supplied persona, current state, "
    "and information this customer has actually received. Decide what this person says and does this week. "
    "Stay consistent with their constraints, but allow attitudes to change after events. Do not assume "
    "future events or create airline policies, flights, compensation, or available seats. Safety and "
    "legally required refunds are fixed. If an offered option is unavailable, do not choose it. Give a "
    "concise reason in the customer's voice. Report one exact Kestrel status and whether they would book "
    "Kestrel again. For a travel-agency persona, speak as the group coordinator and describe the group's "
    "dominant outcome."
)

KESTREL_FACTS = (
    "Kestrel Air: low-cost US airline, bases Orlando and Philadelphia. Business as usual: a canceled flight "
    "is rebooked on the next Kestrel flight with a free seat, or refunded (DOT refund rules always apply). "
    "Call center and app, normal wait 9 minutes, much longer on disruption days. Meal vouchers for "
    "Kestrel-caused delays over 3 hours; hotels only for Kestrel-caused overnight delays."
)

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "status": {"type": "STRING", "enum": STATUSES},
        "would_book_again": {"type": "STRING", "enum": ["yes", "maybe", "no"]},
        "action": {"type": "STRING"},
        "said": {"type": "STRING"},
        "reason": {"type": "STRING"},
        "support_contact": {"type": "STRING"},
        "complaint": {"type": "BOOLEAN"},
        "memory_update": {"type": "STRING"},
    },
    "required": ["status", "would_book_again", "action", "said", "reason", "memory_update"],
}

PROBE_QUESTIONS = {
    "1a": f"How much do you trust {COMPANY}? 1 = not at all, 5 = completely.",
    "1b": f'"I can count on {COMPANY} to treat me right." 1 = strongly disagree, 5 = strongly agree.',
    "2a": f"How likely are you to keep using {COMPANY} over the next three months? 1 = very unlikely, 5 = very likely.",
    "2b": f'"I am thinking about leaving {COMPANY}." 1 = strongly disagree, 5 = strongly agree.',
    "3a": f"How likely are you to recommend {COMPANY} to a friend or colleague? 1 = very unlikely, 5 = very likely.",
    "3b": f"If a friend asked you about {COMPANY} today, what would you tell them? 1 = stay away, 5 = go for it.",
    "4a": f"How fairly has {COMPANY} treated you? 1 = very unfairly, 5 = very fairly.",
    "4b": f'"{COMPANY} takes advantage of people like me." 1 = strongly disagree, 5 = strongly agree.',
}
PROBE_SCHEMA = {
    "type": "OBJECT",
    "properties": {k: {"type": "INTEGER"} for k in PROBE_QUESTIONS},
    "required": list(PROBE_QUESTIONS),
}

_lock = threading.Lock()


# ---------------------------------------------------------------- world
def targeted(persona, target):
    if target in ("everyone", "all"):
        return True
    if isinstance(target, list):
        return persona["id"] in target or persona["group"] in target
    return persona["group"] == target or persona["id"] == target


def option_lines(decisions, persona, week):
    """Facts about recovery options that actually exist for this persona this week."""
    lines = ["Rebooking on the next Kestrel flight with a free seat, or a refund (required by DOT rules)."]
    for d in decisions:
        if d["week"] <= week and targeted(persona, d["target"]):
            for a in d["actions"]:
                lines.append(f"Kestrel is offering: {a['action']} ({a['level']}).")
    return lines


def company_message(decisions, persona, week):
    msgs = [d["message"] for d in decisions if d["week"] <= week and targeted(persona, d["target"])]
    return "\n".join(msgs)


def trips_in_week(persona, week):
    return [t for t in persona["trips"] if t["week"] == week]


def week_facts(persona, week, rng, surprises, use_surprises):
    """What happened to this persona this week. The world decides exposure; the model decides behavior."""
    trips = trips_in_week(persona, week)
    has_flight = bool(trips)
    lines, outcome = [], "none"
    if week == STRIKE_WEEK - 1:
        lines.append("News: ground handling workers at Orlando and Philadelphia plan a 48-hour strike on Dec 22-23.")
    for t in trips:
        route = f"{t['from']} to {t['to']} on {t['date']}"
        if t["date"] in STRIKE_DATES and persona["touches_base"]:
            r = rng.random()
            outcome = "canceled" if r < 0.25 else "delayed" if r < 0.6 else "on time"
            lines.append({
                "canceled": f"Your flight {route} was canceled during the strike; Kestrel texted you the same morning.",
                "delayed": f"Your flight {route} is delayed several hours; baggage and boarding are slow.",
                "on time": f"Your flight {route} is operating on schedule, but the airport is crowded.",
            }[outcome])
        else:
            outcome = "canceled" if rng.random() < 0.01 else "delayed" if rng.random() < 0.21 else "on time"
            lines.append(f"Your flight {route}: {outcome}.")
    if not has_flight:
        lines.append("You have no flight this week.")
    if use_surprises:
        for s in surprises:
            if s["week"] == week:
                lines.append(f"Announcement: {s['text']}")
    return has_flight, outcome, lines


# ---------------------------------------------------------------- LLM
def make_client():
    return genai.Client(
        vertexai=True, api_key=os.environ["TALP_KEY"],
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=5)),
    )


def call_model(client, prompt, schema, seed, level, validate):
    """Returns (parsed, raw_text, call_error). Retries a malformed answer with the same prompt."""
    last = ("", "")
    for _ in range(3):
        try:
            r = client.models.generate_content(
                model=MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM, seed=seed, response_mime_type="application/json",
                    response_schema=schema, max_output_tokens=2048,
                    thinking_config=types.ThinkingConfig(thinking_level=level),
                ),
            )
            text = r.text or ""
            last = (text, "")
            parsed = json.loads(text)
            if validate(parsed):
                return parsed, text, ""
        except Exception as e:  # malformed JSON, 429, timeout
            last = (last[0], repr(e))
    return None, last[0], last[1] or "invalid answer"


def valid_week(p):
    return p.get("status") in STATUSES and p.get("would_book_again") in ("yes", "maybe", "no")


def valid_probe(p):
    return all(type(p.get(k)) is int and 1 <= p[k] <= 5 for k in PROBE_QUESTIONS)


def log_call(path, rec):
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- prompts
def visible(persona):
    return json.dumps({k: v for k, v in persona.items() if k not in HIDDEN_FIELDS}, ensure_ascii=False)


def week_prompt(persona, memory, week, facts, options, message):
    parts = [
        f"KESTREL FACTS: {KESTREL_FACTS}",
        f"PERSONA: {visible(persona)}",
        f"CURRENT_STATE: {memory}",
        f"THIS_WEEK (week {week} of 10): " + " ".join(facts),
        "OPTIONS KNOWN TO THIS CUSTOMER: " + " ".join(options),
    ]
    if message:
        parts.append(f"EXACT_COMPANY_MESSAGE (received by you): {message}")
    parts.append(
        "TASK: Decide what this person says and does now. Use only the known options. Report travel status "
        f"(one of: {', '.join(STATUSES)}) and whether they would book Kestrel again (yes, maybe, no). "
        "If there is no flight this week, report the status of your upcoming booking. Keep the reason brief."
    )
    return "\n".join(parts)


def probe_prompt(persona, memory):
    qs = "\n".join(f"{k}: {q}" for k, q in PROBE_QUESTIONS.items())
    return (f"PERSONA: {visible(persona)}\nWHAT YOU REMEMBER: {memory}\n"
            f"TASK: Answer each question as this customer with a whole number 1-5. Return JSON keyed 1a..4b.\n{qs}")


# ---------------------------------------------------------------- run
def run(args):
    out = HERE / "runs" / args.name
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.jsonl"):
        f.unlink()
    personas = [json.loads(l) for l in open(HERE / "personas.jsonl", encoding="utf-8")]
    decisions = json.load(open(args.decisions)) if args.decisions and args.type != "nodecision" else []
    use_surprises = args.type != "plan_nosurprises"
    surprises = json.load(open(args.surprises))
    client = make_client()
    calls, weekly, probes = out / "calls.jsonl", out / "weekly.jsonl", out / "probe.jsonl"
    memory = {p["id"]: "Has the trips listed in the persona booked. No problems so far." for p in personas}
    counter = [0]

    def next_id(pid, week, tag):
        with _lock:
            counter[0] += 1
            return f"{args.name}-{pid}-w{week}-{tag}-{counter[0]}"

    def probe(p, when):
        week = 0 if when == "start" else 11
        prompt = probe_prompt(p, memory[p["id"]])
        parsed, text, err = call_model(client, prompt, PROBE_SCHEMA, args.seed, "LOW", valid_probe)
        cid = next_id(p["id"], week, "probe")
        log_call(calls, {"id": cid, "persona": p["id"], "week": week, "prompt": SYSTEM + "\n\n" + prompt,
                         "response": text, "model": MODEL, "error": err})
        for k in PROBE_QUESTIONS:  # raw scores; 2b and 4b are not reverse-scored here
            if parsed:
                log_call(probes, {"persona": p["id"], "when": when, "question": k, "score": parsed[k], "call": cid})

    def step(p, week):
        rng = random.Random(f"{args.seed}-{p['id']}-{week}")
        has_flight, outcome, facts = week_facts(p, week, rng, surprises, use_surprises)
        prompt = week_prompt(p, memory[p["id"]], week, facts, option_lines(decisions, p, week),
                             company_message(decisions, p, week))
        level = "MEDIUM" if week in CRISIS_WEEKS else "LOW"
        parsed, text, err = call_model(client, prompt, SCHEMA, args.seed, level, valid_week)
        cid = next_id(p["id"], week, "week")
        log_call(calls, {"id": cid, "persona": p["id"], "week": week, "prompt": SYSTEM + "\n\n" + prompt,
                         "response": text, "model": MODEL, "error": err})
        rec = {"persona": p["id"], "week": week, "call": cid, "had_flight_this_week": has_flight,
               "flight_outcome": outcome, "status": parsed["status"] if parsed else None}
        if parsed:
            rec.update(would_book_again=parsed["would_book_again"], complaint=bool(parsed.get("complaint")),
                       support_contact=parsed.get("support_contact", ""))
            memory[p["id"]] = f"Week {week}: {parsed['memory_update']}"  # rolling memory, not full history
        log_call(weekly, rec)

    with ThreadPoolExecutor(WORKERS) as pool:
        if args.probe:
            list(pool.map(lambda p: probe(p, "start"), personas))
        for week in range(1, 11):  # personas in parallel, weeks in sequence
            list(pool.map(lambda p: step(p, week), personas))
            print(f"{args.name}: week {week} done", flush=True)
        if args.probe:
            list(pool.map(lambda p: probe(p, "end"), personas))

    (out / "personas.jsonl").write_text((HERE / "personas.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    (out / "run.json").write_text(json.dumps({
        "company": "kestrel", "type": args.type, "seed": args.seed, "model": MODEL, "decisions": decisions,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    write_metrics(out, personas)


def write_metrics(out, personas):
    """PROXIES. Persona counts are unweighted; replace with weights per real-customer share."""
    rows = [json.loads(l) for l in open(out / "weekly.jsonl", encoding="utf-8")]
    disrupted = [r for r in rows if r["flight_outcome"] in ("canceled", "delayed")]
    resolved = [r for r in disrupted if r["status"] in ("rebooked", "flies as planned")]
    flown = [r for r in rows if r["had_flight_this_week"]]
    lost = [r for r in flown if r["status"] in ("moved to another airline", "canceled the trip")]
    m = {
        "goal_1": round(100 * (1 - sum(r["flight_outcome"] == "canceled" for r in flown) / max(len(flown), 1)), 1),
        "goal_2": round(100 * len(resolved) / max(len(disrupted), 1), 1),
        "goal_3": sum(bool(r.get("complaint")) for r in rows),
        "goal_3b": None,  # NPS: compute from probe 3a at start vs end (plan_1 / nodecision_1 only)
        "goal_4": round(100 * (1 - len(lost) / max(len(flown), 1)), 1),
        "units": {
            "goal_1": "% of persona flights not canceled (proxy for planned flights operated)",
            "goal_2": "% of disrupted persona flights ending rebooked/flying (proxy for 24h resolution)",
            "goal_3": "number of persona-weeks with a complaint",
            "goal_4": "% of persona flights kept on Kestrel (revenue proxy)",
        },
    }
    (out / "metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--type", choices=["plan", "nodecision", "plan_nosurprises"], required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--decisions")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--surprises", default=str(HERE / "surprises.json"))
    run(ap.parse_args())
