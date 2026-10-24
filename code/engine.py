#!/usr/bin/env python3
"""Checkpointed Kestrel simulation engine, played week by week. World and prompts come from sim.py.

    python server.py                                   # the control room: live sessions, interviews
    python engine.py plan_1 --type plan --seed 1 --decisions decisions.json --probe
    python engine.py plan_1 ... --until 3              # play only weeks 1-3 (a live session does this)
    python engine.py official --decisions decisions.json

A live session advances with the company calendar: when week N starts (and its announcement is in
surprises.json) you play week N; between weeks you can interview any persona about what has happened
to it so far. Every week ends in a checkpoint named by a hash of everything that can change that week:
the prompt code in sim.py, the personas, model, seed, the decisions in force and the surprises announced
up to then. Playing again starts after the last week whose chain is on disk, so a late announcement
re-runs only the weeks it touches, and runs that share a prefix (plan_1 and nodecision_1 before the first
decision) share those weeks. Personas in a week run in parallel; weeks run in sequence.
"""
import argparse
import functools
import hashlib
import inspect
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import sim

HERE = sim.HERE
RUNS = HERE / "runs"
CKPT = HERE / "checkpoints"
LOGS = HERE / "logs"
SESSIONS = HERE / "sessions"
CHECK_PY = HERE.parent / "yeni-case-5-sirket" / "check.py"
ENGINE_VERSION = 4  # 4: posting gate + @replies, dates in the prompt, known crisis in the news beforehand
DEFAULT_PERSONAS = "personas_66.jsonl"  # talp-kestrel branch: 66 personas, each standing for real trips
WEEKS = range(1, 11)
DATES = {1: "Nov 2-8", 2: "Nov 9-15", 3: "Nov 16-22", 4: "Nov 23-29, Thanksgiving", 5: "Nov 30-Dec 6",
         6: "Dec 7-13", 7: "Dec 14-20", 8: "Dec 21-27, Christmas", 9: "Dec 28-Jan 3, New Year", 10: "Jan 4-10"}
BASE_AIRPORTS = {"MCO", "PHL"}
# Simulation labels some persona files carry; the customer must not see them.
ENGINE_HIDDEN = set(sim.HIDDEN_FIELDS) | {"window", "cluster", "segment", "segment_description",
                                         "represents_trips", "share_pct", "connections", "influencer"}

# Persona-to-persona interaction (ported from the simulation-engine branch): each persona may post publicly
# every week; next week its connections read the post, and posts by influencers trend to others.
SOCIAL_SCHEMA = dict(sim.SCHEMA, properties=dict(sim.SCHEMA["properties"], post={
    "type": "STRING",
    "description": "What you posted publicly on social media this week about your trip or Kestrel, in your own "
                   "words; an empty string if you did not post. Most people do not post most weeks. To answer "
                   "someone in your feed, start the post with @ and their full name, e.g. '@Jane Doe ...'.",
}))
TRENDING_PER_WEEK = 2
POST_CHARS = 400
# Who is on social media in a given week (the code gives the chance to post; the model decides whether and what).
# Without this gate 38% of persona-weeks carried a post and 57 of 66 personas posted; real passengers post rarely.
# Being hit yourself (canceled or 3h+ late flight) or getting a company message raises the chance.
POST_ONLINE = {"high": 0.40, "medium": 0.12, "low": 0.03}
POST_ONLINE_HIT = 0.35

MODELS = {
    "gemini-3.5-flash-lite": {"thinking": False, "note": "experiments, ~1 s/call"},
    "gemini-3.1-flash-lite": {"thinking": False, "note": "experiments, ~1 s/call"},
    "gemini-3.5-flash": {"thinking": True, "note": "thinks, 3-5 s/call"},
    "gemini-3.7-flash": {"thinking": True, "note": "hand-in runs, 5-20 s/call"},
    "mock": {"thinking": False, "offline": True, "note": "offline UI test, not a simulation"},
}
DEFAULT_MODEL = sim.MODEL

# name, type, seed, probe
OFFICIAL = [("plan_1", "plan", 1, True), ("plan_2", "plan", 2, False),
            ("nodecision_1", "nodecision", 1, True), ("nodecision_2", "nodecision", 2, False),
            ("plan_nosurprises", "plan_nosurprises", 1, False)]

# Decision menu from 13-kestrel-air.md: action -> {level: cost in $M}
MENU = {
    "Lease an aircraft with crew for 2 weeks": {"1 aircraft": 0.7, "2 aircraft": 1.4},
    "Backup ground handling contract at both bases for the strike days": {"on": 0.5},
    "Free changes and cancellations for bookings in a 2-week window": {"on": 0.2},
    "Goodwill for affected passengers, up to 10,000 passengers": {"a $75 travel credit": 0.3, "$50 cash": 0.5},
    "Rebooking deal with a partner airline for 2 disrupted weeks": {"on": 0.25},
    "Hotel rooms held for stranded passengers, whatever the cause": {"on": 0.2},
    "Extra airport and call-center staff for 2 weeks": {"on": 0.15},
    "Fare cap on the busiest routes for 2 weeks": {"on": 0.5},
    "Fare sale on quiet routes for 2 weeks": {"on": 0.3},
    "Double loyalty points for affected passengers": {"on": 0.1},
    "Merge low-load flights, announced at least 7 days ahead (passengers moved to other flights)": {"on": -0.25},
}
BUDGET = 3.0
MENU_BY_KEY = {sim.action_key(name): name for name in MENU}  # the dashboard's wording finds its menu row by keyword
ON_WORDS = {"on", "enable", "enabled", "yes", "true"}  # the dashboard writes "Enable" for an action with no levels
GROUPS =["vacationers", "families visiting relatives", "students", "business travelers", "travel agencies"]
CHANNELS = ["app", "email", "text", "social media"]

INTERVIEW_SYSTEM = (
    "You are one Kestrel Air customer being interviewed. Stay in character, speak in the first person, "
    "and answer only from the supplied persona and the experiences listed, which are everything you know. "
    "Do not invent flights, policies, compensation or events that are not listed; if you do not know, say so. "
    "Be concrete and honest about your feelings and plans. Answer in the language of the question, "
    "in 2 to 5 sentences unless asked for more."
)

_lock = threading.Lock()
_fp_locks = defaultdict(threading.Lock)


class Canceled(Exception):
    pass


class Limiter:
    """Caps LLM calls in flight across all runs; the cap can change while runs are going."""

    def __init__(self, n):
        self.n, self.used, self.cv = n, 0, threading.Condition()

    def set(self, n):
        with self.cv:
            self.n = max(1, int(n))
            self.cv.notify_all()

    def __enter__(self):
        with self.cv:
            while self.used >= self.n:
                self.cv.wait()
            self.used += 1

    def __exit__(self, *exc):
        with self.cv:
            self.used -= 1
            self.cv.notify_all()


LIMIT = Limiter(80)  # flash-lite: all personas of a week in one wave (66 calls in ~4 s)
THINKING_LIMIT = Limiter(30)  # thinking models slow down past ~30 calls in flight (measured: 66 at once took 128 s, 30 took 48 s)


# ---------------------------------------------------------------- small helpers
def now():
    return datetime.now().isoformat(timespec="seconds")


def h(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]


def read_jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def append_jsonl(path, rec):
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def log(event, **kw):
    """Append-only history of everything the engine and the inputs went through."""
    LOGS.mkdir(exist_ok=True)
    append_jsonl(LOGS / "history.jsonl", {"ts": now(), "event": event, **kw})


def load_env():
    if os.environ.get("TALP_KEY"):
        return
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def resolve(path):
    p = Path(path)
    return p if p.is_absolute() else (HERE / p if (HERE / p).exists() else Path.cwd() / p)


