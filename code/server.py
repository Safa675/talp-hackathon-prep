#!/usr/bin/env python3
"""Local control room for the simulation engine. No installs beyond the venv.

    .venv/bin/python server.py            ->  http://localhost:8765
"""
import argparse
import json
import re
import shutil
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import engine

HERE = engine.HERE
UI = HERE / "ui" / "index.html"
VERSIONS = engine.LOGS / "versions"
SAFE = re.compile(r"^[\w.-]+\.jsonl?$")
MGR = engine.Manager()


def input_files():
    files = {"decisions": [], "surprises": [], "personas": []}
    for f in sorted(HERE.glob("*.json*")):
        kind = next((k for k in files if f.name.startswith(k)), None)
        if kind:
            files[kind].append(f.name)
    return files


def run_detail(name):
    d = engine.RUNS / name
    if not d.is_dir():
        live = MGR.runs.get(name)
        return {"info": live.info} if live else None
    load = lambda f: json.loads((d / f).read_text(encoding="utf-8")) if (d / f).exists() else None
    info = MGR.runs[name].info if name in MGR.runs else (load("engine.json") or {"name": name})
    personas = [{k: p.get(k) for k in ("id", "group", "name", "age", "occupation", "represents_trips")}
                for p in engine.read_jsonl(d / "personas.jsonl")]
    weekly = engine.read_jsonl(d / "weekly.jsonl")
    probe = engine.read_jsonl(d / "probe.jsonl")
    return {"info": info, "run": load("run.json"), "metrics": load("metrics.json"), "personas": personas,
            "weekly": weekly, "probe": probe,
            "history": [e for e in engine.read_jsonl(engine.LOGS / "history.jsonl") if e.get("run") == name][-200:]}


def find_call(run, cid):
    for line in open(engine.RUNS / run / "calls.jsonl", encoding="utf-8"):
        if f'"id": "{cid}"' in line:
            return json.loads(line)
    return None


def save_input(name, content, note=""):
    """Write an input file and keep every version, so the history shows what each run read."""
    if not SAFE.match(name):
        raise ValueError("file name must look like decisions_x.json or surprises_x.json")
    path = HERE / name
    VERSIONS.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    text = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
    if old == text:
        return {"saved": False}
    ver = VERSIONS / f"{path.stem}.{datetime.now().strftime('%Y%m%d-%H%M%S')}{path.suffix}"
    path.write_text(text, encoding="utf-8")
    shutil.copy2(path, ver)
    extra = {}
    if name.startswith("decisions"):
        extra["issues"], extra["budget"] = engine.validate_decisions(content)
        extra["weeks"] = [d.get("week") for d in content]
    elif name.startswith("surprises"):
        extra["weeks"] = [s.get("week") for s in content]
    engine.log("input_saved", file=name, version=ver.name, note=note, items=len(content), **extra)
    return {"saved": True, "version": ver.name, **extra}


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
            if u.path in ("/", "/index.html"):
                return self.send(UI.read_bytes(), ctype="text/html; charset=utf-8")
            if u.path == "/api/state":
                hist = engine.read_jsonl(engine.LOGS / "history.jsonl")
                return self.send({"runs": engine.list_runs(MGR), "limit": engine.LIMIT.n, "in_flight": engine.LIMIT.used,
                                  "models": engine.MODELS, "default_model": engine.DEFAULT_MODEL,
                                  "ckpt": engine.ckpt_stats(), "recent": hist[-12:][::-1], "files": input_files(),
                                  "official": engine.OFFICIAL, "key_set": bool(_key_present())})
            if u.path == "/api/meta":
                _, personas = engine.load_personas(HERE / q.get("personas", "personas.jsonl"))
                return self.send({"menu": engine.MENU, "budget": engine.BUDGET, "channels": engine.CHANNELS,
                                  "groups": sorted({p["group"] for p in personas}),
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
            if u.path == "/api/file":
                if not SAFE.match(q["name"]):
                    return self.send({"error": "bad name"}, 400)
                text = (HERE / q["name"]).read_text(encoding="utf-8")
                content = [json.loads(l) for l in text.splitlines() if l.strip()] if q["name"].endswith(".jsonl") else json.loads(text)
                return self.send({"name": q["name"], "content": content})
            if u.path == "/api/versions":
                stem = q["file"].rsplit(".", 1)[0]
                vs = sorted(VERSIONS.glob(f"{stem}.*")) if VERSIONS.exists() else []
                return self.send([v.name for v in vs][::-1])
            if u.path == "/api/version":
                if not SAFE.match(q["name"].replace("-", "_")):
                    return self.send({"error": "bad name"}, 400)
                return self.send(json.loads((VERSIONS / q["name"]).read_text(encoding="utf-8")))
            self.send({"error": "not found"}, 404)
        except Exception as e:
            self.send({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if u.path == "/api/run":
                run = MGR.submit(**{k: body.get(k) for k in ("name", "type", "seed", "decisions", "surprises",
                                                             "probe", "model", "personas", "replicate") if k in body})
                return self.send(run.info)
            if u.path == "/api/official":
                runs = MGR.official(body["decisions"], body.get("surprises"), body.get("model", engine.DEFAULT_MODEL),
                                    body.get("personas"), tuple(body.get("seeds", (1, 2))))
                return self.send([r.info for r in runs])
            if u.path == "/api/cancel":
                MGR.runs[body["name"]].cancel()
                return self.send({"ok": True})
            if u.path == "/api/limit":
                engine.LIMIT.set(body["n"])
                engine.log("workers_changed", n=engine.LIMIT.n)
                return self.send({"limit": engine.LIMIT.n})
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


def _key_present():
    import os
    return os.environ.get("TALP_KEY")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    engine.load_env()
    engine.log("server_started", port=a.port)
    print(f"Simulation control room: http://localhost:{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
