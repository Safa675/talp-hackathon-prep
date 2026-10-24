"""The operational world: what happens to each flight, and what Kestrel offers when it goes wrong.

Code decides events (cancellations, delays, offers, wait times); the model decides how people react.
Every number here is an assumption, listed in ASSUMPTIONS so TEAM_DOC can quote it.
Randomness is drawn from (run seed, persona, leg), so two seeds differ and a run is repeatable.
"""
import hashlib
import random

from . import config, crises

ASSUMPTIONS = {
    "ordinary_cancel": 0.012,          # dossier: goal 1 asks 98% operated; US low-cost norm ~1-2%
    "ordinary_delay_3h": 0.04,         # dossier: 79% on time; most delays are short
    "ordinary_delay_short": 0.17,
    "strike_cancel_bau": 0.30,         # contractor replacements "where it can" at 97% load
    "strike_cancel_backup": 0.07,
    "strike_delay_3h_bau": 0.45,
    "strike_delay_3h_backup": 0.15,
    "strike_bag_delay_bau": 0.50,
    "strike_bag_delay_backup": 0.12,
    "strike_wheelchair_wait_bau": "60-90 minutes",
    "strike_wheelchair_wait_backup": "about 15 minutes",
    "day_after_strike_cancel_bau": 0.06,   # Dec 24 knock-on (aircraft and crews out of position)
    "lease_cancel_factor": 0.5,            # spare aircraft halves cancellations in its two weeks
    "phone_wait_normal": 9,                # dossier
    "phone_wait_disruption_bau": 120,      # dossier: "much longer on disruption days"
    "phone_wait_disruption_staff": 20,
    "next_free_seat_days_peak": 3,         # week 8 97% booked (dossier): next free Kestrel seat ~Dec 26
    "next_free_seat_days_normal": 1,
    "merge_share": 0.03,                   # share of ordinary-week legs merged when that action is on
    "flights_per_week": 1355,              # 210k / (180 seats x 86%)
    "base_flight_share": 0.60,             # dossier
    "fare_domestic": 120, "fare_intl": 210,
}
INTL = {"CUN", "PUJ", "MBJ", "NAS", "SDQ", "GDL", "MEX", "SJU"}
A = ASSUMPTIONS


