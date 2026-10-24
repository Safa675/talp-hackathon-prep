"""Hard-test report for finished runs: posting, conversation, status consistency, metrics.

    python exp_hard/analyze.py hard_base_none hard_base_plan
"""
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ps = {json.loads(l)["id"]: json.loads(l) for l in open(HERE / "personas_66.jsonl", encoding="utf-8")}
W = {k: p["represents_trips"] for k, p in ps.items()}
FIRST = {k: p["name"].split()[0] for k, p in ps.items()}
LEFT = ("moved to another airline", "canceled the trip")


def report(name):
    d = HERE / "runs" / name
    rows = [json.loads(l) for l in open(d / "weekly.jsonl", encoding="utf-8")]
    calls = {json.loads(l)["id"]: json.loads(l) for l in open(d / "calls.jsonl", encoding="utf-8")}
    m = json.load(open(d / "metrics.json"))
    by = {(r["persona"], r["week"]): r for r in rows}
    posts = [r for r in rows if r.get("post")]
    print(f"\n===== {name}  ({len(rows)} persona-weeks)")
    print("  goals:", {k: m.get(k) for k in ("goal_1", "goal_2", "goal_3", "goal_3b", "goal_4")})
    # --- posting
    per_week = [sum(1 for r in posts if r["week"] == w) for w in range(1, 11)]
    ever = len({r["persona"] for r in posts})
    act = collections.Counter(ps[r["persona"]]["social_media_activity"] for r in posts)
    act_n = collections.Counter(p["social_media_activity"] for p in ps.values())
    print(f"  posts: {len(posts)} ({100*len(posts)/len(rows):.0f}% of persona-weeks) | per week {per_week} | personas who ever posted {ever}/66")
    print("  post rate by social_media_activity:", {a: f"{100*act[a]/(act_n[a]*10):.0f}%" for a in ("low", "medium", "high")})
    # --- conversation: replies naming another persona, and reactions to the feed
    names = {v.lower(): k for k, v in FIRST.items()}
    replies = [r for r in posts if any(re.search(rf"\b{n}\b", r["post"].lower()) for n, k in names.items() if k != r["persona"] and len(n) > 3)]
    fed = [r for r in rows if r.get("feed")]
    def refers(r):
        t = (r.get("said", "") + " " + r.get("action", "") + " " + r.get("post", "")).lower()
        return any(x in t for x in ("post", "online", "social media", "tiktok", "people are saying", "saw ", "read ", "heard", "friend", "others"))
    print(f"  conversation: persona-weeks with a feed {len(fed)} | reply refers to feed/social {sum(refers(r) for r in fed)} | posts naming another persona {len(replies)}")
    for r in replies[:2]:
        print(f"    reply e.g. {r['persona']} w{r['week']}: {r['post'][:160]}")
    # --- status consistency
    flips = [(p, w) for (p, w), r in by.items() if w > 1 and by[(p, w - 1)]["status"] in LEFT and r["status"] == "flies as planned"]
    reb = [(p, w) for (p, w), r in by.items() if r["status"] == "rebooked" and r["flight_outcome"] in ("none", "on time")
           and by.get((p, w - 1), {}).get("status") != "rebooked"]
    after = [(p, w) for (p, w), r in by.items() if w > max(t["week"] for t in ps[p]["trips"]) and r["status"] in LEFT
             and by.get((p, w - 1), {}).get("status") not in LEFT]
    print(f"  status: back-to-Kestrel after leaving {len(flips)} | 'rebooked' without disruption {len(reb)} {reb[:3]} | left after last trip {len(after)} {after[:3]}")
    # --- trust and complaints by week (weighted)
    tr = []
    for w in range(1, 11):
        rs = [r for r in rows if r["week"] == w and isinstance(r.get("trust"), int)]
        tr.append(round(sum(W[r["persona"]] * r["trust"] for r in rs) / max(sum(W[r["persona"]] for r in rs), 1), 2))
    print("  trust w1..10:", tr)
    print("  complaints/week:", [sum(bool(r.get("complaint")) for r in rows if r["week"] == w) for w in range(1, 11)])
    sd = [r for r in rows if r.get("strike_day")]
    print("  strike-day flights:", dict(collections.Counter(r["flight_outcome"] for r in sd)), "| W8 statuses:", dict(collections.Counter(r["status"] for r in rows if r["week"] == 8)))
    # --- probe consistency (reversed items)
    pf = d / "probe.jsonl"
    if pf.exists():
        pr = [json.loads(l) for l in open(pf, encoding="utf-8")]
        sc = collections.defaultdict(dict)
        for x in pr:
            sc[(x["persona"], x["when"])][x["question"]] = x["score"]
        gaps = []
        for s in sc.values():
            if len(s) == 8:
                gaps.append(max(abs(s["1a"] - s["1b"]), abs(s["2a"] - (6 - s["2b"])), abs(s["3a"] - s["3b"]), abs(s["4a"] - (6 - s["4b"]))))
        print(f"  probe: {len(sc)} answer sets | reversed-item contradictions (gap>=2): {sum(g >= 2 for g in gaps)} | mean max gap {sum(gaps)/max(len(gaps),1):.2f}")
        nps = lambda when: round(100 * (sum(s.get('3a') == 5 for (p, wh), s in sc.items() if wh == when) - sum(s.get('3a', 9) <= 3 for (p, wh), s in sc.items() if wh == when)) / 66, 1)
        print(f"  raw probe NPS start {nps('start')} -> end {nps('end')}")
    # --- prompt sanity: does any week prompt mention an event before its week?
    early = [c for c in calls.values() if c.get("persona") and c["week"] in (1, 2, 3, 4, 5, 6) and ("ground handling contractor's workers" in c["prompt"] and "strike" in c["prompt"].lower() and "Dec 22" in c["prompt"] and "48-hour" in c["prompt"])]
    print(f"  strike text in prompts before week 8: {len(early)}")


for n in sys.argv[1:]:
    report(n)
