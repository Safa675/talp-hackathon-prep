"""Crises as inputs: the known strike, and surprises from the dashboard announcements export.

Announcements are mapped to weeks by publish time (week N starts at 13:00 + 30 min x (N-1)).
How we read each surprise lives in data/crises/readings.json (edit it by hand: it is our reading).
An announcement with no reading yet is read once by the model (a call with persona null) and the
reading is saved there, so every later run uses the same reading.

A reading:
  {"is_crisis": true, "title": ..., "week": 6, "until_week": 7, "scope": "all" | "bases" | "intl" | "PHL" | "MCO",
   "extra_cancel": 0.04, "extra_delay": 0.10, "news": "what passengers hear, in plain words",
   "kestrel_caused": false, "reading": "how we read it, one or two sentences"}
"""
import datetime as dt
import json
from pathlib import Path

from . import config

READINGS = config.DATA_DIR / "crises" / "readings.json"
DAY0 = dt.datetime.fromisoformat("2026-10-24T13:00:00+03:00")  # week 1 start, Istanbul time

STRIKE_NEWS = {
    1: "Kestrel's ground handling contractor's workers (baggage, cleaning, wheelchair agents, fuelers) "
       "have announced a 48-hour strike at Orlando and Philadelphia on December 22-23. Talks continue.",
    4: "Holiday travel is at a record. Talks between Kestrel's ground handling contractor and the union "
       "have not settled the planned December 22-23 strike.",
    6: "The union at Kestrel's ground handling contractor says the December 22-23 strike is on and "
       "'may be extended'. The contractor says it will bring in replacement staff where it can.",
    7: "Next week: a 48-hour ground handling strike is planned at Kestrel's Orlando and Philadelphia "
       "bases on Dec 22-23, the busiest days of the year. Travelers are told to watch for messages.",
    8: "STRIKE: ground handling workers walked out at Kestrel's Orlando and Philadelphia bases on Dec "
       "22-23. Long lines, slow turnarounds, delayed bags and canceled flights are reported.",
    9: "The ground handling strike at Kestrel's bases ended after 48 hours. Social media is full of "
       "Christmas travel stories, good and bad.",
}

INTERPRET = """You are the crisis analyst of a simulation of Kestrel Air, a US low-cost airline (bases Orlando MCO
and Philadelphia PHL; 36 aircraft, 210,000 passengers a week; 75% US, 25% Mexico/Caribbean).
A dashboard announcement arrived at the start of week {week} (the ten weeks run Nov 2 - Jan 10).
Crisis texts are deliberately vague. Read it as a careful analyst: serious but survivable; no single
crisis sinks the company.

Announcement title: {title}
Announcement text: {body}

Return JSON:
{{"is_crisis": true/false (false for organizer notes such as prizes or tests),
  "title": "short name",
  "week": {week}, "until_week": last week it affects operations (>= {week}, <= 10),
  "scope": "all" | "bases" | "intl" | "PHL" | "MCO",
  "extra_cancel": extra share of flights canceled while it lasts (0-0.15),
  "extra_delay": extra share of flights delayed 3h+ while it lasts (0-0.3),
  "kestrel_caused": true/false (true only if Kestrel itself is at fault under DOT rules),
  "news": "2-3 sentences that passengers would read in the news this week, factual, no numbers we do not know",
  "reading": "1-2 sentences: how we read its size, who hears about it, what is unknown"}}"""


def week_of_publish(iso):
    t = dt.datetime.fromisoformat(iso)
    mins = (t - DAY0).total_seconds() / 60
    return max(1, min(10, int(mins // 30) + 1)) if mins >= 0 else 0


def load_announcements(path):
    if not path or not Path(path).exists():
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("announcements", data) if isinstance(data, dict) else data
    out = []
    for a in items:
        week = a.get("week") or week_of_publish(a.get("published_at") or a.get("publish_at"))
        out.append({"id": a["id"], "title": a.get("title", ""), "body": a.get("body", ""), "week": week})
    return out


def readings_path(announcements_file):
    """Real announcements -> readings.json; the test file gets its own, so test readings never mix in."""
    return READINGS.with_name("test_readings.json") if "test" in Path(announcements_file).name else READINGS


def load_readings(path=READINGS):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def read_surprises(announcements, llm, path=READINGS):
    """Readings for every announcement that is a crisis inside weeks 1-10. New ones are read by the model."""
    readings = load_readings(path)
    changed = False
    for a in announcements:
        if a["id"] in readings:
            continue
        if a["week"] < 1:  # published before the calendar started: an organizer note
            readings[a["id"]] = {"is_crisis": False, "title": a["title"], "reading": "published before week 1"}
            changed = True
            continue
        prompt = INTERPRET.format(week=a["week"], title=a["title"], body=a["body"])
        parsed, raw, call = llm.generate_json(prompt, persona=None, week=a["week"])
        r = parsed or {"is_crisis": False, "reading": f"could not parse model reading: {raw[:200]}"}
        r.update({"source": "model", "call": call, "announcement": a})
        readings[a["id"]] = r
        changed = True
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(readings, indent=1, ensure_ascii=False), encoding="utf-8")
    return [dict(readings[a["id"]], id=a["id"]) for a in announcements if readings[a["id"]].get("is_crisis")]


def active(surprises, week):
    return [s for s in surprises if s["week"] <= week <= s.get("until_week", s["week"])]


def in_scope(s, leg):
    scope = s.get("scope", "all")
    airports = {leg["from"], leg["to"]}
    if scope == "all":
        return True
    if scope == "bases":
        return bool(airports & config.BASES)
    if scope == "intl":
        return bool(airports & {"CUN", "PUJ", "MBJ", "NAS", "SDQ", "GDL", "SJU", "MEX"})
    return scope in airports
