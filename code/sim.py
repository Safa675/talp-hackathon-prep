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
# Code decides what happens to each flight; the model decides how the person reacts. The probabilities are the
# simulation-engine branch's world.py assumptions (dossier: 79% on time, week 8 97% booked, 6 in 10 flights at a base).
BASES = {"MCO", "PHL"}
INTL = {"CUN", "PUJ", "MBJ", "NAS", "SDQ", "GDL", "MEX", "SJU"}
P = {"cancel": 0.012, "delay": 0.04, "short_delay": 0.17,
     "strike_cancel": 0.30, "strike_cancel_backup": 0.07, "strike_delay": 0.45, "strike_delay_backup": 0.15,
     "strike_bags": 0.50, "strike_bags_backup": 0.12, "knock_on_cancel": 0.06, "lease_factor": 0.5, "merge": 0.03,
     "phone_wait": 120, "phone_wait_staff": 20, "next_seat_days_peak": 3}
# How we read a dashboard announcement: (extra cancel probability, extra 3h+ delay probability) on flights in scope
EVENT_EFFECTS = {"none": (0, 0), "delays": (0, 0.15), "some cancellations": (0.05, 0.15),
                 "many cancellations": (0.15, 0.25)}
STRIKE_NEWS = {
    1: "News: the workers of Kestrel's ground handling contractor have announced a 48-hour strike at Orlando and "
       "Philadelphia airports on Dec 22-23. Talks continue.",
    4: "News: the Dec 22-23 ground handling strike at Orlando and Philadelphia is still on; talks continue.",
    7: "News: the 48-hour ground handling strike at Orlando and Philadelphia on Dec 22-23 is going ahead next week. "
       "The contractor will bring in replacement staff 'where it can'; the union says it 'may be extended'.",
    8: "News: the 48-hour ground handling strike at Orlando and Philadelphia is on, Dec 22-23, in the busiest week "
       "of the year. Turnarounds are slow; some flights are late or canceled.",
    9: "News: the ground handling strike at Orlando and Philadelphia ended after 48 hours.",
}
# A decision's target: everyone, a group, persona ids, or one of these rules
TARGET_RULES = {
    "strike-day passengers": lambda p: any(t["date"] in STRIKE_DATES and {t["from"], t["to"]} & BASES for t in p["trips"]),
    "holiday passengers (weeks 8-9)": lambda p: any(t["week"] in (8, 9) for t in p["trips"]),
    "Orlando and Philadelphia passengers": lambda p: any({t["from"], t["to"]} & BASES for t in p["trips"]),
}
# Menu action -> effect key. Network actions touch every flight; the rest reach only the decision's target.
ACTIONS = [("lease", "Lease an aircraft"), ("backup", "Backup ground handling"), ("free_changes", "Free changes"),
           ("goodwill", "Goodwill"), ("partner", "partner airline"), ("hotel", "Hotel rooms"),
           ("staff", "Extra airport and call-center staff"), ("fare_cap", "Fare cap"), ("fare_sale", "Fare sale"),
           ("points", "Double loyalty points"), ("merge", "Merge low-load flights")]
NETWORK = {"lease", "backup", "staff", "merge"}
# What a passenger can actually see of an action (backup crews and merges show up in the flights themselves)
CUSTOMER_TEXT = {
    "free_changes": "You can change or cancel Kestrel bookings in this two-week window for free.",
    "partner": "If your Kestrel flight is canceled, Kestrel can move you to a partner airline at no extra cost.",
    "lease": "Kestrel has added extra flights with a leased aircraft for these two weeks.",
    "hotel": "If you are stranded overnight for any reason, Kestrel holds a hotel room for you.",
    "staff": "Kestrel has extra staff at the airports and on its phone lines.",
    "goodwill": "Passengers whose trip is disrupted get {level}.",
    "points": "Passengers whose trip is disrupted get double loyalty points.",
    "fare_cap": "Fares on Kestrel's busiest routes are capped for two weeks.",
    "fare_sale": "Kestrel has a fare sale on quieter routes for two weeks.",
}


def targeted(persona, target):
    if isinstance(target, list):
        return any(targeted(persona, t) for t in target)
    if target in ("everyone", "all"):
        return True
    if target in TARGET_RULES:
        return TARGET_RULES[target](persona)
    return persona["group"] == target or persona["id"] == target


def action_key(name):
    return next((k for k, words in ACTIONS if words.lower() in name.lower()), None)


def effects(decisions, persona, week):
    """Effects of the decisions in force for this persona this week: {key: level}. Actions run for two weeks
    from their week; the backup ground handling contract covers the strike days if locked by week 8."""
    eff = {}
    for d in decisions:
        for a in d["actions"]:
            key = action_key(a["action"])
            on = d["week"] <= STRIKE_WEEK if key == "backup" else d["week"] <= week <= d["week"] + 1
            if key and on and (key in NETWORK or targeted(persona, d["target"])):
                eff[key] = a["level"]
    return eff