@functools.lru_cache(maxsize=1)
def prompt_code_hash():
    """Anything in sim.py that shapes a prompt or the world; editing it invalidates checkpoints."""
    parts = [inspect.getsource(f) for f in (sim.targeted, sim.action_key, sim.option_lines, sim.company_message,
                                            sim.effects, sim.trips_in_week, sim.week_facts, sim.leg_facts, sim.visible,
                                            sim.week_prompt, sim.probe_prompt, add_social_graph, Run.feed)]
    return h(parts, sim.P, sim.EVENT_EFFECTS, sim.CUSTOMER_TEXT, sim.SYSTEM, sim.KESTREL_FACTS, sim.SCHEMA, SOCIAL_SCHEMA, sim.PROBE_QUESTIONS, sim.STATUSES,
             sim.STATUS_MEANING, sim.ACTIONS, sorted(sim.NETWORK), sim.WEEK_DATES, POST_ONLINE, POST_ONLINE_HIT,
             inspect.getsource(Run.step),
             sim.STRIKE_WEEK, sim.STRIKE_DATES, sorted(sim.HIDDEN_FIELDS), sorted(sim.CRISIS_WEEKS),
             sorted(ENGINE_HIDDEN), ENGINE_VERSION)


# ---------------------------------------------------------------- LLM
_client = None


def client():
    global _client
    with _lock:
        if _client is None:
            load_env()
            _client = sim.make_client()
    return _client


def mock_answer(prompt, schema, seed):
    """Offline stand-in so the engine and UI can be tested without quota. Never hand in a mock run."""
    rng = random.Random(h(prompt, seed))
    if schema is None:
        q = prompt.rsplit("QUESTION", 1)[-1].split("\n")[0][:120]
        return f"(mock answer, not a model) I heard your question{q} and I would tell you honestly how my trip went."
    if schema is sim.PROBE_SCHEMA:
        return json.dumps({k: rng.randint(2, 5) for k in sim.PROBE_QUESTIONS})
    week = prompt.split("THIS_WEEK", 1)[-1].split("OPTIONS KNOWN", 1)[0]
    state = prompt.split("CURRENT_STATE:", 1)[-1].split("THIS_WEEK", 1)[0]
    if "moved to another airline" in state or "canceled the trip" in state:
        status = "moved to another airline" if "moved" in state else "canceled the trip"
    elif "was canceled" in week:
        status = rng.choice(["rebooked", "rebooked", "moved to another airline", "canceled the trip"])
    elif "delayed" in week:
        status = rng.choice(["flies as planned", "flies as planned", "rebooked"])
    else:
        status = "flies as planned"
    wba = {"flies as planned": "yes", "rebooked": "maybe"}.get(status, "no")
    post = f"(mock post) My Kestrel trip: {status}." if status != "flies as planned" or rng.random() < 0.1 else ""
    return json.dumps({"status": status, "would_book_again": wba, "action": "mock", "said": "(mock answer)",
                       "reason": "mock", "support_contact": "none", "complaint": status != "flies as planned",
                       "memory_update": f"Status so far: {status}.", **({"post": post} if schema is SOCIAL_SCHEMA else {})})


def usage(r):
    u = getattr(r, "usage_metadata", None)
    return {"in": getattr(u, "prompt_token_count", None), "out": getattr(u, "candidates_token_count", None),
            "think": getattr(u, "thoughts_token_count", None), "version": getattr(r, "model_version", None)}


def call(model, prompt, schema, seed, level, validate, system=sim.SYSTEM):
    """Returns (parsed, raw_text, error, usage). With schema=None the answer is plain text.
    Retries a malformed answer with the same prompt."""
    if MODELS.get(model, {}).get("offline"):
        text = mock_answer(prompt, schema, seed)
        return (json.loads(text) if schema else text), text, "", {}
    from google.genai import types
    extra = {"thinking_config": types.ThinkingConfig(thinking_level=level)} \
        if MODELS.get(model, {"thinking": True})["thinking"] else {"temperature": 1.0}
    if schema:
        extra.update(response_mime_type="application/json", response_schema=schema)
    last = ("", "", {})
    for _ in range(3):
        try:
            with THINKING_LIMIT if MODELS.get(model, {"thinking": True})["thinking"] else LIMIT:
                r = client().models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(system_instruction=system, seed=seed,
                                                       max_output_tokens=2048, **extra),
                )
            text = r.text or ""
            last = (text, "", usage(r))
            parsed = json.loads(text) if schema else text.strip()
            if validate(parsed):
                return parsed, text, "", last[2]
        except Exception as e:  # malformed JSON, 429, timeout
            last = (last[0], repr(e), last[2])
    return None, last[0], last[1] or "invalid answer", last[2]


# ---------------------------------------------------------------- reading an announcement
READ_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "effect": {"type": "STRING", "enum": list(sim.EVENT_EFFECTS)},
        "scope": {"type": "STRING", "enum": ["all", "bases", "intl"]},
        "kestrel_caused": {"type": "BOOLEAN"},
        "weeks": {"type": "INTEGER", "description": "how many weeks it acts on flights, 1 to 3"},
        "reading": {"type": "STRING", "description": "one sentence: how big it is, who hears about it, what people do"},
    },
    "required": ["effect", "scope", "kestrel_caused", "weeks", "reading"],
}


def read_event(event, model="gemini-3.5-flash-lite"):
    """The model reads a dashboard announcement once into its effect on Kestrel's flights; the reading is saved
    in the surprises file, where the team can see and change it. Crises are serious but survivable."""
    prompt = (f"You are the analyst of a simulation lab working for Kestrel Air, a US low-cost airline with bases in "
              f"Orlando (MCO) and Philadelphia (PHL); 75% domestic, 25% Mexico and the Caribbean. This announcement "
              f"arrived at the start of week {event['week']} of 10 (Nov 2 - Jan 10):\n\"{event['text']}\"\n"
              f"Decide how it acts on Kestrel's flights: effect (none, delays, some cancellations, many cancellations), "
              f"which flights (all, bases = Orlando and Philadelphia, intl = Mexico and the Caribbean), whether it is "
              f"Kestrel's own doing, for how many weeks, and one sentence on how you read it, written as a neutral news "
              f"report in the third person (passengers will read it). Crises are serious but survivable; do not "
              f"exaggerate, and do not invent facts the text does not give.")
    parsed, _, err, _ = call(model, prompt, READ_SCHEMA, 1, "LOW", lambda r: r.get("effect") in sim.EVENT_EFFECTS)
    if not parsed:
        return dict(event, effect="none", reading=f"(could not read automatically: {err})")
    weeks = max(1, min(3, int(parsed["weeks"])))
    return dict(event, effect=parsed["effect"], scope=parsed["scope"], kestrel_caused=parsed["kestrel_caused"],
                until_week=min(10, event["week"] + weeks - 1), reading=parsed["reading"], read_by=model)


# ---------------------------------------------------------------- inputs
def load_personas(path):
    text = Path(path).read_text(encoding="utf-8")
    personas = [json.loads(l) for l in text.splitlines() if l.strip()]
    for p in personas:  # world-side label; derived when a persona file does not carry it
        p.setdefault("touches_base", any(t["from"] in BASE_AIRPORTS or t["to"] in BASE_AIRPORTS
                                         for t in p.get("trips", [])))
    return text, personas


MEMORY_WEEKS = 6


def remember(memory, line):
    """Memory is the last MEMORY_WEEKS weekly notes, so the strike is still remembered at week 10."""
    kept = [l for l in memory.split("\n") if l.startswith("Week ")]
    return "\n".join((kept + [line])[-MEMORY_WEEKS:])


def shown(persona):
    return {k: v for k, v in persona.items() if k not in ENGINE_HIDDEN}


def add_social_graph(personas, k=3, seed=2026):
    """Who hears whom, same rule as the simulation-engine branch: a persona file may set `connections` by hand;
    otherwise two links to people with the same home or group and one random link, fixed for every run.
    Influencers (high social-media activity) also reach people they are not connected to, as trending posts."""
    rng = random.Random(seed)
    ids = [p["id"] for p in personas]
    for p in personas:
        p["influencer"] = bool(p.get("influencer")) or p.get("social_media_activity") == "high"
        if p.get("connections"):
            continue
        home = p.get("home") or p.get("home_area")
        near = [q["id"] for q in personas if q["id"] != p["id"]
                and ((q.get("home") or q.get("home_area")) == home or q["group"] == p["group"])]
        picks = rng.sample(near, min(k - 1, len(near)))
        rest = [i for i in ids if i != p["id"] and i not in picks]
        p["connections"] = picks + rng.sample(rest, 1)
    return personas


