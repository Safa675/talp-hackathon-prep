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
        content = [engine.read_event(e) if e.get("effect", "auto") == "auto" or not e.get("reading") else e
                   for e in content]
    issues = engine.validate_decisions(content)[0] if name.startswith("decisions") else []
    (HERE / name).write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    engine.log("input_saved", file=name, note=note, items=len(content), issues=issues)
    return {"saved": True, "content": content, "issues": issues}


# ---------------------------------------------------------------- runs
def detail(name):
    run = MGR.runs.get(name)
    if not run:
        return None
    b, rows = run.rows()
    val = run.validity()
    return {"info": run.info, "config": run.config, "personas": b["personas"], "weekly": rows,
            "validity": {k: v for k, v in val.items() if k in ("valid_through", "stale_from", "error")},
            "decisions": b["decisions"], "surprises": b["surprises"],
            "goals": engine.board_metrics(b["personas"], rows, b["decisions"], b["surprises"]) if rows else None}


def state():
    runs = engine.list_runs(MGR)
    return {"runs": runs, "models": engine.MODELS, "default_model": engine.DEFAULT_MODEL, "calendar": calendar(),
            "official": [n for n, *_ in engine.OFFICIAL], "key_set": bool(__import__("os").environ.get("TALP_KEY"))}


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
                return self.send(MGR.create_session(**cfg).info)
            if u.path == "/api/session/update":
                return self.send(MGR.update_session(body.pop("name"), **body).info)
            if u.path == "/api/play":
                return self.send(MGR.play(body["name"], body["until"]).info)
            if u.path == "/api/cancel":
                MGR.runs[body["name"]].cancel()
                return self.send({"ok": True})
            if u.path == "/api/interview":
                run = MGR.runs[body["source"]]
                week = body.get("week")  # the persona knows every event announced up to the week asked about
                return self.send(engine.interview(run.timeline(), run.name, body["personas"], body["question"].strip(),
                                                  body.get("model") or run.config["model"], run.config["seed"], week,
                                                  body.get("asker") or "an interviewer",
                                                  engine.inputs(run.config)["surprises"]))
            if u.path == "/api/file":
                return self.send(save_input(body["name"], body["content"], body.get("note", "")))
            if u.path == "/api/official":  # the five hand-in runs as auto simulations, with this one's inputs
                src = MGR.runs[body["from"]].config
                runs = MGR.official(src["decisions"], src["surprises"], body.get("model") or src["model"],
                                    src["personas"], live=True, social=src["social"])
                return self.send([r.name for r in runs])
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