def option_lines(decisions, persona, week):
    """Recovery options that actually exist for this persona this week, as a passenger would read them."""
    lines = ["Rebooking on the next Kestrel flight with a free seat, or a refund (required by DOT rules)."]
    for key, level in effects(decisions, persona, week).items():
        if CUSTOMER_TEXT.get(key):
            lines.append(CUSTOMER_TEXT[key].format(level=level))
    return lines


def company_message(decisions, persona, week):
    msgs = [d["message"] for d in decisions if d["week"] <= week and targeted(persona, d["target"])]
    return "\n".join(msgs)


def trips_in_week(persona, week):
    return [t for t in persona["trips"] if t["week"] == week]


def events_in_force(surprises, week):
    """An announcement acts on flights in its week and the next one, unless it says until_week."""
    return [s for s in surprises if s["week"] <= week <= s.get("until_week", s["week"] + 1)]


def in_scope(event, leg):
    scope = event.get("scope", "all")
    airports = {leg["from"], leg["to"]}
    return scope == "all" or (scope == "bases" and airports & BASES) or (scope == "intl" and airports & INTL)


def leg_facts(persona, leg, week, rng, eff, events):
    """One flight: outcome ('canceled', 'delayed' = 3h+, 'on time'), what the passenger is told, 24h resolution."""
    route = f"{leg['from']} to {leg['to']} on {leg['date']}"
    base = bool({leg["from"], leg["to"]} & BASES)
    strike = leg["date"] in STRIKE_DATES and base
    lease = P["lease_factor"] if "lease" in eff else 1
    causes, kestrel = [], True
    if strike:
        backup = "backup" in eff
        p_cancel = P["strike_cancel_backup" if backup else "strike_cancel"] * lease
        p_delay = P["strike_delay_backup" if backup else "strike_delay"]
        causes.append("the ground handling strike")
        kestrel = False  # the contractor's strike: BAU meals and hotels are only for Kestrel-caused disruption
    else:
        p_cancel, p_delay = P["cancel"] * lease, P["delay"]
        if leg["date"] == "2026-12-24" and base and "backup" not in eff:
            p_cancel += P["knock_on_cancel"]
            causes.append("knock-on delays from the strike")
        for s in events:
            c, d = EVENT_EFFECTS.get(s.get("effect", "none"), (0, 0))
            if (c or d) and in_scope(s, leg):
                p_cancel, p_delay = p_cancel + c * lease, p_delay + d
                causes.append(f"the disruption announced in week {s['week']}")
                kestrel = kestrel and bool(s.get("kestrel_caused"))
    roll = rng.random()
    if "merge" in eff and week not in (8, 9) and rng.random() < P["merge"]:
        return "on time", (f"Your flight {route} was merged with another flight, announced 7 days ahead; "
                           f"you were moved to a flight a few hours earlier the same day."), None, strike
    why = f" because of {' and '.join(causes)}" if causes else ""
    fast = True
    if roll < p_cancel:
        outcome = "canceled"
        if "partner" in eff:
            rebook = "a seat on a partner airline the same day, at no extra cost"
        elif "lease" in eff:
            rebook = "a seat on an extra Kestrel flight (leased aircraft) the next morning"
        else:
            days = P["next_seat_days_peak"] if week in (8, 9) else 1
            rebook = f"the next Kestrel flight with a free seat, {days} day{'s' if days > 1 else ''} later"
            fast = days <= 1
        text = f"Your flight {route} was CANCELED{why}. Kestrel offers {rebook}, or a full refund (DOT rules)."
        if "hotel" in eff:
            text += " A hotel room is held for you if you are stranded overnight."
        elif not fast:
            text += (" Kestrel pays for a hotel while you wait." if kestrel
                     else " Kestrel does not pay for hotels, because the cause is not Kestrel's own.")
    elif roll < p_cancel + p_delay:
        outcome, text = "delayed", f"Your flight {route} was delayed more than 3 hours{why}."
    elif roll < p_cancel + p_delay + P["short_delay"]:
        return "on time", f"Your flight {route} left a little late (under an hour), as often happens.", None, strike
    else:
        return "on time", f"Your flight {route} operated on time" + (" despite the strike." if strike else "."), None, strike
    text += " Meal vouchers are given." if kestrel or "hotel" in eff else " No meal vouchers are given."
    text += f" The Kestrel phone line wait is about {P['phone_wait_staff' if 'staff' in eff else 'phone_wait']} minutes; the app also works."
    if "goodwill" in eff:
        text += f" Kestrel gives you {eff['goodwill']}."
    if "points" in eff:
        text += " Kestrel gives you double loyalty points on this trip."
    if strike:
        bags = str(persona.get("bags") or persona.get("checks_bags") or "").lower()
        if ("checked" in bags or bags.startswith("yes")) and rng.random() < P["strike_bags_backup" if "backup" in eff else "strike_bags"]:
            text += " Your checked bags did not arrive with you; Kestrel says they will be delivered in 1-2 days."
        if str(persona.get("airport_assistance") or "none").lower() not in ("none", "no", ""):
            text += f" Wheelchair assistance took {'about 15 minutes' if 'backup' in eff else '60-90 minutes'}."
    return outcome, text, fast, strike


