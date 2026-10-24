#!/usr/bin/env python3
"""One-page simulation room. No installs beyond the venv.

    .venv/bin/python server.py            ->  http://localhost:8765

A simulation plays week by week with the company calendar (settings.json: date, start of week 1, grace
minutes): with auto on it plays week N once week N has started plus the grace time, and plays again when
a new event or decision makes a played week stale.
"""
import argparse
import json
import re
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import engine

HERE = engine.HERE
PAGE = HERE / "ui" / "simple.html"
SETTINGS = HERE / "settings.json"
SAFE = re.compile(r"^(decisions|surprises|personas)[\w.-]*\.jsonl?$")
MGR = engine.Manager()


# ---------------------------------------------------------------- calendar
def calendar():
    """Real-time company calendar: 30 minutes per week from the start of week 1."""
    s = {"date": datetime.now().date().isoformat(), "calendar_start": "13:00", "grace_min": 3}
    if SETTINGS.exists():
        s.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    t0 = datetime.fromisoformat(f"{s['date']}T{s['calendar_start']}")
    starts = [t0 + timedelta(minutes=30 * i) for i in range(11)]
    n = datetime.now()
    week = 0 if n < starts[0] else next((w for w in engine.WEEKS if n < starts[w]), 11)
    return {**s, "week": week, "starts": [x.isoformat(timespec="seconds") for x in starts]}


def autoplay():
    """Play auto simulations up to the current calendar week; replay when an edit made a week stale."""
    while True:
        try:
            cal = calendar()
            due = min(cal["week"], 10)
            if due:
                ready = datetime.now() >= datetime.fromisoformat(cal["starts"][due - 1]) + timedelta(minutes=cal["grace_min"])
                target = due if ready or cal["week"] == 11 else due - 1
                for run in list(MGR.runs.values()):
                    if not (run.config["session"] and run.config["auto"]) or run.busy() or run.info["status"] == "failed":
                        continue
                    played = run.info["played"]
                    stale = run.validity().get("valid_through", played) < min(played, target)
                    if target and (played < target or stale):
                        engine.log("autoplay", run=run.name, until=target, stale=stale)
                        MGR.play(run.name, target)
        except Exception as e:
            engine.log("autoplay_error", error=repr(e))
        time.sleep(15)


# ---------------------------------------------------------------- files
def read_input(name):
    text = (HERE / name).read_text(encoding="utf-8")
    return [json.loads(l) for l in text.splitlines() if l.strip()] if name.endswith(".jsonl") else json.loads(text)


def save_input(name, content, note=""):
    """Write an events or decisions file. Events nobody has read yet are read by the model first."""
    if not SAFE.match(name):
        raise ValueError("file name must start with decisions, surprises or personas")
    if name.startswith("surprises"):
        content = [engine.read_event(e) if not e.get("known_crisis") and (e.get("effect", "auto") == "auto" or not e.get("reading"))
                   else e for e in content]
    issues = engine.validate_decisions(content)[0] if name.startswith("decisions") else []
    (HERE / name).write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    engine.log("input_saved", file=name, note=note, items=len(content), issues=issues)
    for run in MGR.runs.values():
        if name in (run.config.get("decisions"), run.config.get("surprises")):
            fingerprint = engine.h(content)
            engine.write_json_atomic(run.log_dir / "inputs" / f"{name}.{fingerprint}.json", content)
            run.audit("input_saved", file=name, note=note, items=len(content), fingerprint=fingerprint)
    return {"saved": True, "content": content, "issues": issues}


# ---------------------------------------------------------------- runs
_disk = {}


def budget(decisions):
    """(issues, cost in $M) by the engine's own board rules, so the page and the hand-in check agree."""
    try:
        return engine.validate_decisions(decisions)
    except Exception as e:
        return [f"could not check the decisions: {type(e).__name__}: {e}"], None


def outdated_from(eng):
    """First week whose inputs (code, personas, model, decisions, events) changed since the run was made;
    0 means from the start, None means it still matches today's files."""
    try:
        now_fps = engine.inputs({"type": eng["type"], "seed": eng["seed"], "decisions": eng.get("decisions_file"),
                                 "surprises": eng.get("surprises_file"), "model": eng["model"],
                                 "personas": eng.get("personas_file"), "replicate": eng.get("replicate", 0),
                                 "social": eng.get("social")})["fps"]
    except Exception:
        return None
    old = eng.get("fps") or []
    return next((w for w in range(11) if w >= len(old) or old[w] != now_fps[w]), None)


