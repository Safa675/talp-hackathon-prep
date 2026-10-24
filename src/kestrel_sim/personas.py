"""Load either persona set into one common shape.

Common fields on every persona:
  id, group, set, name, age, home, tagline, tags, quote (or None),
  card_rows [(label, text)], trips [{date, week, from, to}], strike_exposed,
  weight (passenger trips over the ten weeks this persona stands for),
  connections (persona ids), profile (the text the model reads as "who you are").
Set-specific fields are kept as they are in the source file.

Sets:
  clusters  data/personas/clusters/personas.jsonl, built by pipelines/personas (66 personas).
  curated   data/personas/curated/personas.json, hand-written archetype -> member library (30 personas).
"""
import datetime as dt
import json

from . import config

D0 = dt.date.fromisoformat(config.WEEK1_MONDAY)
TOTAL_TRIPS = 2_166_860  # ten-week passenger trips, from pipelines/personas/make_clusters.py
WINDOW_LABEL = {"strike": "strike days", "holiday": "holiday weeks", "thanksgiving": "Thanksgiving",
                "ordinary": "ordinary week"}


def week_of(date_iso):
    return (dt.date.fromisoformat(date_iso) - D0).days // 7 + 1


def is_strike_exposed(trips):
    return any(t["date"] in config.STRIKE_DATES and {t["from"], t["to"]} & config.BASES for t in trips)


def load_personas(source=config.DEFAULT_PERSONA_SET):
    if source not in config.PERSONA_SETS:
        raise ValueError(f"unknown persona set {source!r}; choose from {', '.join(config.PERSONA_SETS)}")
    loader = {"clusters": _load_clusters, "curated": _load_curated}[source]
    personas = loader(config.PERSONA_SETS[source])
    _add_social_graph(personas)
    return personas


def _add_social_graph(personas, k=3, seed=2026):
    """Who hears whom. Curated personas keep their hand-written connections. Cluster personas get a fixed
    graph (same in every run): two links to people with the same home area or group, one random link.
    Influencers (high social-media activity, or creators in the curated set) also reach everyone as
    'trending' posts; see engine."""
    import random
    rng = random.Random(seed)
    ids = [p["id"] for p in personas]
    for p in personas:
        role = str(p.get("attributes", {}).get("social_role", "")).lower()
        p["influencer"] = (p.get("social_media_activity") == "high" or "opinion leader" in p.get("tags", [])
                           or "creator" in role or "followers" in role)
        if p.get("connections"):
            continue
        near = [q["id"] for q in personas if q["id"] != p["id"]
                and (q.get("home") == p.get("home") or q["group"] == p["group"])]
        picks = rng.sample(near, min(k - 1, len(near)))
        rest = [i for i in ids if i != p["id"] and i not in picks]
        picks += rng.sample(rest, 1)
        p["connections"] = picks


def export_jsonl(personas, path):
    """Write the flat personas.jsonl that goes into a run folder."""
    with open(path, "w", encoding="utf-8") as f:
        for p in personas:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


# --- clusters ---------------------------------------------------------------------------------

def _load_clusters(path):
    personas = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        trips = [{"date": t["date"], "week": t["week"], "from": t["from"], "to": t["to"]} for t in p["trips"]]
        p.update({
            "set": "clusters", "home": p["home_area"], "tagline": p["occupation"], "quote": None,
            "archetype": p["segment"], "archetype_label": p["segment_description"],
            "tags": [f"{p['date_flexibility']} dates", f"{p['money_pressure']} money pressure",
                     WINDOW_LABEL.get(p["window"], p["window"])],
            "card_rows": [("Values", p["values_most"]), ("When it goes wrong", p["reaction_to_disruption"])],
            "trips": trips, "strike_exposed": is_strike_exposed(trips), "weight": p["represents_trips"],
            "connections": p.get("connections", []),
        })
        p["profile"] = _cluster_profile(p)
        personas.append(p)
    return personas


def _cluster_profile(p):
    news = ", ".join(p["news_sources"]) if isinstance(p["news_sources"], list) else p["news_sources"]
    return f"""Name: {p['name']}, {p['age']}, {p['gender']}, lives in {p['home_area']}
Occupation: {p['occupation']} ({p['employment_status']}); household: {p['household']}; income {p['household_income_band']}
Customer type: {p['segment_description']} ({p['group']})
This trip: {p['trip_reason']}; travelling with {p['travel_party']}; airport assistance: {p['airport_assistance']}; bags: {p['checks_bags']}
Date flexibility: {p['date_flexibility']} ({p['flexibility_reason']}); who pays: {p['who_pays']}
Money pressure: {p['money_pressure']}; knows refund rights: {p['knows_refund_rights']}
Kestrel loyalty tier: {p['loyalty_tier']}; also flies other airlines: {'yes' if p['also_flies_rivals'] else 'no'}; books via {p['booking_channel']}
Social media activity: {p['social_media_activity']}; news from: {news}
Tendency to complain: {p['complaint_tendency']}; patience: {p['patience']}; forgiveness: {p['forgiveness']}
What you value most: {p['values_most']}
Past Kestrel experience: {p['past_kestrel_experience']}
When a flight goes wrong you usually: {p['reaction_to_disruption']}
Your story: {p['narrative']}

Your booked Kestrel flights:
{_trip_lines(p['trips'])}"""


# --- curated ----------------------------------------------------------------------------------

def _curated_date(text):
    """'Dec 23' -> '2026-12-23'; January dates fall in 2027."""
    d = dt.datetime.strptime(f"{text} 2026", "%b %d %Y").date()
    return (d.replace(year=2027) if d.month == 1 else d).isoformat()


def _load_curated(path):
    lib = json.loads(path.read_text(encoding="utf-8"))
    personas = []
    for arch in lib["archetypes"]:
        n = len(arch["members"])
        for m in arch["members"]:
            p = dict(m)
            t = p["trip"]
            date = _curated_date(t["date"])
            origin, dest = t["route"].split("-")
            trips = [{"date": date, "week": week_of(date), "from": origin, "to": dest}]
            p.update({
                "set": "curated", "group": arch["group"], "archetype": arch["id"],
                "archetype_label": arch["label"], "core_tension": arch["core_tension"], "shared": arch["shared"],
                "home": f"{p['city']}, {p['state']}",
                "card_rows": [("Wins over", p["wins_over"]), ("Breaks at", p["breaks_at"])],
                "trips": trips, "strike_exposed": is_strike_exposed(trips),
                "weight": round(arch["share"] * TOTAL_TRIPS / n),
            })
            p["profile"] = _curated_profile(p)
            personas.append(p)
    return personas


def _curated_profile(p):
    t = p["trip"]
    shared = "\n".join(f"- {k.replace('_', ' ')}: {v if not isinstance(v, list) else ', '.join(v)}"
                       for k, v in p["shared"].items())
    attrs = "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in p["attributes"].items())
    return f"""Name: {p['name']}, {p['age']}, {p['home']}
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

Your booked Kestrel flight (travelling with {t['travels_with']}, {'fixed date' if t['fixed_date'] else 'flexible date'}, \
checked bags: {t['checked_bags']}, airport assistance: {t['assistance'] or 'none'}):
{_trip_lines(p['trips'])}"""


def _trip_lines(trips):
    return "\n".join(f"- {t['date']} (week {t['week']}): {t['from']} -> {t['to']}" for t in trips)
