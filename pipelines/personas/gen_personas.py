"""Instantiate one representative persona per cluster (clusters.json) with Gemini. Run once; output is frozen.
We fix: cluster, weight, trips (dates/routes from the cluster's window), age range, gender, home area.
The LLM fills: name, life details, behaviour traits and a short narrative consistent with the cluster.
Usage: python3 pipelines/personas/gen_personas.py  -> data/personas/clusters/personas.jsonl, gen_calls.jsonl
"""
import datetime as dt, json, random, sys, concurrent.futures as cf
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from kestrel_sim.llm import generate  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "personas" / "clusters"

MODEL, SEED = "gemini-3.5-flash", 2026
D0 = dt.date(2026, 11, 2)
def week(d): return (d - D0).days // 7 + 1
BASES = {"PHL", "MCO"}; INTL = {"CUN", "PUJ", "MBJ", "NAS", "SDQ", "GDL"}
CITY = {"PHL": "Philadelphia, PA", "MCO": "Orlando, FL", "CMH": "Columbus, OH", "PIT": "Pittsburgh, PA", "BWI": "Baltimore, MD",
        "BOS": "Boston, MA", "ATL": "Atlanta, GA", "TPA": "Tampa, FL", "FLL": "Fort Lauderdale, FL", "RSW": "Fort Myers, FL",
        "SJU": "San Juan, PR", "CUN": "Cancún, Mexico", "PUJ": "Punta Cana, Dominican Rep.", "MBJ": "Montego Bay, Jamaica",
        "NAS": "Nassau, Bahamas", "SDQ": "Santo Domingo, Dominican Rep.", "GDL": "Guadalajara, Mexico"}