def social_graph(personas):
    return {"connections": {p["id"]: p["connections"] for p in personas},
            "influencers": [p["id"] for p in personas if p["influencer"]]}


def menu_level(levels, level):
    """The menu level a decision's level stands for: the same words, 'Enable' for 'on', or the label with its cost
    added ('1 aircraft: $0.7M') or with words left out ('$75 travel credit'). None if no single level fits."""
    lv = str(level or "").strip().lower()
    hits = [n for n in levels if lv == n.lower() or (n == "on" and lv in ON_WORDS) or (lv and n.lower() in lv)]
    if not hits:
        hits = [n for n in levels if lv and lv in n.lower()]
    return hits[0] if len(hits) == 1 else None


def validate_decisions(decs):
    """Board rules from the challenge and dossier. Returns (issues, budget in $M)."""
    issues, cost = [], 0.0
    if not isinstance(decs, list):
        return ["decisions must be a list"], 0.0
    if len(decs) != 2:
        issues.append(f"{len(decs)} decisions; the hand-in needs exactly 2")
    for i, d in enumerate(decs, 1):
        if type(d.get("week")) is not int or not 1 <= d["week"] <= 10:
            issues.append(f"decision {i}: week must be 1-10")
        t = d.get("target")
        known = {"everyone", "all", *sim.TARGET_RULES, *GROUPS}
        if not t:
            issues.append(f"decision {i}: no target")
        elif any(x not in known and " " in x for x in (t if isinstance(t, list) else [t])):
            issues.append(f"decision {i}: target '{t}' matches no one; use everyone, a group, persona ids or one of: "
                          + ", ".join(sim.TARGET_RULES))
        acts = d.get("actions") or []
        if not 1 <= len(acts) <= 3:
            issues.append(f"decision {i}: needs 1-3 actions")
        for a in acts:
            levels = MENU.get(MENU_BY_KEY.get(sim.action_key(a.get("action"))))
            level = menu_level(levels, a.get("level")) if levels else None
            if levels is None:
                issues.append(f"decision {i}: '{a.get('action')}' is not on the menu")
            elif level is None:
                issues.append(f"decision {i}: level '{a.get('level')}' not in {list(levels)}")
            else:
                cost += levels[level]
        msg = d.get("message") or ""
        if not msg.strip() or msg.startswith("REPLACE WITH"):
            issues.append(f"decision {i}: message is empty or still the placeholder")
        if len(msg) > 600:
            issues.append(f"decision {i}: message is {len(msg)} characters (max 600)")
        if not d.get("channels"):
            issues.append(f"decision {i}: no channels")
        if len([l for l in str(d.get("why", "")).split("\n") if l.strip()]) != 3:
            issues.append(f"decision {i}: 'why' should be three lines")
    if cost > BUDGET + 1e-9:
        issues.append(f"budget ${cost:.2f}M is over ${BUDGET:.1f}M")
    return issues, round(cost, 2)


def inputs(cfg):
    """Everything a run reads, re-read from disk each time so edits between weeks take effect."""
    personas_text, personas = load_personas(resolve(cfg["personas"] or DEFAULT_PERSONAS))
    add_social_graph(personas)
    decisions = [] if cfg["type"] == "nodecision" or not cfg["decisions"] else \
        json.loads(resolve(cfg["decisions"]).read_text(encoding="utf-8"))
    sim.check_actions(decisions)
    surprises =json.loads(resolve(cfg["surprises"] or "surprises.json").read_text(encoding="utf-8"))
    if cfg["type"] == "plan_nosurprises":  # every surprise off; the known crisis stays
        surprises = [e for e in surprises if e.get("known_crisis")]
    code = prompt_code_hash()
    people = h(personas_text, cfg["model"], cfg["seed"], cfg["replicate"],
               social_graph(personas) if cfg.get("social") else None)
    fps = [h(code, people)]
    for w in WEEKS:
        fps.append(week_fp(fps[-1], w, code, decisions, surprises))
    return {"personas_text": personas_text, "personas": personas, "decisions": decisions,
            "surprises": surprises, "fps": fps, "code": code, "people": people}


def week_fp(prev, w, code, decisions, surprises):
    return h(prev, w, code, [d for d in decisions if d["week"] <= w], [s for s in surprises if s["week"] <= w])


# ---------------------------------------------------------------- checkpoints
def ckpt_path(fp):
    return CKPT / f"{fp}.json"


def load_ckpt(fp):
    p = ckpt_path(fp)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_ckpt(fp, data):
    CKPT.mkdir(exist_ok=True)
    tmp = ckpt_path(fp).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ckpt_path(fp))


def chain_length(fps, limit=10):
    """How many weeks from week 1 on already have a checkpoint for these inputs."""
    n = 0
    while n < limit and ckpt_path(fps[n + 1]).exists():
        n += 1
    return n


def ckpt_stats():
    files = list(CKPT.glob("*.json")) if CKPT.exists() else []
    return {"count": len(files), "mb": round(sum(f.stat().st_size for f in files) / 1e6, 1),
            "partial": len(list(CKPT.glob("*.partial.jsonl"))) if CKPT.exists() else 0}


