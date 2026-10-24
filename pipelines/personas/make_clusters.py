"""Kestrel customer base -> clusters -> one representative persona per cluster.
Step 1  segments (group x sub-type) with passenger shares: NHTS 2022 air-trip purpose mix, adjusted for a low-cost carrier.
Step 2  travel window per segment (strike days at a base / holiday after / Thanksgiving / ordinary weeks).
Step 3  raking (IPF) so the segment x window table matches BOTH margins: segment shares and the calendar from the dossier.
Each non-empty cell = one cluster = one persona; its weight = passenger trips it stands for over the 10 weeks.
"""
import json

# --- calendar margin (dossier + stated assumptions) -------------------------------------------
ORD = 7 * 210_000                      # weeks 1-3, 5-7, 10 at 210k/week (dossier)
THX = 230_000                          # week 4 Thanksgiving: assumption (+10%)
W8 = round(210_000 * 97 / 86)          # week 8: 97% booked vs 86% normal (dossier) -> ~237k
W9 = 230_000                           # week 9 New Year: assumption
STRIKE = round(W8 * 2 / 7 * 0.60)      # Dec 22-23 = 2 of 7 days; 60% of flights touch a base (dossier) -> ~41k
WIN = {"strike": STRIKE, "holiday": W8 - STRIKE + W9, "thanksgiving": THX, "ordinary": ORD}
TOTAL = sum(WIN.values())

# --- segments: share of passenger trips, and prior weights for the 4 windows --------------------
# (group, key, description, share, [strike, holiday, thanksgiving, ordinary] prior)
SEG = [
 ("vacationers","V-park","Northeast/Midwest families on a Florida theme-park trip",.15,[2,20,10,68]),
 ("vacationers","V-beach","couples/friends to Mexico & Caribbean beaches (international)",.10,[1.5,15,10,73.5]),
 ("vacationers","V-snowbird","retirees escaping winter to Florida, long stays",.08,[1,10,5,84]),
 ("vacationers","V-budget","young deal-hunters on short trips",.07,[1,10,8,81]),
 ("families visiting relatives","F-grandkids","parents with young children visiting grandparents",.12,[5,30,20,45]),
 ("families visiting relatives","F-adultkids","adults flying alone or as a couple to see parents",.10,[5,25,20,50]),
 ("families visiting relatives","F-multigen","multi-generation trips with an elderly parent who needs airport help",.05,[5,30,20,45]),
 ("families visiting relatives","F-diaspora","families visiting relatives in Mexico/Caribbean (international)",.06,[4,35,10,51]),
 ("families visiting relatives","F-minor","children flying alone between separated parents",.02,[6,35,20,39]),
 ("students","S-home","college students flying home for the holidays",.07,[6,25,30,39]),
 ("students","S-trip","students on group trips abroad",.03,[2,40,5,53]),
 ("business travelers","B-corp","corporate road warriors, employer pays",.04,[.5,3,1,95.5]),
 ("business travelers","B-smb","small-business owners paying their own way",.04,[.5,5,2,92.5]),
 ("business travelers","B-contract","contract/shift workers relocating (travel nurses, construction)",.02,[1,10,5,84]),
 ("travel agencies","A-senior","agencies booking senior leisure groups",.02,[3,20,10,67]),
 ("travel agencies","A-event","agencies booking wedding/event groups abroad",.015,[3,25,10,62]),
 ("travel agencies","A-corp","agencies booking corporate/conference groups",.015,[0,2,0,98]),
]
WK = ["strike","holiday","thanksgiving","ordinary"]

# --- raking (iterative proportional fitting) -----------------------------------------------------
M = [[s * p / sum(pr) for p in pr] for (_, _, _, s, pr) in SEG]
row_t = [s for (_, _, _, s, _) in SEG]
col_t = [WIN[w] / TOTAL for w in WK]
for _ in range(200):
    for i, r in enumerate(M):
        f = row_t[i] / sum(r); M[i] = [x * f for x in r]
    for j in range(4):
        c = sum(M[i][j] for i in range(len(M)))
        f = col_t[j] / c if c else 0
        for i in range(len(M)): M[i][j] *= f

clusters = []
for i, (g, k, d, s, _) in enumerate(SEG):
    for j, w in enumerate(WK):
        share = M[i][j]
        if share <= 0: continue
        clusters.append({"cluster": f"{k}:{w}", "group": g, "segment": k, "segment_description": d, "window": w,
                         "share_pct": round(100 * share, 3), "represents_trips": round(share * TOTAL)})
json.dump({"total_trips_10_weeks": TOTAL, "windows": WIN, "clusters": clusters},
          open("clusters.json", "w"), ensure_ascii=False, indent=1)

print(f"total trips over 10 weeks ~{TOTAL:,}  | windows: " + ", ".join(f"{w} {WIN[w]:,}" for w in WK))
print(f"clusters: {len(clusters)}")
print(f"\n{'segment':12s} {'share':>6s} | {'strike':>8s} {'holiday':>8s} {'thanksg':>8s} {'ordinary':>9s}   (passenger trips)")
for i, (g, k, d, s, _) in enumerate(SEG):
    print(f"{k:12s} {100*s:5.1f}% | " + " ".join(f"{M[i][j]*TOTAL:8,.0f}" if M[i][j] > 0 else f"{'-':>8s}" for j in range(4)))
import collections
print("\nclusters per group:", dict(collections.Counter(c["group"] for c in clusters)))