# segment: age range of the persona, who travels, home airports, destinations, nights away
SPEC = {
 "V-park":     dict(age=(32, 48), party="spouse and their children", home=["PHL", "CMH", "PIT", "BWI"], dest=["MCO"], nights=(4, 7)),
 "V-beach":    dict(age=(26, 45), party="partner or friends", home=["PHL", "MCO"], dest=["CUN", "PUJ", "MBJ", "NAS"], nights=(4, 7)),
 "V-snowbird": dict(age=(64, 78), party="spouse", home=["PHL", "PIT", "BOS"], dest=["MCO", "TPA", "FLL"], nights=(30, 60)),
 "V-budget":   dict(age=(19, 30), party="alone or with one friend", home=["PHL", "MCO", "BOS"], dest=["SJU", "MCO", "PHL", "ATL"], nights=(2, 4)),
 "F-grandkids":dict(age=(29, 42), party="their young children (and maybe partner)", home=["PHL", "MCO"], dest=None, nights=(5, 9)),
 "F-adultkids":dict(age=(24, 40), party="alone or with partner", home=["PHL", "MCO"], dest=None, nights=(3, 6)),
 "F-multigen": dict(age=(40, 55), party="family incl. an elderly parent who needs a wheelchair at the airport", home=["PHL", "MCO"], dest=None, nights=(5, 9)),
 "F-diaspora": dict(age=(30, 55), party="family", home=["PHL", "MCO"], dest=["SDQ", "MBJ", "GDL", "PUJ"], nights=(7, 14)),
 "F-minor":    dict(age=(34, 46), party="their child (8-14) flying alone with the unaccompanied-minor service; the persona is the parent", home=["PHL", "MCO"], dest=None, nights=(5, 10)),
 "S-home":     dict(age=(18, 23), party="alone", home=["MCO", "PHL"], dest=None, nights=(10, 20)),
 "S-trip":     dict(age=(19, 23), party="a group of friends", home=["MCO", "PHL"], dest=["CUN", "PUJ"], nights=(4, 6)),
 "B-corp":     dict(age=(30, 55), party="alone", home=["PHL", "MCO"], dest=None, nights=(1, 3)),
 "B-smb":      dict(age=(30, 60), party="alone", home=["MCO", "PHL"], dest=None, nights=(1, 3)),
 "B-contract": dict(age=(25, 50), party="alone", home=["PHL", "MCO"], dest=None, nights=(14, 40)),
 "A-senior":   dict(age=(40, 65), party="a group of 20-40 seniors booked by this agent", home=["PHL"], dest=["MCO", "TPA"], nights=(4, 7)),
 "A-event":    dict(age=(28, 45), party="a wedding/event party of 15-30 booked by this agent", home=["PHL", "MCO"], dest=["PUJ", "CUN"], nights=(3, 6)),
 "A-corp":     dict(age=(30, 55), party="conference groups of 8-15 booked by this agent", home=["PHL"], dest=["MCO"], nights=(2, 4)),
}
ORD_WEEKS = [1, 2, 3, 5, 6, 7, 10]
# Names are assigned by us, not the LLM (it collapsed onto "Miller"): popular US first names by birth cohort x common US surnames.
FIRST = {  # (min_age, max_age): (women, men)
 (64, 99): (["Linda","Patricia","Barbara","Carol","Sandra","Donna","Deborah","Sharon","Kathleen","Janet","Gloria","Brenda"],
            ["Robert","James","Richard","Thomas","Gary","Larry","Dennis","Ronald","Kenneth","Stephen","Harold","Frank"]),
 (49, 63): (["Lisa","Karen","Kimberly","Michelle","Tammy","Laura","Julie","Angela","Denise","Tracy","Teresa","Dawn"],
            ["Michael","David","Mark","Steven","Jeffrey","Scott","Timothy","Brian","Todd","Kevin","Anthony","Greg"]),
 (34, 48): (["Jennifer","Jessica","Amanda","Melissa","Stephanie","Nicole","Heather","Rachel","Erica","Andrea","Monica","Crystal"],
            ["Christopher","Joshua","Matthew","Daniel","Justin","Andrew","Ryan","Jason","Brandon","Eric","Marcus","Luis"]),
 (24, 33): (["Ashley","Brittany","Samantha","Taylor","Megan","Lauren","Alexis","Danielle","Kayla","Jasmine","Vanessa","Courtney"],
            ["Tyler","Kyle","Austin","Jordan","Zachary","Dylan","Nathan","Cody","Kevin","Adrian","Derek","Evan"]),
 (0, 23):  (["Emma","Olivia","Ava","Sophia","Isabella","Madison","Chloe","Hannah","Mia","Abigail","Natalie","Gabriela"],
            ["Ethan","Noah","Jacob","Mason","Logan","Aiden","Caleb","Elijah","Jayden","Isaiah","Mateo","Owen"]),
}
SURNAMES = """Smith Johnson Williams Brown Jones Garcia Davis Rodriguez Martinez Hernandez Lopez Gonzalez Wilson Anderson Thomas Taylor
Moore Jackson Martin Lee Perez Thompson White Harris Sanchez Clark Ramirez Lewis Robinson Walker Young Allen King Wright Scott Torres
Nguyen Hill Flores Green Adams Nelson Baker Hall Rivera Campbell Mitchell Carter Roberts Gomez Phillips Evans Turner Diaz Parker Cruz
Edwards Collins Reyes Stewart Morris Morales Murphy Cook Rogers Ortiz Morgan Cooper Peterson Bailey Reed Kelly Howard Kim Cox Ward
Richardson Watson Brooks Wood James Bennett Gray Mendoza Hughes Price Alvarez Sanders Patel Myers Long Ross Foster""".split()
def assign_name(rng, age, gender, used):
    for (lo, hi), (w, m) in FIRST.items():
        if lo <= age <= hi: pool = w if gender == "woman" else m; break
    while True:
        n = f"{rng.choice(pool)} {rng.choice(SURNAMES)}"
        if n not in used and n.split()[1] not in {u.split()[1] for u in used if list(used).count(u) and sum(x.split()[1] == n.split()[1] for x in used) >= 1}:
            used.add(n); return n

