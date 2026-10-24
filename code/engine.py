#!/usr/bin/env python3
"""Checkpointed, resumable Kestrel simulation engine. World and prompts come from sim.py.

    set -a; . ./.env; set +a
    python engine.py plan_1 --type plan --seed 1 --decisions decisions.json --probe
    python engine.py exp_a --type plan --seed 1 --decisions decisions.json --model gemini-3.5-flash-lite
    python engine.py official --decisions decisions.json          # the five hand-in runs, in parallel

Every week ends in a checkpoint named by a hash of everything that can change that week:
the prompt code in sim.py, the personas, model, seed, the decisions in force and the surprises
announced so far. A run starts after the last week whose whole chain is already on disk, so a late
announcement for week 9 re-runs only weeks 9-10, and runs that share a prefix (plan_1 and
nodecision_1 before the first decision week) compute those weeks once and share them.
Personas in a week run in parallel; weeks run in sequence (week N reads week N-1's memory).
"""
import argparse
import hashlib
import inspect
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import sim

HERE = sim.HERE
RUNS = HERE / "runs"
CKPT = HERE / "checkpoints"
LOGS = HERE / "logs"
CHECK_PY = HERE.parent / "yeni-case-5-sirket" / "check.py"
ENGINE_VERSION = 1
WEEKS = range(1, 11)
BASE_AIRPORTS = {"MCO", "PHL"}
# Simulation labels some persona files carry; the customer must not see them.
ENGINE_HIDDEN = set(sim.HIDDEN_FIELDS) | {"window", "cluster", "segment", "segment_description",
                                         "represents_trips", "share_pct"}

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
CHANNELS = ["app", "email", "text", "social media"]

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


LIMIT = Limiter(30)


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


def prompt_code_hash():
    """Anything in sim.py that shapes a prompt or the world; editing it invalidates checkpoints."""
    parts = [inspect.getsource(f) for f in (sim.targeted, sim.option_lines, sim.company_message,
                                            sim.trips_in_week, sim.week_facts, sim.visible,
                                            sim.week_prompt, sim.probe_prompt)]
    return h(parts, sim.SYSTEM, sim.KESTREL_FACTS, sim.SCHEMA, sim.PROBE_QUESTIONS, sim.STATUSES,
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
    return json.dumps({"status": status, "would_book_again": wba, "action": "mock", "said": "(mock answer)",
                       "reason": "mock", "support_contact": "none", "complaint": status != "flies as planned",
                       "memory_update": f"Status so far: {status}."})


def call(model, prompt, schema, seed, level, validate):
    """Returns (parsed, raw_text, error). Retries a malformed answer with the same prompt."""
    if MODELS.get(model, {}).get("offline"):
        text = mock_answer(prompt, schema, seed)
        return json.loads(text), text, ""
    from google.genai import types
    if MODELS.get(model, {"thinking": True})["thinking"]:
        extra = {"thinking_config": types.ThinkingConfig(thinking_level=level)}
    else:
        extra = {"temperature": 1.0}
    last = ("", "")
    for _ in range(3):
        try:
            with LIMIT:
                r = client().models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=sim.SYSTEM, seed=seed, response_mime_type="application/json",
                        response_schema=schema, max_output_tokens=2048, **extra),
                )
            text = r.text or ""
            last = (text, "")
            parsed = json.loads(text)
            if validate(parsed):
                return parsed, text, ""
        except Exception as e:  # malformed JSON, 429, timeout
            last = (last[0], repr(e))
    return None, last[0], last[1] or "invalid answer"


# ---------------------------------------------------------------- inputs
def load_personas(path):
    text = Path(path).read_text(encoding="utf-8")
    personas = [json.loads(l) for l in text.splitlines() if l.strip()]
    for p in personas:  # world-side label; derived when a persona file does not carry it
        p.setdefault("touches_base", any(t["from"] in BASE_AIRPORTS or t["to"] in BASE_AIRPORTS
                                         for t in p.get("trips", [])))
    return text, personas


def shown(persona):
    return {k: v for k, v in persona.items() if k not in ENGINE_HIDDEN}


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
        if not d.get("target"):
            issues.append(f"decision {i}: no target")
        acts = d.get("actions") or []
        if not 1 <= len(acts) <= 3:
            issues.append(f"decision {i}: needs 1-3 actions")
        for a in acts:
            levels = MENU.get(a.get("action"))
            if levels is None:
                issues.append(f"decision {i}: '{a.get('action')}' is not on the menu")
            elif a.get("level") not in levels:
                issues.append(f"decision {i}: level '{a.get('level')}' not in {list(levels)}")
            else:
                cost += levels[a["level"]]
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


