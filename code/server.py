#!/usr/bin/env python3
"""Local control room for the simulation engine. No installs beyond the venv.

    .venv/bin/python server.py            ->  http://localhost:8765

Live sessions follow the company calendar (settings.json: date, start of week 1, grace minutes):
a session with auto on plays week N once week N has started plus the grace time, and plays again
when an input change makes a played week stale.
"""
import argparse
import json
import re
import shutil
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import engine

HERE = engine.HERE
UI = HERE / "ui" / "index.html"          # the full control room, at /advanced
SIMPLE_UI = HERE / "ui" / "simple.html"  # one page: weeks, events, decisions, persona answers, questions
VERSIONS = engine.LOGS / "versions"
SETTINGS = HERE / "settings.json"
SAFE = re.compile(r"^[\w.-]+\.jsonl?$")
KINDS = ("decisions", "surprises", "personas")
MGR = engine.Manager()


# ---------------------------------------------------------------- calendar
def settings():
    s = {"date": datetime.now().date().isoformat(), "calendar_start": "13:00", "grace_min": 3}
    if SETTINGS.exists():
        s.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    return s


def calendar():
    """Real-time company calendar: 30 minutes per week from the start of week 1."""
    s = settings()
    t0 = datetime.fromisoformat(f"{s['date']}T{s['calendar_start']}")
    starts = [t0 + timedelta(minutes=30 * i) for i in range(11)]
    n = datetime.now()
    week = 0 if n < starts[0] else next((w for w in engine.WEEKS if n < starts[w]), 11)
    return {**s, "week": week, "starts": [x.isoformat(timespec="seconds") for x in starts],
            "now": n.isoformat(timespec="seconds")}


def autoplay():
    """Play auto sessions up to the current calendar week; replay when an edit made a week stale."""
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
def input_files():
    files = []
    for f in sorted(HERE.glob("*.json*")):
        kind = next((k for k in KINDS if f.name.startswith(k)), None)
        if not kind:
            continue
        try:
            items = len(read_input(f.name))
        except Exception:
            items = None
        files.append({"name": f.name, "kind": kind, "items": items, "kb": round(f.stat().st_size / 1024, 1),
                      "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")})
    return files


def read_input(name):
    text = (HERE / name).read_text(encoding="utf-8")
    return [json.loads(l) for l in text.splitlines() if l.strip()] if name.endswith(".jsonl") else json.loads(text)


def check_input(name, content):
    issues = []
    if not isinstance(content, list):
        return ["the file must hold a list"]
    if name.startswith("decisions"):
        issues = engine.validate_decisions(content)[0]
    elif name.startswith("surprises"):
        for i, s in enumerate(content, 1):
            if type(s.get("week")) is not int or not 1 <= s["week"] <= 10 or not str(s.get("text", "")).strip():
                issues.append(f"announcement {i}: needs week 1-10 and text")
    elif name.startswith("personas"):
        ids = [p.get("id") for p in content]
        if len(set(ids)) != len(ids) or None in ids:
            issues.append("every persona needs a unique id")
        groups = {}
        for p in content:
            groups.setdefault(p.get("group"), []).append(p)
            for t in p.get("trips", []):
                if not {"date", "week", "from", "to"} <= set(t):
                    issues.append(f"{p.get('id')}: each trip needs date, week, from, to")
        small = [g for g, ps in groups.items() if len(ps) < 4]
        if len(content) < 24 or len(groups) < 3 or small or None in groups:
            issues.append(f"{len(content)} personas in {len(groups)} groups; the hand-in needs 24+, 3+ groups, 4+ each")
    return issues


def save_input(name, content, note=""):
    """Write an input file and keep every version, so the history shows what each run read."""
    if not SAFE.match(name) or not name.startswith(KINDS):
        raise ValueError("file name must start with decisions, surprises or personas and end in .json/.jsonl")
    path = HERE / name
    VERSIONS.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if name.endswith(".jsonl"):
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in content)
    else:
        text = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
    if old == text:
        return {"saved": False}
    ver = VERSIONS / f"{path.stem}.{datetime.now().strftime('%Y%m%d-%H%M%S')}{path.suffix}"
    path.write_text(text, encoding="utf-8")
    shutil.copy2(path, ver)
    extra = {"issues": check_input(name, content)}
    if name.startswith("decisions"):
        extra["budget"] = engine.validate_decisions(content)[1]
    if not name.startswith("personas"):
        extra["weeks"] = [x.get("week") for x in content]
    engine.log("input_saved", file=name, version=ver.name, note=note, items=len(content), **extra)
    stale = [r.name for r in MGR.runs.values() if r.config["session"] and r.info["played"]
             and r.validity().get("stale_from")]
    return {"saved": True, "version": ver.name, "stale_sessions": stale, **extra}