def rng_for(seed, *parts):
    h = hashlib.sha256("|".join(map(str, (seed,) + parts)).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def fare(leg):
    return A["fare_intl"] if {leg["from"], leg["to"]} & INTL else A["fare_domestic"]


def on_strike(leg):
    return leg["date"] in config.STRIKE_DATES and bool({leg["from"], leg["to"]} & config.BASES)


def leg_outcome(seed, persona, leg, effects, surprises, week):
    """What happens to one flight. Returns a dict the prompt and the metrics both use."""
    r = rng_for(seed, persona["id"], leg["date"], leg["from"], leg["to"])
    peak = week in (8, 9)
    lease = A["lease_cancel_factor"] if "lease_aircraft" in effects else 1.0
    out = {"leg": leg, "fare": fare(leg), "strike": on_strike(leg), "canceled": False, "delay": "none",
           "bags_delayed": False, "wheelchair_wait": None, "merged": False, "kestrel_caused": True,
           "causes": []}

    if out["strike"]:
        backup = "backup_ground" in effects
        p_cancel = (A["strike_cancel_backup"] if backup else A["strike_cancel_bau"]) * lease
        p_delay = A["strike_delay_3h_backup"] if backup else A["strike_delay_3h_bau"]
        p_bag = A["strike_bag_delay_backup"] if backup else A["strike_bag_delay_bau"]
        out["kestrel_caused"] = False  # contractor strike: BAU hotels/meals only for Kestrel-caused delays
        out["causes"].append("the ground handling strike")
        out["bags_delayed"] = r.random() < p_bag
        out["wheelchair_wait"] = A["strike_wheelchair_wait_backup" if backup else "strike_wheelchair_wait_bau"]
    else:
        p_cancel, p_delay = A["ordinary_cancel"] * lease, A["ordinary_delay_3h"]
        if leg["date"] == "2026-12-24" and {leg["from"], leg["to"]} & config.BASES and "backup_ground" not in effects:
            p_cancel += A["day_after_strike_cancel_bau"]
            out["causes"].append("knock-on delays from the strike")
        for s in crises.active(surprises, week):
            if crises.in_scope(s, leg):
                p_cancel += s.get("extra_cancel", 0) * lease
                p_delay += s.get("extra_delay", 0)
                out["causes"].append(s.get("title", "a disruption"))
                out["kestrel_caused"] = out["kestrel_caused"] and s.get("kestrel_caused", False)
        if "merge_flights" in effects and not peak and r.random() < A["merge_share"]:
            out["merged"] = True

    roll = r.random()
    if roll < p_cancel:
        out["canceled"] = True
    elif roll < p_cancel + p_delay:
        out["delay"] = "3+ hours"
    elif roll < p_cancel + p_delay + A["ordinary_delay_short"]:
        out["delay"] = "under an hour"
    out["disrupted"] = out["canceled"] or out["delay"] == "3+ hours"
    if out["disrupted"]:
        out.update(offer(out, effects, peak))
    return out


def offer(out, effects, peak):
    """What Kestrel offers a disrupted passenger, and whether it lands within 24 hours."""
    o = {"phone_wait": A["phone_wait_disruption_staff"] if "extra_staff" in effects else A["phone_wait_disruption_bau"]}
    if out["canceled"]:
        if "partner_rebooking" in effects:
            o["rebook"], o["within_24h"] = "a seat on a partner airline the same day, at no extra cost", True
        elif "lease_aircraft" in effects:
            o["rebook"], o["within_24h"] = "a seat on an extra Kestrel flight (leased aircraft) the next morning", True
        else:
            days = A["next_free_seat_days_peak"] if peak else A["next_free_seat_days_normal"]
            o["rebook"] = f"the next Kestrel flight with a free seat, {days} day{'s' if days > 1 else ''} later"
            o["within_24h"] = days <= 1
        overnight = not o["within_24h"] or "next morning" in o["rebook"]
    else:
        o["rebook"], o["within_24h"] = "your delayed flight, which still operates", True
        overnight = False
    hotel = "hotel_rooms" in effects or (out["kestrel_caused"] and overnight)
    o["hotel"] = "a hotel room is held for you" if hotel and overnight else (
        "no hotel is offered (the cause is not Kestrel's own)" if overnight else None)
    o["meal_voucher"] = out["kestrel_caused"] or "hotel_rooms" in effects
    if "goodwill" in effects:
        o["goodwill"] = "$50 cash" if effects["goodwill"] == "cash" else "a $75 Kestrel travel credit"
    if "double_points" in effects:
        o["points"] = "double loyalty points on this trip"
    o["refund"] = "a full refund to your original payment (DOT rules)"
    return o


def describe(o, persona):
    """Plain-language description of one flight outcome for the persona's prompt."""
    leg = o["leg"]
    head = f"Your Kestrel flight {leg['from']}-{leg['to']} on {leg['date']}"
    if o["merged"]:
        return (f"{head} was merged with another flight, announced 7 days ahead; you were moved to a flight "
                f"a few hours earlier on the same day.")
    why = f" because of {', '.join(o['causes'])}" if o["causes"] else ""
    if o["canceled"]:
        text = f"{head} was CANCELED{why}. Kestrel offers {o['rebook']}, or {o['refund']}."
    elif o["delay"] == "3+ hours":
        text = f"{head} was delayed more than 3 hours{why}."
    elif o["delay"] == "under an hour":
        text = f"{head} left a little late (under an hour), as often happens."
    else:
        text = f"{head} operated on time."
    if o.get("phone_wait"):
        text += f" The phone wait for Kestrel support is about {o['phone_wait']} minutes; the app also works."
    if o.get("hotel"):
        text += f" Overnight: {o['hotel']}."
    if o["disrupted"]:
        text += " Meal vouchers are given." if o.get("meal_voucher") else " No meal vouchers are given."
    for k in ("goodwill", "points"):
        if o.get(k):
            text += f" Kestrel also gives you {o[k]}."
    if o["bags_delayed"]:
        text += " Your checked bags did not arrive with you; Kestrel says they will be delivered in 1-2 days."
    needs_help = str(persona.get("airport_assistance") or (persona.get("trip") or {}).get("assistance") or "none")
    if o["wheelchair_wait"] and needs_help.lower() not in ("none", ""):
        text += f" The wait for wheelchair assistance was {o['wheelchair_wait']}."
    return text


def network_operated_pct(effects_by_week, surprises):
    """Goal 1: % of planned flights operated over the ten weeks, strike days excluded (network level)."""
    planned = canceled = 0.0
    for week in range(1, 11):
        eff = effects_by_week[week]
        flights = A["flights_per_week"] * (5 / 7 if week == 8 else 1)  # strike days excluded
        lease = A["lease_cancel_factor"] if "lease_aircraft" in eff else 1.0
        rate = A["ordinary_cancel"] * lease
        c = flights * rate
        for s in crises.active(surprises, week):
            share = {"all": 1.0, "bases": A["base_flight_share"], "intl": 0.25}.get(s.get("scope", "all"), 0.3)
            c += flights * share * s.get("extra_cancel", 0) * lease
        if week == 8 and "backup_ground" not in eff:  # Dec 24 knock-on at the bases
            c += (A["flights_per_week"] / 7) * A["base_flight_share"] * A["day_after_strike_cancel_bau"]
        if "merge_flights" in eff and week not in (8, 9):
            c += flights * A["merge_share"]
        planned += flights
        canceled += c
    return round(100 * (1 - canceled / planned), 2)