def ckpt_stats():
    files = list(CKPT.glob("*.json")) if CKPT.exists() else []
    return {"count": len(files), "mb": round(sum(f.stat().st_size for f in files) / 1e6, 1),
            "partial": len(list(CKPT.glob("*.partial.jsonl"))) if CKPT.exists() else 0}


# ---------------------------------------------------------------- run
class Run:
    def __init__(self, name, type, seed, decisions=None, surprises=None, probe=False, model=DEFAULT_MODEL,
                 personas=None, replicate=0):
        self.cancel_flag = threading.Event()
        self.info = {
            "name": name, "type": type, "seed": int(seed), "model": model, "probe": bool(probe),
            "decisions_file": decisions, "surprises_file": surprises or "surprises.json",
            "personas_file": personas or "personas.jsonl", "replicate": int(replicate),
            "status": "queued", "phase": "queued", "weeks": {str(w): "pending" for w in WEEKS},
            "week_source": {}, "calls_done": 0, "calls_total": 0, "errors": 0, "resumed_from": 0,
            "queued": now(), "started": None, "finished": None, "error": None, "metrics": None,
        }
        if model not in MODELS:
            raise ValueError(f"unknown model {model}")
        if type not in ("plan", "nodecision", "plan_nosurprises"):
            raise ValueError(f"unknown type {type}")

    @property
    def name(self):
        return self.info["name"]

    def cancel(self):
        self.cancel_flag.set()

    # -------------------------------------------- setup
    def prepare(self):
        i = self.info
        self.personas_text, self.personas = load_personas(resolve(i["personas_file"]))
        self.decisions = [] if i["type"] == "nodecision" or not i["decisions_file"] else \
            json.loads(resolve(i["decisions_file"]).read_text(encoding="utf-8"))
        surprises = json.loads(resolve(i["surprises_file"]).read_text(encoding="utf-8"))
        self.surprises = [] if i["type"] == "plan_nosurprises" else surprises
        base = h(prompt_code_hash(), self.personas_text, i["model"], i["seed"], i["replicate"])
        self.fps = [base]
        for w in WEEKS:
            self.fps.append(h(self.fps[-1], w, [d for d in self.decisions if d["week"] <= w],
                              [s for s in self.surprises if s["week"] == w]))
        self.memory = {p["id"]: "Has the trips listed in the persona booked. No problems so far." for p in self.personas}

    def probe_key(self, when):
        return h(self.fps[0] if when == "start" else self.fps[10], "probe", when)

    # -------------------------------------------- execution
    def execute(self):
        i = self.info
        try:
            i.update(status="running", started=now(), phase="preparing")
            self.prepare()
            out = RUNS / i["name"]
            archive(out)
            out.mkdir(parents=True, exist_ok=True)
            start = 0
            while start < 10 and load_ckpt(self.fps[start + 1]):
                start += 1
            if start:
                self.memory = {e["persona"]: e["memory_after"] for e in load_ckpt(self.fps[start])["entries"]}
                for w in range(1, start + 1):
                    self.mark_reused(w, load_ckpt(self.fps[w]))
            n = len(self.personas)
            i["resumed_from"] = start
            i["calls_total"] = n * (10 - start) + (n * 2 if i["probe"] else 0)
            log("run_started", run=i["name"], type=i["type"], seed=i["seed"], model=i["model"],
                resumed_from_week=start, fp_base=self.fps[0], decisions=len(self.decisions),
                surprises=len(self.surprises))
            self.write_engine_json()
            if i["probe"]:
                self.probe("start")
            for w in range(start + 1, 11):
                self.week(w)
            if i["probe"]:
                self.probe("end")
            i["phase"] = "writing outputs"
            assemble(self, out)
            i.update(status="done", phase="done", finished=now())
            log("run_finished", run=i["name"], metrics=i["metrics"], resumed_from_week=start,
                seconds=round(time.time() - datetime.fromisoformat(i["started"]).timestamp()))
        except Canceled:
            i.update(status="canceled", phase="canceled", finished=now())
            log("run_canceled", run=i["name"], note="finished calls are kept; a re-run resumes from them")
        except Exception as e:
            i.update(status="failed", phase="failed", finished=now(), error=f"{type(e).__name__}: {e}")
            log("run_failed", run=i["name"], error=i["error"])
        self.write_engine_json()
        return self

    def mark_reused(self, w, ck):
        self.info["weeks"][str(w)] = "reused"
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
                log("week_reused", run=i["name"], week=w, fp=fp, origin_run=ck.get("origin_run"))
                i["calls_done"] += len(self.personas)
            else:
                i["weeks"][str(w)] = "running"
                t0 = time.time()
                entries = self.compute(fp, lambda p: self.step(p, w))
                ck = {"fp": fp, "prev": self.fps[w - 1], "week": w, "model": i["model"], "seed": i["seed"],
                      "origin_run": i["name"], "created": now(), "seconds": round(time.time() - t0, 1),
                      "entries": entries}
                save_ckpt(fp, ck)
                i["weeks"][str(w)] = "computed"
                i["week_source"][str(w)] = {"fp": fp, "origin_run": i["name"], "created": ck["created"]}
                counts = Counter(e["status"] for e in entries)
                log("week_done", run=i["name"], week=w, fp=fp, seconds=ck["seconds"], statuses=dict(counts),
                    complaints=sum(bool(e.get("complaint")) for e in entries))
        self.memory = {e["persona"]: e["memory_after"] for e in ck["entries"]}
        self.write_engine_json()

    def compute(self, fp, step):
        """Run step for every persona, resuming from a partial file left by a crash or cancel."""
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
        has_flight, outcome, facts = sim.week_facts(p, w, rng, self.surprises, True)
        prompt = sim.week_prompt(shown(p), self.memory[p["id"]], w, facts,
                                 sim.option_lines(self.decisions, p, w), sim.company_message(self.decisions, p, w))
        level = "MEDIUM" if w in sim.CRISIS_WEEKS else "LOW"
        parsed, text, err = call(i["model"], prompt, sim.SCHEMA, i["seed"], level, sim.valid_week)
        self.count(err)
        e = {"persona": p["id"], "week": w, "prompt": sim.SYSTEM + "\n\n" + prompt, "response": text,
             "error": err, "had_flight_this_week": has_flight, "flight_outcome": outcome}
        if parsed:
            e.update(status=parsed["status"], would_book_again=parsed["would_book_again"],
                     complaint=bool(parsed.get("complaint")), support_contact=parsed.get("support_contact", ""),
                     said=parsed.get("said", ""), action=parsed.get("action", ""),
                     memory_after=f"Week {w}: {parsed['memory_update']}")  # rolling memory, as in sim.py
        return e

    def probe(self, when):
        i, key = self.info, self.probe_key(when)
        i["phase"] = f"check-in ({when})"
        with _fp_locks[key]:
            ck = load_ckpt(key)
            if ck:
                i["calls_done"] += len(self.personas)
                log("probe_reused", run=i["name"], when=when, origin_run=ck.get("origin_run"))
            else:
                def ask(p):
                    if self.cancel_flag.is_set():
                        return None
                    prompt = sim.probe_prompt(shown(p), self.memory[p["id"]])
                    parsed, text, err = call(i["model"], prompt, sim.PROBE_SCHEMA, i["seed"], "LOW", sim.valid_probe)
                    self.count(err)
                    return {"persona": p["id"], "prompt": sim.SYSTEM + "\n\n" + prompt, "response": text,
                            "error": err, "scores": parsed}
                entries = self.compute(key, ask)
                save_ckpt(key, {"fp": key, "when": when, "origin_run": i["name"], "created": now(),
                                "entries": entries})
                log("probe_done", run=i["name"], when=when)
        self.write_engine_json()

    def count(self, err):
        with _lock:
            self.info["calls_done"] += 1
            if err:
                self.info["errors"] += 1

    def write_engine_json(self):
        out = RUNS / self.name
        if out.exists():
            data = dict(self.info, fps=getattr(self, "fps", []))
            (out / "engine.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


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
                           "support_contact": e["support_contact"], "reused": i["weeks"][str(w)] == "reused"})
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
    (out / "run.json").write_text(json.dumps({
        "company": "kestrel", "type": i["type"], "seed": i["seed"], "model": i["model"], "decisions": run.decisions,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    sim.write_metrics(out, run.personas)
    i["metrics"] = add_metrics(out, run.personas, weekly, probes)


def nps(rows, when):
    s = [r["score"] for r in rows if r["when"] == when and r["question"] == "3a"]
    return round(100 * (sum(x == 5 for x in s) - sum(x <= 3 for x in s)) / len(s), 1) if s else None


def add_metrics(out, personas, weekly, probes):
    m = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    if probes:
        m["goal_3b"] = nps(probes, "end")
        m["nps_start"] = nps(probes, "start")
        m["units"]["goal_3b"] = "NPS proxy at the end from check-in 3a (5 = promoter, 1-3 = detractor); start in nps_start"
    weight = {p["id"]: p.get("represents_trips") for p in personas}
    if all(weight.values()):  # persona files that carry how many real trips each persona stands for
        flown = [r for r in weekly if r["had_flight_this_week"]]
        tot = sum(weight[r["persona"]] for r in flown) or 1
        lost = sum(weight[r["persona"]] for r in flown if r["status"] in ("moved to another airline", "canceled the trip"))
        canc = sum(weight[r["persona"]] for r in flown if r["flight_outcome"] == "canceled")
        m["weighted"] = {"goal_1": round(100 * (1 - canc / tot), 1), "goal_4": round(100 * (1 - lost / tot), 1),
                         "unit": "same as goal_1 / goal_4, persona rows weighted by represents_trips"}
    (out / "metrics.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    return m


# ---------------------------------------------------------------- manager
class Manager:
    def __init__(self):
        self.runs = {}

    def submit(self, **cfg):
        name = cfg["name"]
        cur = self.runs.get(name)
        if cur and cur.info["status"] in ("queued", "running"):
            raise ValueError(f"{name} is already running")
        run = Run(**cfg)
        self.runs[name] = run
        log("run_queued", run=name, **{k: v for k, v in cfg.items() if k != "name"})
        threading.Thread(target=run.execute, daemon=True, name=f"run-{name}").start()
        return run

    def official(self, decisions, surprises=None, model=DEFAULT_MODEL, personas=None, seeds=(1, 2)):
        runs = []
        for name, kind, seed, probe in OFFICIAL:
            seed = seeds[0] if seed == 1 else seeds[1]
            runs.append(self.submit(name=name, type=kind, seed=seed, decisions=decisions, surprises=surprises,
                                    probe=probe, model=model, personas=personas))
        return runs


def list_runs(manager=None):
    """Runs on disk plus runs in memory (live state wins)."""
    rows = {}
    for d in sorted(RUNS.glob("*/")) if RUNS.exists() else []:
        info = {"name": d.name, "status": "done" if (d / "run.json").exists() else "incomplete"}
        if (d / "engine.json").exists():
            info.update(json.loads((d / "engine.json").read_text(encoding="utf-8")))
            info.pop("fps", None)
        elif (d / "run.json").exists():
            r = json.loads((d / "run.json").read_text(encoding="utf-8"))
            info.update(type=r.get("type"), seed=r.get("seed"), model=r.get("model"), engine="sim.py",
                        finished=datetime.fromtimestamp((d / "run.json").stat().st_mtime).isoformat(timespec="seconds"))
        if (d / "metrics.json").exists():
            info["metrics"] = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
        rows[d.name] = info
    for name, run in (manager.runs.items() if manager else []):
        rows[name] = dict(run.info)
    return sorted(rows.values(), key=lambda r: r.get("started") or r.get("finished") or "", reverse=True)


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
        ".env", ".venv", ".claude", "runs", "checkpoints", "logs", "submission", "__pycache__", ".DS_Store", "*.pyc"))
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
    ap.add_argument("--personas", default="personas.jsonl")
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=list(MODELS))
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--replicate", type=int, default=0, help="a new number gives a fresh sample, ignoring checkpoints")
    ap.add_argument("--workers", type=int, default=30, help="LLM calls in flight across all runs")
    a = ap.parse_args()
    load_env()
    LIMIT.set(a.workers)
    mgr = Manager()
    if a.name == "official":
        runs = mgr.official(a.decisions, a.surprises, a.model, a.personas)
    else:
        runs = [mgr.submit(name=a.name, type=a.type, seed=a.seed, decisions=a.decisions, surprises=a.surprises,
                           probe=a.probe, model=a.model, personas=a.personas, replicate=a.replicate)]
    while any(r.info["status"] in ("queued", "running") for r in runs):
        time.sleep(2)
        print(" | ".join(f"{r.name}: {r.info['phase']} {r.info['calls_done']}/{r.info['calls_total']}"
                         for r in runs), flush=True)
    for r in runs:
        print(r.name, r.info["status"], r.info["error"] or "", json.dumps(r.info["metrics"] or {})[:200])
    return 0 if all(r.info["status"] == "done" for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