# ---------------------------------------------------------------- run
class Run:
    """One simulated timeline. A batch run plays weeks 1-10 at once; a live session (session=True)
    plays them as the calendar advances and is saved in sessions/ between plays."""

    def __init__(self, name, type, seed, decisions=None, surprises=None, probe=False, model=DEFAULT_MODEL,
                 personas=None, replicate=0, session=False, auto=False, social=True):
        if model not in MODELS:
            raise ValueError(f"unknown model {model}")
        if type not in ("plan", "nodecision", "plan_nosurprises"):
            raise ValueError(f"unknown type {type}")
        if not re.fullmatch(r"[\w.-]+", name or ""):
            raise ValueError("name: letters, digits, _ . - only")
        self.cancel_flag = threading.Event()
        self.config = {"name": name, "type": type, "seed": int(seed), "decisions": decisions,
                       "surprises": surprises or "surprises.json", "probe": bool(probe), "model": model,
                       "personas": personas or DEFAULT_PERSONAS, "replicate": int(replicate or 0),
                       "session": bool(session), "auto": bool(auto), "social": bool(social)}
        c = self.config
        self.info = {
            "name": name, "type": type, "seed": c["seed"], "model": model, "probe": c["probe"],
            "decisions_file": decisions, "surprises_file": c["surprises"], "personas_file": c["personas"],
            "replicate": c["replicate"], "session": c["session"], "auto": c["auto"], "social": c["social"],
            "status": "idle" if session else "queued", "phase": "not started" if session else "queued",
            "weeks": {str(w): "pending" for w in WEEKS}, "week_source": {}, "played": 0, "target": 0,
            "calls_done": 0, "calls_total": 0, "errors": 0, "tokens": {"in": 0, "out": 0, "think": 0},
            "resumed_from": 0, "created": now(), "started": None, "finished": None, "error": None, "metrics": None,
            "log_id": uuid.uuid4().hex,
        }

    @property
    def name(self):
        return self.config["name"]

    @property
    def log_dir(self):
        return LOGS / "runs" / self.name / self.info["log_id"]

    def audit(self, event, **kw):
        rec = {"ts": now(), "event": event, "run": self.name, "log_id": self.info["log_id"], **kw}
        log(event, run=self.name, log_id=self.info["log_id"], **kw)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        append_jsonl(self.log_dir / "events.jsonl", rec)

    def save_week_log(self, w, ck):
        """Keep this run's complete weekly record even if its checkpoint is shared or the session is deleted."""
        write_json_atomic(self.log_dir / f"week-{w:02d}.json", {
            "run": self.name, "log_id": self.info["log_id"], "week": w, "checkpoint": ck["fp"],
            "checkpoint_origin": ck.get("origin_run"), "created": ck.get("created"),
            "model": self.config["model"], "seed": self.config["seed"],
            "decisions_known": [d for d in self.decisions if d["week"] <= w],
            "events_known": [s for s in self.surprises if s["week"] <= w],
            "entries": ck["entries"],
        })

    def backfill_logs(self):
        """Give older live sessions their own records from the checkpoint chain on disk."""
        self.prepare()
        self.info["chain"] = self.fps[:self.info["played"] + 1]
        self.info["people"] = self.people
        missing = [w for w in range(1, self.info["played"] + 1)
                   if not (self.log_dir / f"week-{w:02d}.json").exists()]
        if not missing:
            self.save()
            return
        for w in missing:
            ck = load_ckpt(self.fps[w])
            if ck:
                self.save_week_log(w, ck)
        self.audit("logs_backfilled", weeks=missing)
        self.save()

    def cancel(self):
        self.cancel_flag.set()

    def busy(self):
        return self.info["status"] in ("queued", "running")

    # -------------------------------------------- state on disk
    def save(self):
        write_json_atomic(self.log_dir / "state.json", {"config": self.config, "info": self.info})
        if self.config["session"]:
            SESSIONS.mkdir(exist_ok=True)
            (SESSIONS / f"{self.name}.json").write_text(
                json.dumps({"config": self.config, "info": self.info}, indent=2, ensure_ascii=False), encoding="utf-8")
        out = RUNS / self.name
        if out.exists() and not self.config["session"] or (out / "run.json").exists() and self.info["played"] == 10:
            data = dict(self.info, fps=getattr(self, "fps", []))
            (out / "engine.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        run = cls(**dict({"social": False}, **d["config"]))  # sessions saved before the social layer had none
        run.info.update(d["info"])
        run.info.setdefault("log_id", uuid.uuid4().hex)
        if run.info["status"] in ("running", "queued"):
            run.info.update(status="paused", phase="server restarted mid-week; play again to resume")
        return run

    def inputs_now(self):
        """Current inputs. A live session keeps the weeks it already played as history: a new event or decision
        for a played week does not replay it; it acts from the next week played on."""
        b = inputs(self.config)
        kept = self.info.get("chain") or []
        if not self.config["session"] or not kept or self.info.get("people", b["people"]) != b["people"]:
            return b  # new personas, model, seed or social setting: the history starts again
        fps = [kept[0]]
        for fp in kept[1:self.info["played"] + 1]:
            if not ckpt_path(fp).exists():
                break
            fps.append(fp)
        for w in range(len(fps), 11):  # weeks still to play follow today's code and inputs
            fps.append(week_fp(fps[-1], w, b["code"], b["decisions"], b["surprises"]))
        return dict(b, fps=fps)

    def validity(self):
        """Weeks played that still match the current inputs. Editing a decision or a surprise for week N
        makes weeks N.. stale; playing again recomputes only those."""
        try:
            b = self.inputs_now()
        except Exception as e:
            return {"valid_through": 0, "error": f"{type(e).__name__}: {e}"}
        ok = chain_length(b["fps"], self.info["played"])
        return {"valid_through": ok, "stale_from": ok + 1 if ok < self.info["played"] else None,
                "decisions": b["decisions"], "surprises": b["surprises"]}

    # -------------------------------------------- execution
    def prepare(self):
        b = self.inputs_now()
        self.people = b["people"]
        self.personas_text, self.personas = b["personas_text"], b["personas"]
        self.decisions, self.surprises, self.fps = b["decisions"], b["surprises"], b["fps"]
        self.by_id = {p["id"]: p for p in self.personas}
        self.memory = {p["id"]: "Has the trips listed in the persona booked. No problems so far." for p in self.personas}
        self.posts = {}  # persona id -> what it posted last week
        self.last_status = {}

    def carry(self, entries):
        """State the next week reads: each persona's rolling memory and last week's posts."""
        self.memory = {e["persona"]: e["memory_after"] for e in entries}
        self.posts = {e["persona"]: e.get("post") or "" for e in entries}
        self.last_status = {e["persona"]: e["status"] for e in entries}

    def feed(self, p, w):
        """What this persona saw from other personas this week: posts from its connections last week,
        and up to TRENDING_PER_WEEK posts by influencers it is not connected to."""
        if w == 1 or not self.config["social"]:
            return []
        lines = [f'{self.by_id[c].get("name", c)}, someone you know, posted: "{self.posts[c]}"'
                 for c in p["connections"] if self.posts.get(c)]
        me = "@" + str(p.get("name", p["id"])).lower()
        lines += [f'{q.get("name", q["id"])} replied to you: "{self.posts[q["id"]]}"' for q in self.personas
                  if q["id"] != p["id"] and q["id"] not in p["connections"] and me in self.posts.get(q["id"], "").lower()]
        trending = [q["id"] for q in self.personas if q["influencer"] and q["id"] != p["id"]
                    and q["id"] not in p["connections"] and self.posts.get(q["id"])]
        rng = random.Random(f"{self.info['seed']}-trending-{w}-{p['id']}")
        for i in rng.sample(trending, min(TRENDING_PER_WEEK, len(trending))):
            lines.append(f'Trending on social media, {self.by_id[i].get("name", i)} posted: "{self.posts[i]}"')
        return lines

    def probe_key(self, when):
        return h(self.fps[0] if when == "start" else self.fps[10], "probe", when)

    def execute(self, until=10):
        i, c = self.info, self.config
        t0 = time.time()
        self.cancel_flag.clear()
        try:
            i.update(status="running", started=now(), finished=None, error=None, phase="preparing", target=until,
                     calls_done=0, errors=0, week_source={}, weeks={str(w): "pending" for w in WEEKS})
            self.prepare()
            start = chain_length(self.fps, until)
            if start:
                self.carry(load_ckpt(self.fps[start])["entries"])
                for w in range(1, start + 1):
                    ck = load_ckpt(self.fps[w])
                    self.mark_reused(w, ck)
                    self.save_week_log(w, ck)
                i["chain"] = self.fps[:start + 1]
                i["people"] = self.people
            n = len(self.personas)
            i["resumed_from"] = start
            i["played"] = start
            i["calls_total"] = n * (until - start) + (n * (1 + (until == 10)) if c["probe"] else 0)
            self.audit("run_started", session=c["session"], type=c["type"], seed=c["seed"], model=c["model"],
                resumed_from_week=start, until=until, decisions=len(self.decisions), surprises=len(self.surprises))
            if not c["session"]:
                archive(RUNS / self.name)
                (RUNS / self.name).mkdir(parents=True, exist_ok=True)
            self.save()
            if c["probe"]:
                self.probe("start")
            for w in range(start + 1, until + 1):
                self.week(w)
            if until == 10:
                if c["probe"]:
                    self.probe("end")
                i["phase"] = "writing outputs"
                out = RUNS / self.name
                if c["session"]:
                    archive(out)
                    out.mkdir(parents=True, exist_ok=True)
                assemble(self, out)
                i.update(status="done", phase="done: hand-in files written")
                self.audit("run_finished", metrics=i["metrics"], resumed_from_week=start,
                    seconds=round(time.time() - t0), tokens=i["tokens"])
            else:
                i.update(status="paused", phase=f"played through week {until}")
                self.audit("weeks_played", through=until, resumed_from_week=start,
                    seconds=round(time.time() - t0), tokens=i["tokens"])
        except Canceled:
            i.update(status="canceled" if not c["session"] else "paused", phase="stopped; finished calls are kept")
            self.audit("run_canceled", played=i["played"])
        except Exception as e:
            i.update(status="failed", phase="failed", error=f"{type(e).__name__}: {e}")
            self.audit("run_failed", error=i["error"])
        i["finished"] = now()
        self.save()
        return self

    def mark_reused(self, w, ck):
        mine = ck.get("origin_run") == self.name
        self.info["weeks"][str(w)] = "computed" if mine else "reused"
        self.info["week_source"][str(w)] = {"fp": self.fps[w], "origin_run": ck.get("origin_run"),
                                            "created": ck.get("created")}

    def week(self, w):
        i, fp = self.info, self.fps[w]
        i["weeks"][str(w)] = "waiting"
        i["phase"] = f"week {w}"
        with _fp_locks[fp]:  # another run may be computing the same week right now
            ck = load_ckpt(fp)
            if ck:
                self.mark_reused(w, ck)
                self.audit("week_reused", week=w, fp=fp, origin_run=ck.get("origin_run"))
                i["calls_done"] += len(self.personas)
            else:
                i["weeks"][str(w)] = "running"
                t0 = time.time()
                entries = self.compute(fp, lambda p: self.step(p, w))
                ck = {"fp": fp, "prev": self.fps[w - 1], "week": w, "model": i["model"], "seed": i["seed"],
                      "origin_run": self.name, "created": now(), "seconds": round(time.time() - t0, 1),
                      "entries": entries}
                save_ckpt(fp, ck)
                i["weeks"][str(w)] = "computed"
                i["week_source"][str(w)] = {"fp": fp, "origin_run": self.name, "created": ck["created"]}
                self.audit("week_done", week=w, fp=fp, seconds=ck["seconds"],
                    statuses=dict(Counter(e["status"] for e in entries)),
                    complaints=sum(bool(e.get("complaint")) for e in entries),
                    posts=sum(bool(e.get("post")) for e in entries))
        self.save_week_log(w, ck)
        self.carry(ck["entries"])
        i["played"] = w
        i["chain"] = self.fps[:w + 1]
        i["people"] = self.people
        self.save()

    def compute(self, fp, step):
        """Run step for every persona, resuming from a partial file left by a crash or a stop."""
        partial = CKPT / f"{fp}.partial.jsonl"
        CKPT.mkdir(exist_ok=True)
        done = {e["persona"]: e for e in read_jsonl(partial)}
        self.info["calls_done"] += len(done)
        for attempt in range(2):
            todo = [p for p in self.personas if p["id"] not in done]
            if not todo:
                break
            with ThreadPoolExecutor(len(todo)) as pool:
                for e in pool.map(step, todo):
                    if e and not e.get("error"):
                        done[e["persona"]] = e
                        append_jsonl(partial, e)
            if self.cancel_flag.is_set():
                raise Canceled()
        failed = [p["id"] for p in self.personas if p["id"] not in done]
        if failed:
            raise RuntimeError(f"{len(failed)} persona calls failed after retries: {', '.join(failed[:5])}")
        partial.unlink(missing_ok=True)
        return [done[p["id"]] for p in self.personas]

    def step(self, p, w):
        if self.cancel_flag.is_set():
            return None
        i = self.info
        rng = random.Random(f"{i['seed']}-{p['id']}-{w}")
        has_flight, outcome, facts, world = sim.week_facts(p, w, rng, self.surprises, True, self.decisions)
        if self.last_status.get(p["id"]):
            facts = [f"Your booking status last week: {self.last_status[p['id']]}."] + facts
        feed = self.feed(p, w)
        if feed:
            facts = facts + ["Social media and people you know, last week: " + " | ".join(feed)]
        prompt = sim.week_prompt(shown(p), self.memory[p["id"]], w, facts,
                                 sim.option_lines(self.decisions, p, w), sim.company_message(self.decisions, p, w))
        level = "LOW"  # MEDIUM in crisis weeks doubled the wait; LOW keeps a week under ~15 s
        online = False
        if self.config["social"]:
            # the bump is for news that is new to this persona this week, not for an old message still in force
            hit = outcome in ("canceled", "delayed") or any(d["week"] == w and sim.targeted(p, d["target"])
                                                           for d in self.decisions)
            chance = POST_ONLINE.get(p.get("social_media_activity"), POST_ONLINE["medium"]) + (POST_ONLINE_HIT if hit else 0)
            online = random.Random(f"{i['seed']}-{p['id']}-{w}-online").random() < chance
            prompt += ("\nSOCIAL MEDIA: you are on social media this week and may post if you want to (most weeks "
                       "people do not)." if online else "\nSOCIAL MEDIA: you are not posting on social media this week.")
        schema = SOCIAL_SCHEMA if online else sim.SCHEMA
        parsed, text, err, use = call(i["model"], prompt, schema, i["seed"], level, sim.valid_week)
        self.count(err, use)
        e = {"persona": p["id"], "week": w, "prompt": sim.SYSTEM + "\n\n" + prompt, "response": text,
             "error": err, "had_flight_this_week": has_flight, "flight_outcome": outcome, "usage": use, "feed": feed,
             "strike_day": world["strike_day"], "within_24h": world["within_24h"], "flights": world["flights"]}
        if parsed:
            e.update(status=parsed["status"], would_book_again=parsed["would_book_again"],
                     complaint=bool(parsed.get("complaint")), support_contact=parsed.get("support_contact", ""),
                     said=parsed.get("said", ""), action=parsed.get("action", ""),
                     post=str(parsed.get("post") or "").strip()[:POST_CHARS],
                     trust=parsed.get("trust") if parsed.get("trust") in (1, 2, 3, 4, 5) else None,
                     memory_after=remember(self.memory[p["id"]], f"Week {w}: {parsed['memory_update']}"))
        return e

    def probe(self, when):
        i, key = self.info, self.probe_key(when)
        i["phase"] = f"check-in ({when})"
        with _fp_locks[key]:
            ck = load_ckpt(key)
            if ck:
                i["calls_done"] += len(self.personas)
            else:
                def ask(p):
                    if self.cancel_flag.is_set():
                        return None
                    prompt = sim.probe_prompt(shown(p), self.memory[p["id"]])
                    parsed, text, err, use = call(i["model"], prompt, sim.PROBE_SCHEMA, i["seed"], "LOW", sim.valid_probe)
                    self.count(err, use)
                    return {"persona": p["id"], "prompt": sim.SYSTEM + "\n\n" + prompt, "response": text,
                            "error": err, "scores": parsed}
                entries = self.compute(key, ask)
                save_ckpt(key, {"fp": key, "when": when, "origin_run": self.name, "created": now(),
                                "model": i["model"], "entries": entries})
                self.audit("probe_done", when=when)

    def count(self, err, use):
        with _lock:
            self.info["calls_done"] += 1
            if err:
                self.info["errors"] += 1
            for k in ("in", "out", "think"):
                self.info["tokens"][k] += (use or {}).get(k) or 0

    # -------------------------------------------- reading a timeline
    def timeline(self):
        """{persona id: [(week, prompt, response)]} for the weeks that match the current inputs."""
        b = self.inputs_now()
        valid = chain_length(b["fps"], self.info["played"])
        out = defaultdict(list)
        for w in range(1, valid + 1):
            for e in load_ckpt(b["fps"][w])["entries"]:
                out[e["persona"]].append((w, e["prompt"], e["response"]))
        return b["personas"], valid, out

    def rows(self):
        """weekly.jsonl-shaped rows for the weeks played so far (live view of a session)."""
        b = self.inputs_now()
        valid = chain_length(b["fps"], self.info["played"])
        rows = []
        for w in range(1, valid + 1):
            ck = load_ckpt(b["fps"][w])
            for e in ck["entries"]:
                rows.append({"persona": e["persona"], "week": w, "call": f"{self.name}-{e['persona']}-w{w}-week",
                             "status": e["status"], "had_flight_this_week": e["had_flight_this_week"],
                             "flight_outcome": e["flight_outcome"], "would_book_again": e["would_book_again"],
                             "complaint": e["complaint"], "support_contact": e["support_contact"],
                             "post": e.get("post", ""), "feed": e.get("feed", []),
                             "said": e.get("said", ""), "action": e.get("action", ""), "trust": e.get("trust"),
                             "strike_day": e.get("strike_day"), "within_24h": e.get("within_24h"),
                             "flights": e.get("flights", []), "reused": ck.get("origin_run") != self.name})
        return b, rows

    def find_call(self, cid):
        m = re.fullmatch(rf"{re.escape(self.name)}-(.+)-w(\d+)-week", cid)
        if not m:
            return None
        b = self.inputs_now()
        ck = load_ckpt(b["fps"][int(m.group(2))])
        e = next((e for e in (ck or {}).get("entries", []) if e["persona"] == m.group(1)), None)
        return e and {"id": cid, "persona": e["persona"], "week": e["week"], "prompt": e["prompt"],
                      "response": e["response"], "model": self.config["model"], "error": e["error"]}


# ---------------------------------------------------------------- outputs
def archive(out):
    """Keep the previous version of a run in logs/archive (calls stay in the checkpoints)."""
    if not (out / "run.json").exists():
        if out.exists():
            shutil.rmtree(out)
        return
    dest = LOGS / "archive" / out.name / datetime.now().strftime("%Y%m%d-%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    for f in out.iterdir():
        if f.is_file() and f.name != "calls.jsonl":
            shutil.copy2(f, dest / f.name)
    shutil.rmtree(out)
    log("run_archived", run=out.name, to=str(dest.relative_to(HERE)))


def assemble(run, out):
    """Write the hand-in layout from the checkpoint chain; call ids are per run, per persona, per week."""
    name, i = run.name, run.info
    calls, weekly, probes = [], [], []
    for w in WEEKS:
        for e in load_ckpt(run.fps[w])["entries"]:
            cid = f"{name}-{e['persona']}-w{w}-week"
            calls.append({"id": cid, "persona": e["persona"], "week": w, "prompt": e["prompt"],
                          "response": e["response"], "model": i["model"], "error": e["error"]})
            weekly.append({"persona": e["persona"], "week": w, "call": cid, "status": e["status"],
                           "had_flight_this_week": e["had_flight_this_week"], "flight_outcome": e["flight_outcome"],
                           "would_book_again": e["would_book_again"], "complaint": e["complaint"],
                           "support_contact": e["support_contact"], "post": e.get("post", ""),
                           "said": e.get("said", ""), "action": e.get("action", ""), "trust": e.get("trust"),
                           "strike_day": e.get("strike_day"), "within_24h": e.get("within_24h"),
                           "feed": e.get("feed", []), "reused": i["weeks"][str(w)] == "reused"})
    if i["probe"]:
        for when, wk in (("start", 0), ("end", 11)):
            for e in load_ckpt(run.probe_key(when))["entries"]:
                cid = f"{name}-{e['persona']}-w{wk}-probe"
                calls.append({"id": cid, "persona": e["persona"], "week": wk, "prompt": e["prompt"],
                              "response": e["response"], "model": i["model"], "error": e["error"]})
                for k in sim.PROBE_QUESTIONS:  # raw scores; 2b and 4b are not reverse-scored here
                    probes.append({"persona": e["persona"], "when": when, "question": k,
                                   "score": e["scores"][k], "call": cid})
    for fname, rows in (("calls.jsonl", calls), ("weekly.jsonl", weekly), ("probe.jsonl", probes)):
        if rows:
            (out / fname).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (out / "personas.jsonl").write_text(run.personas_text, encoding="utf-8")
    if run.config["social"]:
        (out / "social.json").write_text(json.dumps(social_graph(run.personas), indent=1), encoding="utf-8")
    (out / "run.json").write_text(json.dumps({
        "company": "kestrel", "type": i["type"], "seed": i["seed"], "model": i["model"], "decisions": run.decisions,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    sim.write_metrics(out, run.personas)
    i["metrics"] = add_metrics(out, run, weekly, probes)


def nps(rows, when):
    s = [r["score"] for r in rows if r["when"] == when and r["question"] == "3a"]
    return round(100 * (sum(x == 5 for x in s) - sum(x <= 3 for x in s)) / len(s), 1) if s else None


def observed_week_metrics(rows, probes=()):
    """Only observations recorded for one simulated week; no network or monthly extrapolation."""
    scheduled = [r for r in rows if r.get("had_flight_this_week")]
    affected = [r for r in scheduled if r.get("flight_outcome") in ("canceled", "delayed")]
    resolved = [r for r in affected if r.get("within_24h") is True]
    unresolved = [r for r in affected if r.get("within_24h") is False]
    trust = [r["trust"] for r in rows if isinstance(r.get("trust"), (int, float))]
    return {
        "personas": len(rows),
        "scheduled": len(scheduled),
        "operated": sum(r.get("flight_outcome") != "canceled" for r in scheduled),
        "canceled": sum(r.get("flight_outcome") == "canceled" for r in scheduled),
        "delayed": sum(r.get("flight_outcome") == "delayed" for r in scheduled),
        "affected": len(affected),
        "resolved_24h": len(resolved),
        "unresolved_24h": len(unresolved),
        "unknown_24h": len(affected) - len(resolved) - len(unresolved),
        "complaints": sum(bool(r.get("complaint")) for r in rows),
        "book_again_yes": sum(r.get("would_book_again") == "yes" for r in rows),
        "book_again_answered": sum(r.get("would_book_again") in ("yes", "no") for r in rows),
        "trust_average": round(sum(trust) / len(trust), 2) if trust else None,
        "trust_answered": len(trust),
        "kept_kestrel": sum(r.get("status") not in ("moved to another airline", "canceled the trip") for r in scheduled),
        "nps": nps(probes, "end") if probes else None,
        "nps_respondents": sum(r.get("when") == "end" and r.get("question") == "3a" for r in probes),
    }


# Dossier baseline, November 2: 210,000 passengers and ~1,355 flights a week, 2,500 complaints a month, NPS +12
FLIGHTS_PER_WEEK, PAX_PER_WEEK, COMPLAINTS_PER_MONTH, NPS_BASE = 1355, 210_000, 2500, 12
FARE = {"domestic": 120, "intl": 210}
SCOPE_SHARE = {"all": 1.0, "bases": 0.6, "intl": 0.25}  # share of Kestrel flights an event touches


def board_metrics(personas, weekly, decisions, surprises, probes=(), metric_weeks=None, baseline_weekly=None):
    """The board's goals in the board's units. Persona rows are weighted by represents_trips when the persona file
    has it (each persona stands for that many real trips); otherwise every persona counts once."""
    w = {p["id"]: p.get("represents_trips") or 1 for p in personas}
    by_id = {p["id"]: p for p in personas}
    weighted = all(p.get("represents_trips") for p in personas)
    net = {"id": "", "group": "", "trips": []}  # network-wide actions reach every flight

    # goal 1: network flights operated, from the world's cancel rates, strike days left out
    planned = canceled = 0.0
    played_through = max((r["week"] for r in weekly), default=0)
    metric_weeks = list(metric_weeks) if metric_weeks is not None else list(range(1, played_through + 1))
    for week in metric_weeks:
        eff = sim.effects(decisions, net, week)
        lease = sim.P["lease_factor"] if "lease" in eff else 1
        flights = FLIGHTS_PER_WEEK * (5 / 7 if week == sim.STRIKE_WEEK else 1)
        rate = sim.P["cancel"] * lease
        for e in sim.events_in_force(surprises, week):
            rate += sim.EVENT_EFFECTS.get(e.get("effect", "none"), (0, 0))[0] * SCOPE_SHARE.get(e.get("scope", "all"), 1) * lease
        c = flights * rate
        if week == sim.STRIKE_WEEK and "backup" not in eff and sim.strike_announced(surprises, week):  # Dec 24 knock-on
            c += FLIGHTS_PER_WEEK / 7 * SCOPE_SHARE["bases"] * sim.P["knock_on_cancel"]
        if "merge" in eff and week not in (8, 9):
            c += flights * sim.P["merge"]
        planned, canceled = planned + flights, canceled + c

    # goal 2: affected passengers rebooked within 24h or refunded
    # A refund counts as "within 24h" only when the passenger could get it without the phone queue (app or website)
    # or an offer within 24h existed; counting every cancellation as resolved put the no-decision run at 100%.
    hit = [r for r in weekly if r["flight_outcome"] in ("canceled", "delayed")]
    self_service = lambda r: str(by_id[r["persona"]].get("booking_channel", "")).lower() in ("app", "website")
    ok = [r for r in hit if r.get("within_24h")
          or (r["status"] in ("canceled the trip", "moved to another airline") and self_service(r))]

    # goal 3: complaints a month in December (weeks 5-9), the dossier's 2,500 scaled by the complaint rate against
    # the weeks before the first event (the same weeks in every run that shares a seed, so runs compare on one base).
    # Weights are capped at the 75th percentile: uncapped, two or three "ordinary week" personas (120-230k trips
    # each) carried over half of all complaint weight and a plan run could score worse than no decision.
    cap = sorted(w.values())[int(0.75 * (len(w) - 1))] if w else 1
    wc = {k: min(v, cap) for k, v in w.items()}
    rate = lambda rows: sum(wc[r["persona"]] * bool(r.get("complaint")) for r in rows) / max(sum(wc[r["persona"]] for r in rows), 1)
    first_event = min((e["week"] for e in surprises), default=11)
    base_rows = [r for r in (baseline_weekly if baseline_weekly is not None else weekly) if r["week"] < first_event]
    base = max(rate(base_rows), 0.01)  # floor: a few quiet weeks with no complaints should not blow up the ratio
    december = [r for r in weekly if 5 <= r["week"] <= 9] or weekly
    complaints = COMPLAINTS_PER_MONTH * rate(december) / base if weekly else None

    # goal 3b: NPS moved from +12 by the change in check-in 3a
    s, e = nps(probes, "start"), nps(probes, "end")
    nps_now = round(NPS_BASE + e - s, 1) if s is not None and e is not None else None

    # goal 4: revenue weeks 5-10 as % of plan; lost trips x fare, minus the fare cap's lost revenue
    def fare(r):
        legs = [t for t in by_id[r["persona"]]["trips"] if t["week"] == r["week"]]
        return FARE["intl"] if any({t["from"], t["to"]} & sim.INTL for t in legs) else FARE["domestic"]
    late = [r for r in weekly if r["week"] >= 5 and r["had_flight_this_week"]]
    plan = sum(w[r["persona"]] * fare(r) for r in late)
    lost = sum(w[r["persona"]] * fare(r) for r in late if r["status"] in ("moved to another airline", "canceled the trip"))
    cap = 0.5e6 if any(d["week"] <= week <= d["week"] + 1 and sim.action_key(a["action"]) == "fare_cap"
                       for week in metric_weeks if week >= 5 for d in decisions for a in d["actions"]) else 0
    revenue_weeks = sum(week >= 5 for week in metric_weeks)
    scale = PAX_PER_WEEK * revenue_weeks * 140 / plan if plan and not weighted else 1
    return {
        "goal_1": round(100 * (1 - canceled / planned), 2) if planned else None,
        "goal_2": round(100 * sum(w[r["persona"]] for r in ok) / sum(w[r["persona"]] for r in hit), 1) if hit else None,
        "goal_3": round(complaints) if complaints is not None else None,
        "goal_3b": nps_now,
        "goal_4": round(100 * (1 - (lost * scale + cap) / (plan * scale)), 2) if plan else None,
        "revenue_lost_usd": round(lost * scale + cap) if plan else None,
        "units": {
            "goal_1": f"% of planned Kestrel flights operated in week(s) {', '.join(map(str, metric_weeks))}, strike days left out (network, ~1,355 flights a week)",
            "goal_2": "% of passengers on canceled or 3h+ delayed flights rebooked within 24h, or refunded through the app or website (no phone queue)"
                      + (", weighted by represents_trips" if weighted else ", unweighted"),
            "goal_3": "complaints a month in December (weeks 5-9): 2,500 baseline scaled by the complaint rate against the weeks before the first event; weights capped at the 75th percentile",
            "goal_3b": "NPS: +12 plus the change in the check-in 3a NPS from start to end (plan_1 and nodecision_1 only)",
            "goal_4": "revenue weeks 5-10 as % of plan: lost trips x fare ($120 domestic, $210 intl), less a fare cap's $0.5M",
        },
    }


def add_metrics(out, run, weekly, probes):
    m = board_metrics(run.personas, weekly, run.decisions, run.surprises, probes)
    (out / "metrics.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    return m


# ---------------------------------------------------------------- interviews
def _between(text, start, end):
    m = re.search(re.escape(start) + r"(.*?)(?:" + end + r"|$)", text, re.S)
    return m.group(1).strip() if m else ""


def experience(entries, upto):
    """Turn a persona's week prompts and answers into a first-person record of what it lived through."""
    lines, seen, memory = [], set(), "Has the trips listed in the persona booked. Nothing has happened yet."
    for w, prompt, response in sorted(entries):
        if w > upto:
            continue
        try:
            r = json.loads(response)
        except Exception:
            r = {}
        happened = _between(prompt, f"THIS_WEEK (week {w} of 10): ", r"\nOPTIONS KNOWN")
        line = f"Week {w} ({DATES[w]}): {happened}"
        for msg in _between(prompt, "EXACT_COMPANY_MESSAGE (received by you): ", r"\nTASK:").split("\n"):
            if msg.strip() and msg not in seen:
                seen.add(msg)
                line += f' Kestrel sent you this message: "{msg.strip()}"'
        if r:
            line += (f" What you did: {r.get('action', '')}. You said: \"{r.get('said', '')}\"."
                     f" Your booking: {r.get('status')}. Would book Kestrel again: {r.get('would_book_again')}.")
            if r.get("post"):
                line += f' You posted publicly: "{r["post"]}"'
            memory = r.get("memory_update") or memory
        lines.append(line)
    return lines, memory


def interview_prompt(persona, lines, memory, week, question, asker, news=()):
    when = "before week 1 (November 1)" if week == 0 else f"the end of week {week} ({DATES[week]})"
    exp = "\n".join(lines) or "Nothing has happened yet; your trips are booked."
    heard = "\n".join(f"Week {e['week']}: {e['text']}" + (f" Reports say: {e['reading']}" if e.get("read_by") else "")
                      for e in news) or "Nothing special."
    return (f"PERSONA: {json.dumps(shown(persona), ensure_ascii=False)}\n"
            f"IT IS NOW {when}.\nNEWS YOU HAVE HEARD SO FAR:\n{heard}\nYOUR EXPERIENCES SO FAR:\n{exp}\n"
            f"WHAT IS ON YOUR MIND: {memory}\n"
            f"QUESTION from {asker}: {question}\n"
            "Answer as this person.")


def interview(timeline, source, persona_ids, question, model, seed=1, week=None, asker="an interviewer",
              surprises=(), run_log_dir=None):
    """Ask personas a free question about what they lived through up to `week`. Logged to logs/interviews.jsonl."""
    personas, valid, entries = timeline
    week = valid if week is None else max(0, min(int(week), valid))  # only weeks the persona has lived through
    chosen = [p for p in personas if p["id"] in set(persona_ids)]

    def ask(p):
        lines, memory = experience(entries.get(p["id"], []), min(week, valid))
        news = [e for e in sim.news_until(surprises, week) if e.get("known_from", e["week"]) <= week]
        prompt = interview_prompt(p, lines, memory, week, question, asker, news)
        answer, text, err, use = call(model, prompt, None, seed, "LOW", lambda a: bool(a), system=INTERVIEW_SYSTEM)
        rec = {"ts": now(), "id": h(source, p["id"], week, question, now(), random.random())[:12], "source": source,
               "persona": p["id"], "name": p.get("name"), "group": p.get("group"), "week": week, "asker": asker,
               "question": question, "answer": answer or "", "error": err, "model": model, "usage": use,
               "prompt": INTERVIEW_SYSTEM + "\n\n" + prompt}
        LOGS.mkdir(exist_ok=True)
        append_jsonl(LOGS / "interviews.jsonl", rec)
        return rec

    with ThreadPoolExecutor(max(1, len(chosen))) as pool:
        recs = list(pool.map(ask, chosen))
    if run_log_dir is not None:
        Path(run_log_dir).mkdir(parents=True, exist_ok=True)
        for rec in recs:
            append_jsonl(Path(run_log_dir) / "interviews.jsonl", rec)
    log("interview", run=source, week=week, personas=len(recs), question=question[:200], model=model,
        errors=sum(bool(r["error"]) for r in recs))
    return recs


def disk_timeline(name):
    """Timeline of a finished run from its hand-in files (works for sim.py runs too)."""
    d = RUNS / name
    _, personas = load_personas(d / "personas.jsonl")
    add_social_graph(personas)
    calls = {c["id"]: c for c in read_jsonl(d / "calls.jsonl")}
    entries = defaultdict(list)
    weeks = 0
    for r in read_jsonl(d / "weekly.jsonl"):
        c = calls.get(r["call"])
        if c:
            entries[r["persona"]].append((r["week"], c["prompt"], c["response"]))
            weeks = max(weeks, r["week"])
    return personas, weeks, entries


# ---------------------------------------------------------------- manager
class Manager:
    def __init__(self):
        self.runs = {}
        for f in sorted(SESSIONS.glob("*.json")) if SESSIONS.exists() else []:
            try:
                run = Run.load(f)
                self.runs[run.name] = run
                try:
                    run.backfill_logs()
                except Exception as e:
                    log("session_log_backfill_failed", run=run.name, error=repr(e))
            except Exception as e:
                log("session_load_failed", file=f.name, error=repr(e))

    def _free(self, name):
        cur = self.runs.get(name)
        if cur and cur.busy():
            raise ValueError(f"{name} is running")
        return cur

    def submit(self, **cfg):
        """A batch run: weeks 1-10 now."""
        cur = self._free(cfg["name"])
        if cur and cur.config["session"]:
            raise ValueError(f"{cfg['name']} is a live session; play it, or delete the session first")
        run = Run(**cfg)
        self.runs[run.name] = run
        run.audit("run_queued", **{k: v for k, v in run.config.items() if k != "name"})
        threading.Thread(target=run.execute, daemon=True, name=f"run-{run.name}").start()
        return run

    def create_session(self, **cfg):
        cur = self._free(cfg["name"])
        if cur and cur.config["session"]:
            raise ValueError(f"session {cfg['name']} already exists")
        run = Run(session=True, **cfg)
        self.runs[run.name] = run
        run.save()
        run.audit("session_created", **{k: v for k, v in run.config.items() if k != "name"})
        return run

    def play(self, name, until):
        run = self.runs[name]
        if run.busy():
            raise ValueError(f"{name} is already running")
        until = max(1, min(10, int(until)))
        run.info.update(status="queued", phase=f"queued to week {until}", target=until)
        threading.Thread(target=run.execute, args=(until,), daemon=True, name=f"play-{name}").start()
        return run

    def update_session(self, name, **changes):
        run = self._free(name)
        if changes.pop("reset", False):  # forget every played week; the next play starts at week 1
            run.info.update(played=0, chain=[], weeks={str(w): "pending" for w in WEEKS}, week_source={})
        for k in ("decisions", "surprises", "auto", "social", "personas", "model"):
            if k in changes:
                run.config[k] = changes[k]
                run.info[{"decisions": "decisions_file", "surprises": "surprises_file",
                          "personas": "personas_file"}.get(k, k)] = changes[k]
        run.save()
        run.audit("session_updated", **changes)
        return run

    def delete_session(self, name):
        run = self._free(name)
        if not run or not run.config["session"]:
            raise ValueError(f"no session {name}")
        (SESSIONS / f"{name}.json").unlink(missing_ok=True)
        del self.runs[name]
        run.audit("session_deleted", note="the audit log and checkpoints are kept")

    def official(self, decisions, surprises=None, model=DEFAULT_MODEL, personas=None, seeds=(1, 2), live=False,
                 social=True):
        """The five hand-in runs: now (batch), or as live sessions played with the calendar."""
        runs = []
        for name, kind, seed, probe in OFFICIAL:
            cfg = dict(name=name, type=kind, seed=seeds[0] if seed == 1 else seeds[1], decisions=decisions,
                       surprises=surprises, probe=probe, model=model, personas=personas, social=social)
            if live:
                cur = self.runs.get(name)
                runs.append(cur if cur and cur.config["session"] else self.create_session(auto=True, **cfg))
            else:
                runs.append(self.submit(**cfg))
        return runs

    def timeline(self, source):
        run = self.runs.get(source)
        if run and run.config["session"] and not (RUNS / source / "weekly.jsonl").exists():
            return run.timeline(), run.config
        if run and run.busy():
            return run.timeline(), run.config
        return disk_timeline(source), json.loads((RUNS / source / "run.json").read_text(encoding="utf-8"))


def list_runs(manager=None):
    """Runs on disk plus runs and sessions in memory (live state wins)."""
    rows = {}
    for d in sorted(RUNS.glob("*/")) if RUNS.exists() else []:
        info = {"name": d.name, "status": "done" if (d / "run.json").exists() else "incomplete"}
        if (d / "engine.json").exists():
            info.update(json.loads((d / "engine.json").read_text(encoding="utf-8")))
            info.pop("fps", None)
        elif (d / "run.json").exists():
            r = json.loads((d / "run.json").read_text(encoding="utf-8"))
            info.update(type=r.get("type"), seed=r.get("seed"), model=r.get("model"), engine="sim.py", played=10,
                        finished=datetime.fromtimestamp((d / "run.json").stat().st_mtime).isoformat(timespec="seconds"))
        if (d / "metrics.json").exists():
            info["metrics"] = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
        if info.get("status") in ("running", "queued") and not (manager and d.name in manager.runs):
            info.update(status="interrupted", phase="the server stopped mid-run; start it again to resume")
        rows[d.name] = info
    for name, run in (manager.runs.items() if manager else []):
        rows[name] = dict(rows.get(name, {}), **run.info)
    return sorted(rows.values(), key=lambda r: r.get("started") or r.get("finished") or r.get("created") or "",
                  reverse=True)


# ---------------------------------------------------------------- hand-in
def build_submission(team="NN"):
    """Copy the five runs, the docs and the code into submission/, zip it and run check.py on it."""
    name = f"team-{team}_submission"
    base = HERE / "submission"
    root = base / name
    if root.exists():
        shutil.rmtree(root)
    (root / "runs").mkdir(parents=True)
    notes = []
    for run, *_ in OFFICIAL:
        src = RUNS / run
        if (src / "run.json").exists():
            shutil.copytree(src, root / "runs" / run)
            model = json.loads((src / "run.json").read_text())["model"]
            if MODELS.get(model, {}).get("offline"):
                notes.append(f"WARNING {run} was made with the offline mock model; re-run it with a real model")
        else:
            notes.append(f"missing run {run}")
    for doc in ("CLIENT_MEMO.md", "TEAM_DOC.md"):
        src = next((p for p in (HERE.parent / doc, HERE / doc) if p.exists()), None)
        if src:
            shutil.copy2(src, root / doc)
        else:
            notes.append(f"{doc} not found next to code/ or in code/")
    shutil.copytree(HERE, root / "code", ignore=shutil.ignore_patterns(
        ".env", ".venv", ".claude", "runs", "checkpoints", "logs", "sessions", "submission", "__pycache__",
        ".DS_Store", "*.pyc"))
    zip_path = shutil.make_archive(str(base / name), "zip", base, name)
    res = subprocess.run([sys.executable, str(CHECK_PY), zip_path], capture_output=True, text=True)
    log("submission_built", zip=str(Path(zip_path).relative_to(HERE)), check_exit=res.returncode, notes=notes)
    return {"zip": zip_path, "check_exit": res.returncode, "check": res.stdout + res.stderr, "notes": notes}


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="run name, or 'official' for the five hand-in runs")
    ap.add_argument("--type", choices=["plan", "nodecision", "plan_nosurprises"], default="plan")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--decisions")
    ap.add_argument("--surprises", default="surprises.json")
    ap.add_argument("--personas", default=DEFAULT_PERSONAS)
    ap.add_argument("--no-social", action="store_true", help="personas do not see each other's posts")
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=list(MODELS))
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--until", type=int, default=10, help="play weeks 1..until only")
    ap.add_argument("--replicate", type=int, default=0, help="a new number gives a fresh sample, ignoring checkpoints")
    ap.add_argument("--workers", type=int, default=80, help="LLM calls in flight across all runs")
    a = ap.parse_args()
    load_env()
    LIMIT.set(a.workers)
    mgr = Manager()
    if a.name == "official":
        runs = mgr.official(a.decisions, a.surprises, a.model, a.personas, social=not a.no_social)
    else:
        cfg = dict(name=a.name, type=a.type, seed=a.seed, decisions=a.decisions, surprises=a.surprises,
                   probe=a.probe, model=a.model, personas=a.personas, replicate=a.replicate, social=not a.no_social)
        run = Run(**cfg)
        mgr.runs[run.name] = run
        threading.Thread(target=run.execute, args=(a.until,), daemon=True).start()
        runs = [run]
    time.sleep(0.2)
    while any(r.busy() for r in runs):
        time.sleep(2)
        print(" | ".join(f"{r.name}: {r.info['phase']} {r.info['calls_done']}/{r.info['calls_total']}"
                         for r in runs), flush=True)
    for r in runs:
        print(r.name, r.info["status"], r.info["error"] or "", json.dumps(r.info["metrics"] or {})[:200])
    return 0 if all(r.info["status"] in ("done", "paused") for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