# Behaviour drivers are assigned by us (the LLM put almost everyone at "medium"). Distributions are stated assumptions:
# most people never complain (2,500 complaints/month on ~900k passengers/month), many also fly rivals (dossier), few are gold.
def pick(rng, d): return rng.choices(list(d), weights=list(d.values()))[0]
def assign_traits(p, rng):
    seg, grp = p["segment"], p["group"]
    flex = {"V-budget": {"flexible": 5, "some": 3, "fixed": 2}, "V-snowbird": {"flexible": 5, "some": 3, "fixed": 2},
            "S-home": {"some": 5, "fixed": 3, "flexible": 2}, "B-corp": {"fixed": 7, "some": 3}, "B-smb": {"fixed": 5, "some": 4, "flexible": 1},
            "A-event": {"fixed": 9, "some": 1}, "F-minor": {"fixed": 8, "some": 2}}.get(seg, {"fixed": 5, "some": 3.5, "flexible": 1.5})
    if p["window"] in ("strike", "holiday", "thanksgiving") and "flexible" in flex: flex = dict(flex, flexible=flex["flexible"] * 0.5)
    money = {"students": {"high": 6, "medium": 3, "low": 1}, "business travelers": {"low": 5, "medium": 4, "high": 1},
             "travel agencies": {"medium": 6, "low": 3, "high": 1}}.get(grp, {"medium": 5, "high": 3, "low": 2})
    rights = {"business travelers": {"yes": 5, "partly": 4, "no": 1}, "travel agencies": {"yes": 8, "partly": 2}}.get(grp, {"yes": 2.5, "partly": 4, "no": 3.5})
    young = p["age"] < 35
    p.update({
        "date_flexibility": pick(rng, flex), "money_pressure": pick(rng, money), "knows_refund_rights": pick(rng, rights),
        "loyalty_tier": pick(rng, {"none": 55, "member": 38, "gold": 7}), "also_flies_rivals": rng.random() < 0.7,
        "booking_channel": "travel agency" if grp == "travel agencies" else pick(rng, {"app": 3 if p["age"] < 60 else 1, "website": 4.5, "phone": 1.5 if p["age"] < 60 else 4}),
        "social_media_activity": pick(rng, {"low": 2, "medium": 4, "high": 4} if young else {"low": 4, "medium": 4, "high": 2}),
        "complaint_tendency": pick(rng, {"low": 50, "medium": 35, "high": 15}),
        "patience": pick(rng, {"low": 25, "medium": 50, "high": 25}), "forgiveness": pick(rng, {"low": 25, "medium": 50, "high": 25})})

def trips_for(c, rng, k):
    s = SPEC[c["segment"]]; home = rng.choice(s["home"])
    other = {"PHL": "MCO", "MCO": "PHL"}.get(home, "MCO")
    dest = rng.choice(s["dest"]) if s["dest"] else other
    if c["segment"] == "S-home":   # students study in one base and go home elsewhere
        dest = rng.choice({"MCO": ["PHL", "BOS", "PIT"], "PHL": ["MCO", "TPA", "RSW"]}[home])
    n = rng.randint(*s["nights"]); w = c["window"]
    if w == "strike":
        out = dt.date(2026, 12, rng.choice([22, 23]))
        if home not in BASES and dest not in BASES: dest = "MCO"
    elif w == "holiday":
        out = rng.choice([dt.date(2026, 12, 24), dt.date(2026, 12, 26), dt.date(2026, 12, 27), dt.date(2026, 12, 28), dt.date(2026, 12, 30), dt.date(2027, 1, 2)])
    elif w == "thanksgiving":
        out = dt.date(2026, 11, rng.choice([24, 25])); n = min(n, (dt.date(2026, 11, 30) - out).days)
    else:
        wk = ORD_WEEKS[k % len(ORD_WEEKS)]
        out = D0 + dt.timedelta(days=7 * (wk - 1) + rng.choice([1, 3, 4]))
        if wk <= 7: n = min(n, (dt.date(2026, 12, 20) - out).days)
    legs = [{"date": out.isoformat(), "week": week(out), "from": home, "to": dest}]
    back = out + dt.timedelta(days=max(1, n))
    if c["window"] == "strike" and back <= dt.date(2026, 12, 27): back = dt.date(2026, 12, 29)
    if back <= dt.date(2027, 1, 10) and not (c["window"] != "strike" and back in (dt.date(2026, 12, 22), dt.date(2026, 12, 23))):
        legs.append({"date": back.isoformat(), "week": week(back), "from": dest, "to": home})
    return home, legs

SCHEMA = {"type": "OBJECT", "properties": {
  "name": {"type": "STRING"}, "occupation": {"type": "STRING"},
  "employment_status": {"type": "STRING", "enum": ["full-time", "part-time", "gig", "self-employed", "retired", "student", "not working"]},
  "household": {"type": "STRING"}, "household_income_band": {"type": "STRING", "enum": ["<$25k", "$25-50k", "$50-75k", "$75-100k", "$100-150k", "$150k+"]},
  "travel_party": {"type": "STRING"}, "trip_reason": {"type": "STRING"},
  "airport_assistance": {"type": "STRING", "enum": ["none", "wheelchair", "unaccompanied minor", "other"]},
  "checks_bags": {"type": "STRING"},
  "flexibility_reason": {"type": "STRING"}, "who_pays": {"type": "STRING"},
  "news_sources": {"type": "ARRAY", "items": {"type": "STRING"}},
  "values_most": {"type": "STRING"}, "past_kestrel_experience": {"type": "STRING"},
  "reaction_to_disruption": {"type": "STRING"}, "narrative": {"type": "STRING"}},
 "required": ["name", "occupation", "employment_status", "household", "household_income_band", "travel_party", "trip_reason",
              "airport_assistance", "checks_bags", "flexibility_reason",
              "who_pays", "news_sources",
              "values_most", "past_kestrel_experience", "reaction_to_disruption", "narrative"]}