def disk_detail(name):
    """A finished run as it was handed in (runs/<name>/), read-only: weeks, personas, check-ins, its log."""
    d = engine.RUNS / name
    if not re.fullmatch(r"[\w.-]+", name or "") or not (d / "run.json").exists():
        return None
    stamp = [(d / f).stat().st_mtime if (d / f).exists() else 0 for f in ("run.json", "weekly.jsonl", "engine.json")]
    if name not in _disk or _disk[name][0] != stamp:
        run = json.loads((d / "run.json").read_text(encoding="utf-8"))
        eng = json.loads((d / "engine.json").read_text(encoding="utf-8")) if (d / "engine.json").exists() else {}
        fps = eng.get("fps") or []
        _, personas = engine.load_personas(d / "personas.jsonl")
        flights = {}  # what happened to each flight is kept in the checkpoints, not in weekly.jsonl
        for w in engine.WEEKS:
            for e in ((engine.load_ckpt(fps[w]) or {}) if len(fps) > w else {}).get("entries", []):
                flights[e["persona"], w] = e.get("flights", [])
        rows = [dict(r, flights=flights.get((r["persona"], r["week"]), [])) for r in engine.read_jsonl(d / "weekly.jsonl")]
        probes = engine.read_jsonl(d / "probe.jsonl")
        log_dir = engine.LOGS / "runs" / name / str(eng.get("log_id"))
        if (log_dir / "week-10.json").exists():  # the events this run actually knew
            surprises = json.loads((log_dir / "week-10.json").read_text(encoding="utf-8"))["events_known"]
        else:
            try:
                surprises = json.loads(engine.resolve(eng["surprises_file"]).read_text(encoding="utf-8"))
                surprises = [e for e in surprises if e.get("known_crisis") or e.get("known_crisis_update") or run["type"] != "plan_nosurprises"]
            except Exception:
                surprises = []
        played = max((r["week"] for r in rows), default=0)
        info = {k: v for k, v in eng.items() if k != "fps"}
        info.update(name=name, type=run["type"], seed=run["seed"], model=run["model"], status="done", played=played,
                    target=played, session=False, auto=False, phase="finished run", social=(d / "social.json").exists())
        _disk[name] = (stamp, eng, {
            "info": info, "config": {"session": False, "seed": run["seed"], "model": run["model"],
                                     "decisions": eng.get("decisions_file"), "surprises": eng.get("surprises_file")},
            "personas": personas, "weekly": rows, "validity": {"valid_through": played, "stale_from": None},
            "decisions": run["decisions"], "surprises": surprises, "readonly": True,
            "log_dir": str(log_dir) if log_dir.exists() else None,
            "goals": json.loads((d / "metrics.json").read_text(encoding="utf-8")) if (d / "metrics.json").exists() else None,
            "goals_by_week": {str(w): engine.observed_week_metrics([r for r in rows if r["week"] == w],
                                                                   probes if w == 10 else ())
                              for w in sorted({r["week"] for r in rows})}})
    _, eng, out = _disk[name]
    return dict(out, outdated_from=outdated_from(eng) if eng else None, budget=budget(out["decisions"]))


def handin():
    """For each finished hand-in run: the first week that no longer matches today's events and decisions."""
    out = {}
    for n, *_ in engine.OFFICIAL:
        f, run = engine.RUNS / n / "engine.json", MGR.runs.get(n)
        if (run and run.busy()) or not f.exists() or not (engine.RUNS / n / "run.json").exists():
            continue
        out[n] = outdated_from(json.loads(f.read_text(encoding="utf-8")))
    return out


def detail(name):
    run = MGR.runs.get(name)
    if not run or not (run.config["session"] or run.busy()):
        d = disk_detail(name)  # a finished batch run: exactly what was handed in
        if d or not run:
            return d
    b, rows = run.rows()
    val = run.validity()
    probe_path = engine.RUNS / name / "probe.jsonl"
    probes = engine.read_jsonl(probe_path) if run.info["played"] == 10 else []
    weekly_goals = {str(w): engine.observed_week_metrics([r for r in rows if r["week"] == w],
                                                        probes if w == 10 else ())
                    for w in sorted({r["week"] for r in rows})}
    return {"info": run.info, "config": run.config, "personas": b["personas"], "weekly": rows,
            "validity": {k: v for k, v in val.items() if k in ("valid_through", "stale_from", "error")},
            "decisions": b["decisions"], "surprises": b["surprises"], "budget": budget(b["decisions"]),
            "goals": engine.board_metrics(b["personas"], rows, b["decisions"], b["surprises"], probes) if rows else None,
            "goals_by_week": weekly_goals}


def state():
    runs = engine.list_runs(MGR)
    return {"runs": runs, "models": engine.MODELS, "default_model": engine.DEFAULT_MODEL, "calendar": calendar(),
            "official": [n for n, *_ in engine.OFFICIAL], "handin": handin(),
            "key_set": bool(__import__("os").environ.get("TALP_KEY"))}


def log_dir_of(name):
    run = MGR.runs.get(name)
    if run:
        return run.log_dir, run.info["log_id"]
    d = disk_detail(name)
    return (Path(d["log_dir"]), d["info"].get("log_id")) if d and d["log_dir"] else (None, None)


