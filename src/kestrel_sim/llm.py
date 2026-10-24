"""Gemini over Vertex REST (standard library only) and a call log in calls.jsonl format.

generate() is the low-level call: retries on rate limits and server errors,
optional JSON schema, thinking parts dropped. Gemini wraps it with a seed,
a model and a thread-safe CallLog, so every call ends up in calls.jsonl with
id, persona, week, prompt, response and model, as check.py expects.
"""
import itertools
import json
import random
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import config

URL = "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"
RETRY_CODES = (429, 500, 502, 503, 504)


def generate(prompt, model=config.DEFAULT_MODEL, seed=1, temperature=config.DEFAULT_TEMPERATURE,
             schema=None, as_json=False, max_retries=6, timeout=120):
    """One generateContent call. Returns the reply text; raises RuntimeError after the last retry."""
    cfg = {"temperature": temperature, "seed": seed}
    if schema is not None or as_json:
        cfg["responseMimeType"] = "application/json"
    if schema is not None:
        cfg["responseSchema"] = schema
    body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                       "generationConfig": cfg}).encode()
    for attempt in range(max_retries):
        req = urllib.request.Request(URL.format(model=model), data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "x-goog-api-key": config.load_api_key()})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            parts = d["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code in RETRY_CODES and attempt < max_retries - 1:
                time.sleep(min(30, 2 ** attempt + random.random()))
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as e:
            if attempt < max_retries - 1:
                time.sleep(min(30, 2 ** attempt + random.random()))
                continue
            raise RuntimeError(f"call failed: {e}")


class CallLog:
    """Thread-safe, in-memory log of LLM calls."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self.calls = []

    def add(self, persona, week, prompt, response, model) -> str:
        with self._lock:
            call_id = f"c{next(self._ids):05d}"
            self.calls.append({"id": call_id, "persona": persona, "week": week,
                               "prompt": prompt, "response": response, "model": model})
        return call_id

    def write_jsonl(self, path):
        with open(path, "w", encoding="utf-8") as f:
            for c in self.calls:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")


class Gemini:
    """A model, a seed and a call log: one per run."""

    def __init__(self, model=config.DEFAULT_MODEL, seed=1, temperature=config.DEFAULT_TEMPERATURE, log=None):
        self.model = model
        self.seed = seed
        self.temperature = temperature
        self.log = log if log is not None else CallLog()

    def generate(self, prompt, persona=None, week=0, as_json=False, schema=None):
        """Send one prompt; return (text, call_id). Failures are logged as 'ERROR: ...' and not raised."""
        try:
            text = generate(prompt, model=self.model, seed=self.seed, temperature=self.temperature,
                            schema=schema, as_json=as_json)
        except RuntimeError as e:
            text = f"ERROR: {e}"
        return text, self.log.add(persona, week, prompt, text, self.model)

    def generate_json(self, prompt, persona=None, week=0, schema=None):
        """Like generate, but parse the reply as JSON (None if it does not parse)."""
        text, call_id = self.generate(prompt, persona, week, as_json=True, schema=schema)
        return parse_json(text), text, call_id

    def map(self, fn, items, workers=config.MAX_WORKERS):
        """Run fn over items in parallel threads, preserving order."""
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(fn, items))


BAD_UNICODE_ESCAPE = re.compile(r"\\u(?![0-9a-fA-F]{4})")


def parse_json(text):
    """Parse a model reply as JSON. Tolerates text around the object and broken \\u escapes
    (the model sometimes writes 'Canc\\u00un' for 'Cancún')."""
    text = text or ""
    start, end = text.find("{"), text.rfind("}")
    candidates = [text] + ([text[start:end + 1]] if start != -1 and end > start else [])
    for c in candidates:
        for attempt in (c, BAD_UNICODE_ESCAPE.sub(r"\\\\u", c)):
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                continue
    return None