# ---------------------------------------------------------------- runs
def run_detail(name):
    run = MGR.runs.get(name)
    d = engine.RUNS / name
    load = lambda f: json.loads((d / f).read_text(encoding="utf-8")) if (d / f).exists() else None
    if run and run.config["session"] and run.info["played"] < 10:
        b, rows = run.rows()
        val = run.validity()
        return {"info": run.info, "config": run.config, "personas": b["personas"], "weekly": rows, "probe": [],
                "metrics": None, "validity": {k: v for k, v in val.items() if k in ("valid_through", "stale_from", "error")},
                "decisions": b["decisions"], "surprises": b["surprises"], "history": run_history(name),
                "social": engine.social_graph(b["personas"]) if run.config["social"] else None}
    if not d.is_dir():
        return {"info": run.info, "config": run.config, "history": run_history(name)} if run else None
    info = run.info if run else (load("engine.json") or {"name": name})
    return {"info": info, "config": run.config if run else None, "run": load("run.json"), "metrics": load("metrics.json"),
            "personas": engine.read_jsonl(d / "personas.jsonl"), "weekly": engine.read_jsonl(d / "weekly.jsonl"),
            "probe": engine.read_jsonl(d / "probe.jsonl"), "history": run_history(name), "social": load("social.json")}


def run_history(name):
    return [e for e in engine.read_jsonl(engine.LOGS / "history.jsonl") if e.get("run") == name][-200:]


def find_call(run_name, cid):
    run = MGR.runs.get(run_name)
    if run and run.config["session"] and run.info["played"] < 10:
        return run.find_call(cid)
    for line in open(engine.RUNS / run_name / "calls.jsonl", encoding="utf-8"):
        if f'"id": "{cid}"' in line:
            return json.loads(line)
    return None


