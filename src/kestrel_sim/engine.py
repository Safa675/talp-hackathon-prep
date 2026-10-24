"""The ten-week simulation. One run = one persona set, one decision file (or none), surprises on or off, one seed.

Each week, for every persona in parallel:
  1. code sets the events: the outcome of each Kestrel flight that week (world.py), the news
     (known strike timeline + active surprises), the company's messages (decisions targeted at them,
     word for word, from their week on), and last week's posts from their connections and trending ones;
  2. Gemini, playing the persona, decides what they think and do, and reports a dossier status;
  3. code updates the state: memory, bookings lost or moved, complaints, posts for next week.
Check-in questions run before week 1 (week 0) and after week 10 (week 11) when probe=True.
Outputs follow 'How to save your runs' in the challenge.
"""
import json
from pathlib import Path

from . import config, crises, decisions as dec, prompts, world
from .llm import Gemini
from .personas import export_jsonl, load_personas

RUN_TYPES = ("plan", "nodecision", "plan_nosurprises")


class Run:
    def __init__(self, run_type, seed, persona_set=config.DEFAULT_PERSONA_SET, decision_file=None,
                 announcements_file=None, surprises=True, probe=False, model=config.DEFAULT_MODEL,
                 only=None, weeks=10):
        assert run_type in RUN_TYPES
        self.run_type, self.seed, self.probe, self.weeks = run_type, seed, probe, weeks
        self.llm = Gemini(model=model, seed=seed)
        self.personas = load_personas(persona_set)
        self.all_personas = self.personas
        if only:
            self.personas = [p for p in self.personas if p["id"] in set(only)]
        self.by_id = {p["id"]: p for p in self.all_personas}
        self.decisions = dec.load(decision_file) if run_type != "nodecision" else []
        anns = crises.load_announcements(announcements_file) if surprises and run_type != "plan_nosurprises" else []
        self.surprises = crises.read_surprises(anns, self.llm, crises.readings_path(announcements_file)) if anns else []
        for p in self.personas:
            p["strike_exposed_original"] = p["strike_exposed"]
        self.state = {p["id"]: {"memory": [], "last_status": None, "lost": set(), "moved": {},
                                "disrupted_weeks": [], "posts": {}, "weekly": {}} for p in self.personas}
        self.weekly_rows, self.probe_rows, self.outcomes = [], [], []

    # --- per-week inputs ------------------------------------------------------------------------
    def legs_in_week(self, p, week):
        st = self.state[p["id"]]
        legs = []
        for i, t in enumerate(p["trips"]):
            if i in st["lost"]:
                continue
            t = st["moved"].get(i, t)
            if t["week"] == week:
                legs.append((i, t))
        return legs

    def upcoming(self, p, week):
        st = self.state[p["id"]]
        out = []
        for i, t in enumerate(p["trips"]):
            t2 = st["moved"].get(i, t)
            if i in st["lost"]:
                out.append(f"{t['date']} {t['from']}-{t['to']}: no longer booked with Kestrel")
            elif t2["week"] > week:
                out.append(f"{t2['date']} {t2['from']}-{t2['to']} (week {t2['week']})")
        return out

    def news(self, week):
        items = [world_news for w, world_news in sorted(crises.STRIKE_NEWS.items()) if w == week]
        if week > 1 and week not in crises.STRIKE_NEWS:
            items.append(crises.STRIKE_NEWS[max(w for w in crises.STRIKE_NEWS if w < week)].split(". ")[0] + ".")
        for s in crises.active(self.surprises, week):
            items.append(s["news"])
        return items

    def feed(self, p, week):
        if week == 1:
            return []
        posts = []
        for c in p.get("connections", []):
            post = self.state.get(c, {}).get("posts", {}).get(week - 1)
            if post:
                posts.append(f"{self.by_id[c]['name']}: \"{post}\"")
        trending = [(q["id"], self.state[q["id"]]["posts"].get(week - 1)) for q in self.personas
                    if q.get("influencer") and q["id"] != p["id"] and q["id"] not in p.get("connections", [])]
        trending = [(i, t) for i, t in trending if t]
        r = world.rng_for(self.seed, "trending", week, p["id"])
        for i, t in r.sample(trending, min(2, len(trending))):
            posts.append(f"Trending on social media, {self.by_id[i]['name']}: \"{t}\"")
        return posts

    def messages(self, p, week):
        st = self.state[p["id"]]
        return [d["message"] for d in self.decisions if dec.targets(d, p, week, st["disrupted_weeks"])]

    # --- one persona-week -----------------------------------------------------------------------
    def persona_week(self, p, week, effects):
        st = self.state[p["id"]]
        events, outs = [], []
        for i, leg in self.legs_in_week(p, week):
            o = world.leg_outcome(self.seed, p, leg, effects, self.surprises, week)
            o["index"] = i
            outs.append(o)
            events.append(world.describe(o, p))
            if o["disrupted"]:
                st["disrupted_weeks"].append(week)
        change_offer = []
        if "free_changes" in effects:
            for i, t in enumerate(p["trips"]):
                t2 = st["moved"].get(i, t)
                # flights later in the two-week window (this week's flights have already happened)
                if i not in st["lost"] and t2["week"] > week and "free_changes" in self.effects_by_week[t2["week"]]:
                    change_offer.append(f"{t2['date']} {t2['from']}-{t2['to']}")
        ctx = {"memory": st["memory"][-6:], "last_status": st["last_status"], "events": events,
               "upcoming": self.upcoming(p, week), "news": self.news(week), "feed": self.feed(p, week),
               "messages": self.messages(p, week), "change_offer": change_offer}
        prompt = prompts.week_prompt(p, week, ctx)
        for _ in range(3):  # retry if the reply has no parseable status
            parsed, raw, call = self.llm.generate_json(prompt, persona=p["id"], week=week)
            status = prompts.parse_status(str((parsed or {}).get("status_line") or raw))
            if parsed and status and prompts.parse_status(raw) == status:  # the status words must be in the reply
                break
        parsed = parsed or {}
        status = status or (st["last_status"] or "flies as planned")
        return {"p": p, "week": week, "parsed": parsed, "status": status, "call": call, "outs": outs,
                "change_offer": change_offer, "raw_ok": bool(parsed) and prompts.parse_status(raw) is not None}

    def apply(self, res):
        p, week, parsed, status = res["p"], res["week"], res["parsed"], res["status"]
        st = self.state[p["id"]]
        change = str(parsed.get("change_flight", "keep")).lower()
        if res["change_offer"] and change != "keep":
            for i, t in enumerate(p["trips"]):
                t2 = st["moved"].get(i, t)
                if f"{t2['date']} {t2['from']}-{t2['to']}" not in res["change_offer"]:
                    continue
                if "cancel" in change:
                    st["lost"].add(i)
                elif world.on_strike(t2):
                    new_date = "2026-12-21" if "earlier" in change else "2026-12-26"
                    st["moved"][i] = dict(t2, date=new_date, week=8)
        if status in ("moved to another airline", "canceled the trip"):
            for i, t in enumerate(p["trips"]):
                t2 = st["moved"].get(i, t)
                if t2["week"] >= week:
                    st["lost"].add(i)
        st["last_status"] = status
        if parsed.get("memory"):
            st["memory"].append(f"Week {week}: {parsed['memory']}")
        if parsed.get("post"):
            st["posts"][week] = str(parsed["post"])[:400]
        row = {"persona": p["id"], "week": week, "status": status, "call": res["call"],
               "book_again": parsed.get("book_again") if parsed.get("book_again") in config.BOOK_AGAIN else None,
               "trust": parsed.get("trust_1to5"), "nps": parsed.get("nps_0to10"),
               "complained": bool(parsed.get("complained")), "contacted_support": bool(parsed.get("contacted_support")),
               "posted": bool(parsed.get("post")), "change_flight": change if res["change_offer"] else None,
               "actions": parsed.get("actions"),
               "flights": [{"date": o["leg"]["date"], "route": f"{o['leg']['from']}-{o['leg']['to']}",
                            "canceled": o["canceled"], "delay": o["delay"], "strike": o["strike"],
                            "within_24h_offer": o.get("within_24h")} for o in res["outs"]]}
        self.weekly_rows.append(row)
        for o in res["outs"]:
            self.outcomes.append({"persona": p["id"], "week": week, "status": status, **{k: v for k, v in o.items() if k != "leg"},
                                  "date": o["leg"]["date"], "route": f"{o['leg']['from']}-{o['leg']['to']}"})

    # --- probes ---------------------------------------------------------------------------------
    def ask_probe(self, when):
        week = 0 if when == "start" else 11

        def one(p):
            st = self.state[p["id"]]
            ctx = None if when == "start" else prompts.end_probe_context(st["memory"], st["last_status"])
            prompt = prompts.probe_prompt(p, ctx) if ctx else prompts.probe_prompt(p)
            for _ in range(3):
                parsed, raw, call = self.llm.generate_json(prompt, persona=p["id"], week=week)
                if parsed and all(isinstance(parsed.get(q), int) and 1 <= parsed[q] <= 5 for q in prompts.PROBE_QUESTIONS):
                    return [{"persona": p["id"], "when": when, "question": q, "score": parsed[q], "call": call}
                            for q in prompts.PROBE_QUESTIONS]
            return []
        for rows in self.llm.map(one, self.personas):
            self.probe_rows.extend(rows)

    # --- the run --------------------------------------------------------------------------------
    def run(self):
        if self.probe:
            self.ask_probe("start")
        self.effects_by_week = {w: dec.effects(self.decisions, w) for w in range(1, 11)}
        for week in range(1, self.weeks + 1):
            eff = self.effects_by_week[week]
            results = self.llm.map(lambda p: self.persona_week(p, week, eff), self.personas)
            for r in results:
                self.apply(r)
        if self.probe and self.weeks == 10:
            self.ask_probe("end")
        return self

    def save(self, out_dir, persona_export=None):
        from .metrics import compute
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        run_json = {"company": config.COMPANY_SLUG, "type": self.run_type, "seed": self.seed,
                    "model": self.llm.model, "decisions": dec.for_run_json(self.decisions),
                    "persona_set": self.all_personas[0]["set"],
                    "surprises": [{k: s.get(k) for k in ("id", "title", "week", "until_week", "scope", "extra_cancel",
                                                         "extra_delay", "kestrel_caused", "reading")} for s in self.surprises]}
        (out / "run.json").write_text(json.dumps(run_json, indent=1, ensure_ascii=False), encoding="utf-8")
        export_jsonl([{k: v for k, v in p.items() if k not in ("strike_exposed_original",)} for p in self.all_personas],
                     out / "personas.jsonl")
        self.llm.log.write_jsonl(out / "calls.jsonl")
        with open(out / "weekly.jsonl", "w", encoding="utf-8") as f:
            for r in self.weekly_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(out / "world.jsonl", "w", encoding="utf-8") as f:
            for r in self.outcomes:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        if self.probe:
            with open(out / "probe.jsonl", "w", encoding="utf-8") as f:
                for r in self.probe_rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        metrics = compute(self)
        (out / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
        return metrics