# ---------------------------------------------------------------- http
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, obj, code=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/":
                return self.send(PAGE.read_bytes(), ctype="text/html; charset=utf-8")
            if u.path == "/api/state":
                return self.send(state())
            if u.path == "/api/meta":
                _, personas = engine.load_personas(HERE / engine.DEFAULT_PERSONAS)
                return self.send({"menu": engine.MENU, "budget": engine.BUDGET, 
                                  "groups": sorted({p["group"] for p in personas}),
                                  "targets": list(engine.sim.TARGET_RULES)})
            if u.path == "/api/run":
                r = detail(q["name"])
                return self.send(r) if r else self.send({"error": "no such simulation"}, 404)
            if u.path == "/api/logs":
                log_dir, log_id = log_dir_of(q.get("name"))
                if not log_dir:
                    return self.send({"error": "no such simulation"}, 404)
                if "week" in q:
                    week = int(q["week"])
                    if not 1 <= week <= 10:
                        return self.send({"error": "week must be 1-10"}, 400)
                    path = log_dir / f"week-{week:02d}.json"
                    return self.send(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else self.send({"error": "week not logged"}, 404)
                state_file = log_dir / "state.json"
                return self.send({"run": q["name"], "log_id": log_id, "path": str(log_dir),
                                  "state": json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else None,
                                  "events": engine.read_jsonl(log_dir / "events.jsonl"),
                                  "weeks": sorted(int(p.stem.split("-")[1]) for p in log_dir.glob("week-*.json"))})
            if u.path == "/api/file":
                if not SAFE.match(q["name"]):
                    return self.send({"error": "bad name"}, 400)
                return self.send({"name": q["name"], "content": read_input(q["name"])})
            self.send({"error": "not found"}, 404)
        except Exception as e:
            self.send({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if u.path == "/api/session":
                cfg = {k: body[k] for k in ("name", "type", "seed", "decisions", "surprises", "probe", "model",
                                            "personas", "auto", "social") if k in body}
                cfg["replicate"] = int(time.time())  # a new simulation starts from scratch: no week is reused
                cfg["surprises"] = f"surprises_{cfg['name']}.json"  # its own events, empty: nothing left over
                (HERE / cfg["surprises"]).write_text("[]\n", encoding="utf-8")
                return self.send(MGR.create_session(**cfg).info)
            if u.path == "/api/session/delete":  # the simulation goes; its checkpoints stay
                MGR.delete_session(body["name"])
                return self.send({"ok": True})
            if u.path == "/api/session/update":
                return self.send(MGR.update_session(body.pop("name"), **body).info)
            if u.path == "/api/play":
                return self.send(MGR.play(body["name"], body["until"]).info)
            if u.path == "/api/cancel":
                MGR.runs[body["name"]].cancel()
                return self.send({"ok": True})
            if u.path == "/api/interview":
                run, week = MGR.runs.get(body["source"]), body.get("week")  # the persona knows every event up to that week
                if run and (run.config["session"] or run.busy()):
                    timeline, cfg, news, log_dir = run.timeline(), run.config, engine.inputs(run.config)["surprises"], run.log_dir
                else:  # a finished run: the personas live through the weeks it handed in
                    d = disk_detail(body["source"])
                    if not d:
                        return self.send({"error": "no such simulation"}, 404)
                    timeline, cfg, news, log_dir = engine.disk_timeline(body["source"]), d["config"], d["surprises"], d["log_dir"]
                return self.send(engine.interview(timeline, body["source"], body["personas"], body["question"].strip(),
                                                  body.get("model") or cfg["model"], cfg["seed"], week,
                                                  body.get("asker") or "an interviewer", news, run_log_dir=log_dir))
            if u.path == "/api/file":
                return self.send(save_input(body["name"], body["content"], body.get("note", "")))
            if u.path == "/api/official":  # the five hand-in runs: weeks 1-10 now, with every event entered so far
                src = MGR.runs[body["from"]].config
                busy = [n for n, *_ in engine.OFFICIAL if n in MGR.runs and MGR.runs[n].busy()]
                if busy:
                    return self.send({"error": f"still running: {', '.join(busy)}; wait or stop them first"}, 409)
                if src["type"] == "nodecision" or not src["decisions"]:
                    return self.send({"error": f"{src['name']} has no decisions; add the two locked decisions first"}, 400)
                issues = engine.validate_decisions(engine.inputs(src)["decisions"])[0]
                for n, *_ in engine.OFFICIAL:  # hand-in sessions from the old live button give way to batch runs
                    if n in MGR.runs and MGR.runs[n].config["session"]:
                        MGR.delete_session(n)
                runs = MGR.official(src["decisions"], src["surprises"], body.get("model") or src["model"],
                                    src["personas"], social=src["social"])
                return self.send({"runs": [r.name for r in runs], "issues": issues})
            if u.path == "/api/submission":
                return self.send(engine.build_submission(re.sub(r"\D", "", str(body.get("team", ""))).zfill(2)[:2]))
            self.send({"error": "not found"}, 404)
        except Exception as e:
            self.send({"error": f"{type(e).__name__}: {e}"}, 400)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    engine.load_env()
    engine.log("server_started", port=a.port)
    threading.Thread(target=autoplay, daemon=True, name="autoplay").start()
    print(f"Simulation room: http://localhost:{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
