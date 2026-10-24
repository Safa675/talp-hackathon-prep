"""(Superseded by make_clusters.py + gen_personas.py; kept for reference.)
30-persona skeleton for Kestrel Air (fixed fields only; narratives come later from the LLM).
Grounding: dossier (bases, routes 75/25, week-8 load, groups) + NHTS 2022 air-trip profile (purpose, party size,
children, age), income shifted down for a low-cost carrier. Strike-exposed passengers are oversampled (12/30)
and corrected with weights in the metrics."""
import json
from pathlib import Path
OUT = Path(__file__).resolve().parents[2] / "data" / "personas" / "clusters"   # outputs live with the data

W = {"2026-11-03":1,"2026-11-04":1,"2026-11-06":1,"2026-11-10":2,"2026-11-11":2,"2026-11-12":2,"2026-11-17":3,"2026-11-18":3,"2026-11-20":3,
     "2026-11-25":4,"2026-11-29":4,"2026-12-01":5,"2026-12-02":5,"2026-12-08":6,"2026-12-09":6,"2026-12-10":6,"2026-12-11":6,
     "2026-12-14":7,"2026-12-16":7,"2026-12-18":7,"2026-12-19":7,"2026-12-20":7,"2026-12-22":8,"2026-12-23":8,"2026-12-24":8,
     "2026-12-26":8,"2026-12-27":8,"2026-12-28":9,"2026-12-29":9,"2026-12-30":9,"2026-12-31":9,"2027-01-02":9,"2027-01-03":9,
     "2027-01-05":10,"2027-01-06":10,"2027-01-07":10,"2027-01-08":10,"2027-01-09":10,"2027-01-10":10}
def legs(*ls): return [{"date": d, "week": W[d], "from": a, "to": b} for d, a, b in ls]
STRIKE = {"2026-12-22", "2026-12-23"}; BASES = {"PHL", "MCO"}

