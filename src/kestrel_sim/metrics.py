"""Turn persona behaviour into the board's goals (dossier "What the board wants by January 10").

Weights: each persona stands for `weight` passenger trips over the ten weeks; each of its booked legs
stands for weight / number of legs. Absolute LLM levels (NPS, complaint rates) are not trusted; we
calibrate them to the dossier's November 2 baseline (NPS +12, about 2,500 complaints a month) and
report the change the simulation produces.

goal_1   % of planned flights operated over the ten weeks, strike days excluded (network model)
goal_2   % of passengers on disrupted flights rebooked or refunded within 24 hours
goal_3   NPS at week 10, calibrated: +12 + (simulated NPS week 10 - simulated NPS week 1)
goal_3b  complaints per month in December (weeks 5-9), calibrated to 2,500 for weeks 1-3
goal_4   revenue weeks 5-10, % of plan (legs kept vs booked, minus revenue-reducing actions)
"""
from collections import defaultdict

from . import config, decisions as dec, world

BASELINE_NPS = 12
BASELINE_COMPLAINTS = 2500
COMPLAINT_PRIOR = 0.003  # weighted complaints per persona-week in ordinary weeks, pooled from test runs (assumption)
PLAN_REVENUE_W5_10 = 6 * 210_000 * (0.75 * 120 + 0.25 * 210)  # dossier: ~$180M
REVENUE_ACTIONS = {"fare_cap": 500_000, "fare_sale": 300_000}


def _nps(rows, weights):
    tot = sum(weights[r["persona"]] for r in rows if isinstance(r.get("nps"), (int, float)))
    if not tot:
        return None
    pro = sum(weights[r["persona"]] for r in rows if isinstance(r.get("nps"), (int, float)) and r["nps"] >= 9)
    det = sum(weights[r["persona"]] for r in rows if isinstance(r.get("nps"), (int, float)) and r["nps"] <= 6)
    return 100 * (pro - det) / tot


def compute(run):
    personas = {p["id"]: p for p in run.personas}
    w = {pid: p["weight"] for pid, p in personas.items()}
    leg_w = {pid: p["weight"] / max(1, len(p["trips"])) for pid, p in personas.items()}
    by_week = defaultdict(list)
    for r in run.weekly_rows:
        by_week[r["week"]].append(r)
    final_status = {r["persona"]: r["status"] for r in run.weekly_rows if r["week"] == max(by_week)}

    # goal 1: network model (world.py), strike days excluded
    g1 = world.network_operated_pct(run.effects_by_week, run.surprises)

    # goal 2: disrupted legs resolved within 24 hours
    status_at = {(r["persona"], r["week"]): r["status"] for r in run.weekly_rows}
    fast_refund_channel = lambda p: str(p.get("booking_channel") or p.get("shared", {}).get("preferred_channel", "")).lower() != "phone"
    num = den = 0.0
    for o in run.outcomes:
        if not o["disrupted"]:
            continue
        p, s = personas[o["persona"]], status_at[(o["persona"], o["week"])]
        lw = leg_w[o["persona"]]
        den += lw
        if s in ("flies as planned", "rebooked"):
            num += lw if o.get("within_24h") else 0
        else:  # refunded: within 24h if support is reachable fast or they use the app/web
            num += lw if (o.get("phone_wait", 999) <= 30 or fast_refund_channel(p)) else 0
    g2 = round(100 * num / den, 1) if den else None

    # goal 3: NPS and complaints, calibrated to the dossier baseline
    nps_w1, nps_last = _nps(by_week[1], w), _nps(by_week[max(by_week)], w)
    g3 = round(BASELINE_NPS + (nps_last - nps_w1), 1) if nps_w1 is not None and nps_last is not None else None
    def complaint_rate(weeks, prior=None):
        rows = [r for wk in weeks for r in by_week.get(wk, [])]
        c = sum(w[r["persona"]] for r in rows if r["complained"])
        t = sum(w[r["persona"]] for r in rows)
        if prior is None:
            return c / t if t else 0.0
        return (c + prior * t) / (2 * t) if t else prior  # shrink halfway to the prior
    # Weeks 1-3 hold almost no complaints in a few dozen personas, so the baseline is shrunk towards a
    # prior of 0.3% (weighted) per persona-week; without it goal_3b swung from about 1,000 to 6,800 between seeds.
    base_rate = complaint_rate([1, 2, 3], prior=COMPLAINT_PRIOR)
    dec_rate = complaint_rate([5, 6, 7, 8, 9])
    g3b = round(BASELINE_COMPLAINTS * dec_rate / base_rate)

    # goal 4: revenue weeks 5-10
    booked = kept = 0.0
    for pid, p in personas.items():
        lost = run.state[pid]["lost"]
        for i, t in enumerate(p["trips"]):
            if 5 <= t["week"] <= 10:
                v = world.fare(t) * leg_w[pid]
                booked += v
                kept += 0 if i in lost else v
    eff_cost = sum(c for key, c in REVENUE_ACTIONS.items() if any(key in run.effects_by_week[wk] for wk in range(5, 11)))
    g4 = round(100 * (kept / booked) - 100 * eff_cost / PLAN_REVENUE_W5_10, 2) if booked else None

    shares = defaultdict(float)
    for pid, s in final_status.items():
        shares[s] += w[pid]
    total_w = sum(w[pid] for pid in final_status) or 1
    again = defaultdict(float)
    for r in by_week[max(by_week)]:
        again[r["book_again"]] += w[r["persona"]]
    return {
        "goal_1": g1, "goal_2": g2, "goal_3": g3, "goal_3b": g3b, "goal_4": g4,
        "units": {
            "goal_1": "% of planned flights operated over weeks 1-10, strike days Dec 22-23 excluded (network model)",
            "goal_2": "% of passengers on canceled or 3h+ delayed flights rebooked or refunded within 24 hours (trip-weighted)",
            "goal_3": "NPS at week 10, calibrated: dossier +12 plus the simulated change from week 1",
            "goal_3b": "complaints per month in December (weeks 5-9), calibrated to 2,500/month for weeks 1-3 (baseline shrunk to a 0.3%/persona-week prior)",
            "goal_4": "% of planned revenue for weeks 5-10 (kept bookings, minus fare cap/sale lost revenue)",
        },
        "decisions_cost_usd": dec.total_cost(run.decisions),
        "budget_usd": dec.BUDGET,
        "detail": {
            "nps_simulated_week1": round(nps_w1, 1) if nps_w1 is not None else None,
            "nps_simulated_last_week": round(nps_last, 1) if nps_last is not None else None,
            "complaint_rate_weeks_1_3": round(base_rate, 4), "complaint_rate_weeks_5_9": round(dec_rate, 4),
            "final_status_share_pct": {k: round(100 * v / total_w, 1) for k, v in shares.items()},
            "book_again_share_pct": {str(k): round(100 * v / total_w, 1) for k, v in again.items()},
            "disrupted_legs": sum(1 for o in run.outcomes if o["disrupted"]),
            "strike_legs": sum(1 for o in run.outcomes if o["strike"]),
            "personas": len(personas), "weeks": max(by_week),
        },
    }
