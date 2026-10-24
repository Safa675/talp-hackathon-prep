"""Load the archetype -> member persona library and flatten it into personas.

personas.json is the human-edited source. Each member inherits its archetype's
shared traits; member fields win on conflict. export_jsonl() writes the
personas.jsonl file that goes into every run folder.
"""
import json

from . import config

STRIKE_DATES = {"Dec 22", "Dec 23"}
STRIKE_BASES = {"MCO", "PHL"}


def load_library(path=config.PERSONA_SOURCE):
    return json.loads(path.read_text(encoding="utf-8"))


def load_personas(path=config.PERSONA_SOURCE):
    lib = load_library(path)
    weekly = lib["meta"]["weekly_passengers"]
    personas = []
    for arch in lib["archetypes"]:
        n = len(arch["members"])
        for m in arch["members"]:
            p = dict(m)
            p["group"] = arch["group"]
            p["archetype"] = arch["id"]
            p["archetype_label"] = arch["label"]
            p["core_tension"] = arch["core_tension"]
            p["shared"] = arch["shared"]
            p["weight"] = round(arch["share"] * weekly / n)
            p["strike_exposed"] = is_strike_exposed(p["trip"])
            personas.append(p)
    return personas


def is_strike_exposed(trip):
    airports = set(trip["route"].split("-"))
    return trip["date"] in STRIKE_DATES and bool(airports & STRIKE_BASES)


def export_jsonl(personas, path=config.PERSONA_EXPORT):
    with open(path, "w", encoding="utf-8") as f:
        for p in personas:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


def profile_text(p):
    """The persona as the model reads it: archetype traits first, then the individual."""
    trip = p["trip"]
    shared = "\n".join(f"- {k.replace('_', ' ')}: {v if not isinstance(v, list) else ', '.join(v)}"
                       for k, v in p["shared"].items())
    attrs = "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in p["attributes"].items())
    assistance = trip["assistance"] or "none"
    return f"""Name: {p['name']}, {p['age']}, {p['city']}, {p['state']}
Who you are: {p['tagline']}
Customer type: {p['archetype_label']} ({p['group']})
What typically matters to people like you: {p['core_tension']}
Typical traits of people like you:
{shared}
Your own traits (these override the typical ones):
{attrs}
What wins you over: {p['wins_over']}
What makes you give up on a company: {p['breaks_at']}
Your story: {p['backstory']}

Your next Kestrel Air trip: {trip['date']}, {trip['route']}, travelling with {trip['travels_with']}, \
{'fixed date' if trip['fixed_date'] else 'flexible date'}, checked bags: {trip['checked_bags']}, \
airport assistance: {assistance}."""