def week_facts(persona, week, rng, surprises, use_surprises, decisions=()):
    """What happened to this persona this week, after the decisions and announcements in force.
    Returns (has_flight, worst outcome, lines for the prompt, world record for the metrics)."""
    trips = trips_in_week(persona, week)
    eff = effects(decisions, persona, week)
    events = events_in_force(surprises, week) if use_surprises else []
    lines, outcome, world = [], "none", {"strike_day": False, "within_24h": None, "flights": []}
    if week in STRIKE_NEWS:
        lines.append(STRIKE_NEWS[week])
    rank = {"none": 0, "on time": 1, "delayed": 2, "canceled": 3}
    for t in trips:
        o, text, fast, strike = leg_facts(persona, t, week, rng, eff, events)
        lines.append(text)
        world["flights"].append(text)
        world["strike_day"] = world["strike_day"] or strike
        if fast is not None:
            world["within_24h"] = fast if world["within_24h"] is None else world["within_24h"] and fast
        outcome = max(outcome, o, key=rank.get)
    if not trips:
        lines.append("You have no flight this week.")
    if use_surprises:
        for s in surprises:
            if s["week"] == week:
                lines.append(f"Announcement: {s['text']}")
    return bool(trips), outcome, lines, world


# ---------------------------------------------------------------- LLM
def make_client():
    return genai.Client(
        vertexai=True, api_key=os.environ["TALP_KEY"],
        http_options=types.HttpOptions(timeout=30_000,  # ms per request; a hung call gets cut and retried
                                       retry_options=types.HttpRetryOptions(attempts=5)),
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
        has_flight, outcome, facts, world = week_facts(p, week, rng, surprises, use_surprises, decisions)
        prompt = week_prompt(p, memory[p["id"]], week, facts, option_lines(decisions, p, week),
                             company_message(decisions, p, week))
        level = "MEDIUM" if week in CRISIS_WEEKS else "LOW"
        parsed, text, err = call_model(client, prompt, SCHEMA, args.seed, level, valid_week)
        cid = next_id(p["id"], week, "week")
        log_call(calls, {"id": cid, "persona": p["id"], "week": week, "prompt": SYSTEM + "\n\n" + prompt,
                         "response": text, "model": MODEL, "error": err})
        rec = {"persona": p["id"], "week": week, "call": cid, "had_flight_this_week": has_flight,
               "flight_outcome": outcome, "strike_day": world["strike_day"], "within_24h": world["within_24h"],
               "status": parsed["status"] if parsed else None}
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
    """Board goals from persona-weeks. Unweighted: each persona-week with a flight counts once."""
    rows = [json.loads(l) for l in open(out / "weekly.jsonl", encoding="utf-8")]
    flown = [r for r in rows if r["had_flight_this_week"]]
    planned = [r for r in flown if not r.get("strike_day")]  # goal 1 leaves out the strike days
    disrupted = [r for r in flown if r["flight_outcome"] in ("canceled", "delayed")]  # canceled or 3h+ late
    resolved = [r for r in disrupted if r.get("within_24h") or r["status"] == "canceled the trip"]  # rebooked <24h or refunded
    late = [r for r in flown if r["week"] >= 5]
    lost = [r for r in late if r["status"] in ("moved to another airline", "canceled the trip")]
    m = {
        "goal_1": round(100 * (1 - sum(r["flight_outcome"] == "canceled" for r in planned) / max(len(planned), 1)), 1),
        "goal_2": round(100 * len(resolved) / max(len(disrupted), 1), 1),
        "goal_3": sum(bool(r.get("complaint")) for r in rows),
        "goal_3b": None,  # NPS: compute from probe 3a at start vs end (plan_1 / nodecision_1 only)
        "goal_4": round(100 * (1 - len(lost) / max(len(late), 1)), 1),
        "units": {
            "goal_1": "% of persona flights operated (not canceled), strike days left out",
            "goal_2": "% of canceled or 3h+ delayed persona flights rebooked within 24h or refunded",
            "goal_3": "number of persona-weeks with a complaint",
            "goal_4": "% of persona flights in weeks 5-10 kept on Kestrel (revenue proxy)",
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