def prompt_for(p):
    legs = "\n".join(f"  - {l['date']} (week {l['week']}): {CITY.get(l['from'], l['from'])} ({l['from']}) -> {CITY.get(l['to'], l['to'])} ({l['to']})" for l in p["trips"])
    return f"""You are building ONE representative customer persona for a simulation of Kestrel Air, a fictional US low-cost airline
(bases Orlando MCO and Philadelphia PHL; 75% US domestic, 25% Mexico/Caribbean; price-conscious customers who often also fly other airlines).

This persona stands for a whole cluster of customers, so make them TYPICAL of the cluster, not extreme or quirky.
Cluster: {p['segment_description']} ({p['group']}).
Travel window: {p['window']} ({p['represents_trips']:,} passenger trips over the 10 weeks are like this person).
Fixed facts you must keep:
- Name {p['name']} (keep exactly). Age {p['age']}, {p['gender']}, lives in {p['home_area']}.
- Travels with: {p['party_hint']}.
- Behaviour (keep consistent): date flexibility {p['date_flexibility']}; knows refund rights: {p['knows_refund_rights']}; money pressure {p['money_pressure']};
  loyalty tier {p['loyalty_tier']}; also flies other airlines: {"yes" if p['also_flies_rivals'] else "no"}; books via {p['booking_channel']};
  social media activity {p['social_media_activity']}; tendency to complain {p['complaint_tendency']}; patience {p['patience']}; forgiveness {p['forgiveness']}.
- Booked Kestrel flights:
{legs}

Fill in the rest so it is realistic for this cluster in late 2026 (US, price-conscious low-cost-airline customer).
Rules: do NOT state or imply race, ethnicity, religion, political views or immigration status;
no health details except airport assistance when the cluster requires it; no stereotypes. Keep income realistic for a low-cost-airline customer.
"narrative": 3-4 concrete sentences in third person: who they are, why this trip matters, why they fly Kestrel.
"past_kestrel_experience": one sentence. "reaction_to_disruption": one sentence on what they typically do when a flight goes wrong."""

def main():
    data = json.loads((OUT / "clusters.json").read_text(encoding="utf-8"))
    rng = random.Random(SEED); personas = []
    for k, c in enumerate(data["clusters"]):
        s = SPEC[c["segment"]]; home, legs = trips_for(c, rng, k)
        personas.append({"id": f"{c['segment']}-{c['window']}", "group": c["group"], "cluster": c["cluster"], "segment": c["segment"],
                         "segment_description": c["segment_description"], "window": c["window"], "represents_trips": c["represents_trips"],
                         "share_pct": c["share_pct"], "age": rng.randint(*s["age"]), "gender": rng.choice(["woman", "man"]),
                         "home_area": CITY[home], "party_hint": s["party"], "trips": legs,
                         "strike_exposed": any(l["date"] in ("2026-12-22", "2026-12-23") and (l["from"] in BASES or l["to"] in BASES) for l in legs),
                         "international": any(l["from"] in INTL or l["to"] in INTL for l in legs)})
    used = set()
    for p in personas: p["name"] = assign_name(rng, p["age"], p["gender"], used); assign_traits(p, rng)
    def work(p):
        pr = prompt_for(p); resp = generate(pr, model=MODEL, seed=SEED + personas.index(p), temperature=0.9, schema=SCHEMA)
        return p, pr, resp
    calls = []
    with cf.ThreadPoolExecutor(16) as ex:
        for p, pr, resp in ex.map(work, personas):
            g = json.loads(resp); g["name"] = p["name"]; p.update(g); calls.append({"persona": p["id"], "model": MODEL, "seed": SEED + personas.index(p), "prompt": pr, "response": resp})
    names = [p["name"] for p in personas]
    dup = {n for n in names if names.count(n) > 1}
    with open(OUT / "personas.jsonl", "w", encoding="utf-8") as f:
        for p in personas: f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(OUT / "gen_calls.jsonl", "w", encoding="utf-8") as f:
        for c in calls: f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(personas)} personas written; duplicate names: {sorted(dup) or 'none'}; strike-exposed: {sum(p['strike_exposed'] for p in personas)}; international: {sum(p['international'] for p in personas)}")

if __name__ == "__main__":
    main()
