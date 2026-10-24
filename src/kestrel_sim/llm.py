"""Gemini client wrapper that records every call in the calls.jsonl format.

Each call is stored with id, persona, week, prompt, response and model, which
is exactly what the challenge's check.py expects.
"""
import itertools
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from google import genai
from google.genai import types

from . import config


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
    def __init__(self, model=config.DEFAULT_MODEL, seed=1, temperature=config.DEFAULT_TEMPERATURE, log=None):
        self.model = model
        self.seed = seed
        self.temperature = temperature
        self.log = log if log is not None else CallLog()
        self.client = genai.Client(
            vertexai=True, api_key=config.load_api_key(),
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=5)),
        )

    def generate(self, prompt, persona=None, week=0, as_json=False):
        """Send one prompt; return (text, call_id). The call is logged either way."""
        cfg = types.GenerateContentConfig(temperature=self.temperature, seed=self.seed)
        if as_json:
            cfg.response_mime_type = "application/json"
        try:
            reply = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
            text = reply.text or ""
        except Exception as e:  # keep the run alive; the failure is visible in the log
            text = f"ERROR: {type(e).__name__}: {e}"
        call_id = self.log.add(persona, week, prompt, text, self.model)
        return text, call_id

    def generate_json(self, prompt, persona=None, week=0):
        """Like generate, but parse the reply as JSON (None if it does not parse)."""
        text, call_id = self.generate(prompt, persona, week, as_json=True)
        return parse_json(text), text, call_id

    def map(self, fn, items, workers=config.MAX_WORKERS):
        """Run fn over items in parallel threads, preserving order."""
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(fn, items))


def parse_json(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        start, end = (text or "").find("{"), (text or "").rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None