P = [
 # id, group, name, age, occupation, home, party, assistance, bags, flexibility, rights, money, payer, loyalty, rival, channel, news, social, complain, patience, income, legs
 ("V1","vacationers","Linda Kowalski",68,"retired bookkeeper","Philadelphia, PA","with husband Ray (70)","wheelchair for Ray","2 checked","some","no","medium","self","member",False,"phone","family group chat, local TV news","low","low","high","$50-75k",legs(("2026-12-22","PHL","MCO"),("2027-01-05","MCO","PHL"))),
 ("V2","vacationers","Marisol Vega",34,"dental hygienist","Orlando, FL","with partner","none","carry-on","fixed (prepaid all-inclusive)","partly","medium","self","none",True,"app","Instagram, TikTok","high","medium","low","$75-100k",legs(("2026-12-23","MCO","CUN"),("2026-12-30","CUN","MCO"))),
 ("V3","vacationers","Tyler Brooks",29,"remote QA engineer","Boston, MA","alone","none","carry-on","flexible","yes","low","self","none",True,"web","Reddit, YouTube","medium","high","medium","$75-100k",legs(("2026-12-10","BOS","SJU"),("2026-12-14","SJU","BOS"))),
 ("V4","vacationers","Derek Miller",41,"HVAC technician","Columbus, OH","with wife and kids (7, 10)","none","3 checked","fixed (school break)","no","high","self","none",True,"web","Facebook, coworkers","medium","medium","medium","$50-75k",legs(("2026-12-28","CMH","MCO"),("2027-01-02","MCO","CMH"))),
 ("V5","vacationers","Gloria Hensley",61,"school administrator","Philadelphia, PA","with her sister","none","1 checked","fixed","no","low","self","member",False,"email","local TV news, Facebook","low","low","medium","$75-100k",legs(("2026-11-25","PHL","PUJ"),("2026-11-29","PUJ","PHL"))),
 ("V6","vacationers","Kevin O'Hara",52,"self-employed contractor","Philadelphia, PA","with 3 friends (golf trip)","none","golf bag checked","flexible","yes","low","self","none",True,"app","X, sports radio","high","high","low","$100-125k",legs(("2026-12-16","PHL","TPA"),("2026-12-20","TPA","PHL"))),
 ("V7","vacationers","Brianna Scott",26,"ER nurse (shift work)","Orlando, FL","with a friend","none","carry-on","fixed (shift schedule)","no","high","self","none",True,"app","TikTok, Instagram","high","medium","low","$50-75k",legs(("2026-12-26","MCO","SJU"),("2026-12-31","SJU","MCO"))),
 ("V8","vacationers","Harold Whitfield",74,"retired steelworker","Pittsburgh, PA","with wife June (72)","none","2 checked","flexible","no","low","self","gold",False,"phone","cable news, neighbors","low","low","high","$35-50k",legs(("2027-01-06","PIT","TPA"))),
 ("F1","families visiting relatives","Angela Rossi",38,"medical receptionist (single mother)","Philadelphia, PA","with kids (4, 8)","none","2 checked + car seat","fixed (Christmas)","no","high","self","none",False,"app","Facebook, family group chat","medium","medium","low","$35-50k",legs(("2026-12-22","PHL","MCO"),("2026-12-29","MCO","PHL"))),
 ("F2","families visiting relatives","Carlos Mendoza",45,"bus mechanic","Orlando, FL","wife, 3 kids, mother-in-law (78)","wheelchair for mother-in-law","4 checked","fixed (Christmas)","partly","high","self","member",False,"app","family group chat, local TV news","medium","medium","medium","$50-75k",legs(("2026-12-23","MCO","PHL"),("2027-01-02","PHL","MCO"))),
 ("F3","families visiting relatives","Danielle Carter",31,"middle-school teacher","Orlando, FL","alone","none","carry-on","some (on school break)","yes","medium","self","none",True,"app","Instagram, coworkers","medium","low","high","$50-75k",legs(("2026-12-22","MCO","PHL"),("2026-12-27","PHL","MCO"))),
 ("F4","families visiting relatives","Rachel Thompson",40,"hospital nurse (books for daughter Maya, 11)","Philadelphia, PA","daughter flies alone","unaccompanied minor service","1 checked","fixed (custody schedule)","partly","medium","self","none",False,"text","Facebook, X","high","high","low","$75-100k",legs(("2026-12-23","PHL","MCO"),("2027-01-03","MCO","PHL"))),
 ("F5","families visiting relatives","Robert Johnson",58,"warehouse supervisor","Charlotte, NC","with wife","none","1 checked","fixed (Thanksgiving)","no","medium","self","gold",False,"email","local TV news, church friends","low","low","high","$50-75k",legs(("2026-11-25","CLT","FLL"),("2026-11-29","FLL","CLT"))),
 ("F6","families visiting relatives","Luis Ortega",47,"auto mechanic","Philadelphia, PA","wife and 2 teens","none","4 checked (gifts)","fixed","no","high","self","none",True,"app","WhatsApp family chat, YouTube","medium","medium","medium","$35-50k",legs(("2026-12-19","PHL","SDQ"),("2027-01-03","SDQ","PHL"))),
 ("F7","families visiting relatives","Patricia Lee",66,"retired librarian","Orlando, FL","alone (to grandchildren)","wheelchair (knee surgery)","1 checked","fixed (Christmas Eve)","no","low","self","member",False,"email","Facebook, family group chat","low","low","high","$50-75k",legs(("2026-12-24","MCO","DTW"),("2027-01-07","DTW","MCO"))),
 ("F8","families visiting relatives","Tasha Green",32,"remote customer-success manager","Orlando, FL","husband, toddler (3), baby (1)","none","3 checked + stroller","some","partly","medium","self","none",True,"app","Instagram, parenting groups","medium","medium","low","$75-100k",legs(("2026-12-19","MCO","PHL"),("2027-01-02","PHL","MCO"))),
 ("S1","students","Jordan Reyes",20,"college student (UCF)","Orlando, FL","alone","none","carry-on","some","no","high","parents","none",True,"app","TikTok, X","high","medium","low","parents $50-75k",legs(("2026-12-22","MCO","PHL"),("2027-01-09","PHL","MCO"))),
 ("S2","students","Hannah Schultz",19,"college student (Temple), part-time barista","Philadelphia, PA","alone","none","1 checked","fixed","no","high","self","none",False,"app","Instagram, friends","medium","low","medium","own <$15k",legs(("2026-12-23","PHL","MCO"),("2027-01-10","MCO","PHL"))),
 ("S3","students","Devin Clarke",23,"law student","Philadelphia, PA","alone","none","carry-on","some","yes","medium","self","none",True,"web","X, Reddit (5k followers)","high","high","medium","own <$25k",legs(("2026-12-22","PHL","RSW"),("2027-01-06","RSW","PHL"))),
 ("S4","students","Sofia Marino",21,"college student (UCF)","Orlando, FL","with 4 friends","none","carry-on","fixed (prepaid hotel)","no","high","self","none",True,"app","TikTok, group chat","high","medium","low","own <$25k",legs(("2026-12-29","MCO","CUN"),("2027-01-03","CUN","MCO"))),
 ("S5","students","Ethan Walsh",18,"college freshman (Drexel)","Philadelphia, PA","alone","none","1 checked","some","no","low","parents","none",False,"email","Instagram, parents","medium","low","medium","parents $100-125k",legs(("2026-11-25","PHL","MCO"),("2026-11-29","MCO","PHL"),("2026-12-18","PHL","MCO"),("2027-01-09","MCO","PHL"))),
 ("B1","business travelers","Michael Torres",44,"medical-device sales rep","Philadelphia, PA","alone","none","carry-on","fixed (client meetings)","yes","low","employer","gold",True,"app","LinkedIn, podcasts","medium","medium","medium","$100-125k",legs(("2026-11-04","PHL","MCO"),("2026-11-06","MCO","PHL"),("2026-11-18","PHL","MCO"),("2026-11-20","MCO","PHL"),("2026-12-22","PHL","MCO"),("2026-12-27","MCO","PHL"),("2027-01-07","PHL","MCO"),("2027-01-08","MCO","PHL"))),
 ("B2","business travelers","Sarah Kim",37,"event-planning business owner","Orlando, FL","alone","none","1 checked","some","partly","medium","self (business)","none",True,"web","Instagram, local business groups","medium","medium","medium","$75-100k",legs(("2026-11-10","MCO","PHL"),("2026-11-12","PHL","MCO"),("2026-12-09","MCO","PHL"),("2026-12-11","PHL","MCO"))),
 ("B3","business travelers","Greg Hansen",55,"engineer, government contractor","Atlanta, GA","alone","none","carry-on","fixed","yes","low","employer (cheapest-fare policy)","member",True,"email","cable news, coworkers","low","low","high","$100-125k",legs(("2026-11-17","ATL","SJU"),("2026-11-20","SJU","ATL"),("2027-01-05","ATL","SJU"),("2027-01-08","SJU","ATL"))),
 ("B4","business travelers","Lauren Price",29,"travel nurse (contract)","Philadelphia, PA","alone","none","2 checked","fixed (contract start)","partly","medium","employer reimburses","none",True,"app","TikTok, nurse forums","high","medium","medium","$75-100k",legs(("2026-12-01","PHL","MCO"),("2027-01-08","MCO","PHL"))),
 ("B5","business travelers","Tom Becker",49,"construction project manager","Orlando, FL","alone","none","tool case checked","fixed","yes","low","employer","member",True,"app","X, coworkers","medium","high","low","$100-125k",legs(("2026-11-03","MCO","CUN"),("2026-11-06","CUN","MCO"),("2026-12-08","MCO","CUN"),("2026-12-11","CUN","MCO"))),
 ("A1","travel agencies","Debbie Alvarez (Sunshine Group Tours)",57,"group-tour agency owner; 32 seniors","Philadelphia, PA","group of 32 seniors","wheelchairs for 5 travelers","32 checked","fixed (hotel block)","yes","medium","clients","group desk",False,"phone","email, industry newsletters","low","medium","medium","agency",legs(("2026-12-22","PHL","MCO"),("2026-12-28","MCO","PHL"))),
 ("A2","travel agencies","Kyle Morgan (Vow Voyages)",32,"destination-wedding planner; 25 guests","Philadelphia, PA","wedding party of 25 (wedding Dec 26)","none","25 checked","fixed (wedding)","yes","medium","clients","group desk",True,"email","Instagram, WhatsApp","high","high","low","agency",legs(("2026-12-23","PHL","PUJ"),("2026-12-28","PUJ","PHL"))),
 ("A3","travel agencies","Brenda Cole (Keystone Business Travel)",49,"corporate travel agent; groups of 10","Philadelphia, PA","conference groups of 10","none","carry-on","some","yes","medium","clients","corporate contract",True,"email","LinkedIn, industry newsletters","low","medium","medium","agency",legs(("2026-11-11","PHL","MCO"),("2026-12-02","PHL","MCO"),("2027-01-06","PHL","MCO"))),
 ("A4","travel agencies","Andre Baptiste (Island Hop Travel)",45,"family-travel agent; groups of 20","Orlando, FL","family groups of 20","none","20 checked","fixed (New Year)","yes","medium","clients","group desk",True,"phone","WhatsApp, Facebook","medium","medium","medium","agency",legs(("2026-12-30","MCO","MBJ"),("2027-01-06","MBJ","MCO"))),
]
KEYS = ["id","group","name","age","occupation","home","party","airport_assistance","bags","date_flexibility","knows_refund_rights",
        "money_pressure","who_pays","loyalty","also_flies_rivals","preferred_channel","news_sources","social_media_activity",
        "complaint_tendency","patience","income_band","trips"]
