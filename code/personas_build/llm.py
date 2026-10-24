"""Minimal Vertex (Gemini) client over REST: no installs. Key from env TALP_KEY or ./.env (never logged)."""
import json, os, random, time, urllib.request, urllib.error
from pathlib import Path

def _key():
    k = os.environ.get("TALP_KEY")
    if not k:
        env = Path(__file__).with_name(".env")
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("TALP_KEY="): k = line.split("=", 1)[1].strip()
    if not k: raise SystemExit("TALP_KEY missing (set env var or .env)")
    return k

URL = "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"

def generate(prompt, model="gemini-3.5-flash-lite", seed=1, temperature=1.0, schema=None, max_retries=6, timeout=120):
    cfg = {"temperature": temperature, "seed": seed}
    if schema is not None:
        cfg["responseMimeType"] = "application/json"; cfg["responseSchema"] = schema
    body = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg}).encode()
    for attempt in range(max_retries):
        req = urllib.request.Request(URL.format(model=model), data=body, method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": _key()})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            parts = d["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(min(30, 2 ** attempt + random.random())); continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as e:
            if attempt < max_retries - 1:
                time.sleep(min(30, 2 ** attempt + random.random())); continue
            raise RuntimeError(f"call failed: {e}")