def state():
    hist = engine.read_jsonl(engine.LOGS / "history.jsonl")
    runs = engine.list_runs(MGR)
    for r in runs:
        run = MGR.runs.get(r["name"])
        if run and run.config["session"] and not run.busy():
            r["validity"] = {k: v for k, v in run.validity().items() if k in ("valid_through", "stale_from", "error")}
    return {"runs": runs, "limit": engine.LIMIT.n, "in_flight": engine.LIMIT.used, "models": engine.MODELS,
            "default_model": engine.DEFAULT_MODEL, "ckpt": engine.ckpt_stats(), "recent": hist[-14:][::-1],
            "files": input_files(), "official": engine.OFFICIAL, "calendar": calendar(),
            "key_set": bool(__import__("os").environ.get("TALP_KEY"))}


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
            if u.path in ("/", "/simple"):
                return self.send(SIMPLE_UI.read_bytes(), ctype="text/html; charset=utf-8")
            if u.path in ("/advanced", "/index.html"):
                return self.send(UI.read_bytes(), ctype="text/html; charset=utf-8")
            if u.path == "/api/state":
                return self.send(state())
            if u.path == "/api/meta":
                _, personas = engine.load_personas(HERE / q.get("personas", engine.DEFAULT_PERSONAS))
                return self.send({"menu": engine.MENU, "budget": engine.BUDGET, "channels": engine.CHANNELS,
                                  "dates": engine.DATES, "groups": sorted({p["group"] for p in personas}),
                                  "targets": list(engine.sim.TARGET_RULES),
                                  "news": engine.sim.STRIKE_NEWS,
                                  "personas": [{"id": p["id"], "group": p["group"], "name": p.get("name")} for p in personas]})
            if u.path == "/api/run":
                r = run_detail(q["name"])
                return self.send(r) if r else self.send({"error": "no such run"}, 404)
            if u.path == "/api/call":
                c = find_call(q["run"], q["id"])
                return self.send(c) if c else self.send({"error": "no such call"}, 404)
            if u.path == "/api/history":
                rows = engine.read_jsonl(engine.LOGS / "history.jsonl")
                if q.get("run"):
                    rows = [r for r in rows if r.get("run") == q["run"]]
                if q.get("event"):
                    rows = [r for r in rows if r["event"] == q["event"]]
                return self.send(rows[-int(q.get("limit", 500)):][::-1])
            if u.path == "/api/interviews":
                rows = engine.read_jsonl(engine.LOGS / "interviews.jsonl")
                if q.get("source"):
                    rows = [r for r in rows if r["source"] == q["source"]]
                if q.get("persona"):
                    rows = [r for r in rows if r["persona"] == q["persona"]]
                return self.send(rows[-int(q.get("limit", 200)):][::-1])
            if u.path == "/api/file":
                if not SAFE.match(q["name"]):
                    return self.send({"error": "bad name"}, 400)
                content = read_input(q["name"])
                return self.send({"name": q["name"], "content": content, "issues": check_input(q["name"], content)})
            if u.path == "/api/versions":
                stem = q["file"].rsplit(".", 1)[0]
                vs = sorted(VERSIONS.glob(f"{stem}.2*")) if VERSIONS.exists() else []
                return self.send([v.name for v in vs][::-1])
            if u.path == "/api/version":
                if not SAFE.match(q["name"]):
                    return self.send({"error": "bad name"}, 400)
                text = (VERSIONS / q["name"]).read_text(encoding="utf-8")
                return self.send([json.loads(l) for l in text.splitlines() if l.strip()]
                                 if q["name"].endswith(".jsonl") else json.loads(text))
            self.send({"error": "not found"}, 404)
        except Exception as e:
            self.send({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            cfg = lambda: {k: body[k] for k in ("name", "type", "seed", "decisions", "surprises", "probe", "model",
                                                 "personas", "replicate", "auto", "social") if k in body}
            if u.path == "/api/run":
                c = cfg()
                c.pop("auto", None)
                return self.send(MGR.submit(**c).info)
            if u.path == "/api/session":
                return self.send(MGR.create_session(**cfg()).info)
            if u.path == "/api/session/update":
                return self.send(MGR.update_session(body.pop("name"), **body).info)
            if u.path == "/api/session/delete":
                MGR.delete_session(body["name"])
                return self.send({"ok": True})
            if u.path == "/api/play":
                names = body["names"] if "names" in body else [body["name"]]
                until = body.get("until") or min(max(calendar()["week"], 1), 10)
                started, skipped = [], []
                for n in names:
                    try:
                        MGR.play(n, until)
                        started.append(n)
                    except ValueError as e:
                        skipped.append(f"{n}: {e}")
                return self.send({"started": started, "skipped": skipped, "until": until})
            if u.path == "/api/official":
                runs = MGR.official(body["decisions"], body.get("surprises"), body.get("model", engine.DEFAULT_MODEL),
                                    body.get("personas"), tuple(body.get("seeds", (1, 2))), live=bool(body.get("live")),
                                    social=body.get("social", True))
                return self.send([r.info for r in runs])
            if u.path == "/api/cancel":
                MGR.runs[body["name"]].cancel()
                return self.send({"ok": True})
            if u.path == "/api/interview":
                source = body["source"]
                timeline, conf = MGR.timeline(source)
                recs = engine.interview(timeline, source, body["personas"], body["question"].strip(),
                                        body.get("model") or conf.get("model"), conf.get("seed", 1),
                                        body.get("week"), body.get("asker") or "an interviewer")
                return self.send(recs)
            if u.path == "/api/limit":
                engine.LIMIT.set(body["n"])
                engine.log("workers_changed", n=engine.LIMIT.n)
                return self.send({"limit": engine.LIMIT.n})
            if u.path == "/api/settings":
                s = settings()
                s.update({k: body[k] for k in ("date", "calendar_start", "grace_min") if k in body})
                SETTINGS.write_text(json.dumps(s, indent=2), encoding="utf-8")
                engine.log("settings_changed", **s)
                return self.send(calendar())
            if u.path == "/api/validate":
                issues, budget = engine.validate_decisions(body["decisions"])
                return self.send({"issues": issues, "budget": budget})
            if u.path == "/api/file":
                return self.send(save_input(body["name"], body["content"], body.get("note", "")))
            if u.path == "/api/submission":
                return self.send(engine.build_submission(re.sub(r"\D", "", str(body.get("team", ""))).zfill(2)[:2]))
            if u.path == "/api/note":
                engine.log("note", text=str(body["text"])[:2000], run=body.get("run"))
                return self.send({"ok": True})
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
    print(f"Simulation control room: http://localhost:{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