out = []
for row in P:
    p = dict(zip(KEYS, row))
    p["intl"] = any(l["to"] in {"CUN","PUJ","SDQ","MBJ"} or l["from"] in {"CUN","PUJ","SDQ","MBJ"} for l in p["trips"])
    p["touches_base"] = any(l["from"] in BASES or l["to"] in BASES for l in p["trips"])
    p["strike_exposed"] = any(l["date"] in STRIKE and (l["from"] in BASES or l["to"] in BASES) for l in p["trips"])
    p["stratum"] = ("strike" if p["strike_exposed"] else
                    "holiday-after-strike" if any(l["week"] in (8, 9) for l in p["trips"]) else
                    "thanksgiving" if any(l["week"] == 4 for l in p["trips"]) else "other")
    out.append(p)
with open(OUT / "personas_skeleton.jsonl", "w", encoding="utf-8") as f:
    for p in out: f.write(json.dumps(p, ensure_ascii=False) + "\n")
import collections
print("personas", len(out), "| groups", dict(collections.Counter(p["group"] for p in out)))
print("strata", dict(collections.Counter(p["stratum"] for p in out)), "| intl", sum(p["intl"] for p in out), "| touch base", sum(p["touches_base"] for p in out))
print("assistance", [p["id"] for p in out if p["airport_assistance"] != "none"])
