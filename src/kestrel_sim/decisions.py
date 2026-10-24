"""Decision files: load, validate against the dossier menu and budget, and turn into world effects.

A decision file is a JSON list of decisions as locked on the dashboard:
  {"week", "target", "actions": [{"action", "level"}], "message", "channels", "why"}
plus one field of ours, "target_rule", saying in machine terms who receives the message:
  {"all": true} | {"strike_exposed": true} | {"disrupted": true} | {"weeks": [8, 9]} | {"groups": [...]}
  (several keys = all must hold; "disrupted" means the persona's flight was canceled or delayed
  3h+ in or after the decision week). target_rule is stripped before writing run.json.
"""
import json
from pathlib import Path

BUDGET = 3_000_000

# Dossier decision menu: keyword -> (key, {level keyword: cost}); a negative cost adds to the budget.
MENU = [
    ("lease", "lease_aircraft", {"2": 1_400_000, "1": 700_000}),
    ("backup ground", "backup_ground", {"": 500_000}),
    ("free change", "free_changes", {"": 200_000}),
    ("goodwill", "goodwill", {"cash": 500_000, "50": 500_000, "credit": 300_000, "75": 300_000}),
    ("partner", "partner_rebooking", {"": 250_000}),
    ("hotel", "hotel_rooms", {"": 200_000}),
    ("extra airport", "extra_staff", {"": 150_000}),
    ("fare cap", "fare_cap", {"": 500_000}),
    ("fare sale", "fare_sale", {"": 300_000}),
    ("loyalty", "double_points", {"": 100_000}),
    ("merge", "merge_flights", {"": -250_000}),
]
TWO_WEEK = {"lease_aircraft", "free_changes", "partner_rebooking", "extra_staff", "fare_cap", "fare_sale"}


def classify(action):
    """(key, cost, level_tag) for one dashboard action."""
    name, level = action["action"].lower(), str(action.get("level", "")).lower()
    for kw, key, levels in MENU:
        if kw in name:
            for lk, cost in levels.items():
                if lk in level:
                    tag = "2" if key == "lease_aircraft" and lk == "2" else \
                          "cash" if key == "goodwill" and lk in ("cash", "50") else \
                          "credit" if key == "goodwill" else ""
                    return key, cost, tag
    raise ValueError(f"action not in the Kestrel menu: {action}")


def load(path):
    if not path:
        return []
    decisions = json.loads(Path(path).read_text(encoding="utf-8"))
    decisions = decisions.get("decisions", decisions) if isinstance(decisions, dict) else decisions
    validate(decisions)
    return decisions


def validate(decisions):
    if len(decisions) != 2:
        raise ValueError(f"exactly two decisions are needed, got {len(decisions)}")
    total = 0
    for i, d in enumerate(decisions, 1):
        if not 1 <= d["week"] <= 10:
            raise ValueError(f"decision {i}: week must be 1-10")
        if not 1 <= len(d["actions"]) <= 3:
            raise ValueError(f"decision {i}: one to three actions")
        if len(d["message"]) > 600:
            raise ValueError(f"decision {i}: message is {len(d['message'])} characters (max 600)")
        why = d["why"].split("\n") if isinstance(d["why"], str) else d["why"]
        if len([x for x in why if str(x).strip()]) != 3:
            raise ValueError(f"decision {i}: 'why' must be three lines")
        total += sum(classify(a)[1] for a in d["actions"])
    if total > BUDGET:
        raise ValueError(f"decisions cost ${total:,} (budget ${BUDGET:,})")
    return total


def total_cost(decisions):
    return sum(classify(a)[1] for d in decisions for a in d["actions"])


def for_run_json(decisions):
    """The decisions exactly as locked (without our target_rule)."""
    return [{k: v for k, v in d.items() if k != "target_rule"} for d in decisions]


def effects(decisions, week):
    """Active effects in a week: {key: level_tag}. Two-week actions run for the decision week and the
    next; the others run from their week to the end (goodwill, hotels, loyalty points, backup handling
    for the strike days, merged flights)."""
    active = {}
    for d in decisions:
        for a in d["actions"]:
            key, _, tag = classify(a)
            span = range(d["week"], d["week"] + 2) if key in TWO_WEEK else range(d["week"], 11)
            if week in span:
                active[key] = tag
    return active


def targets(decision, persona, week, disrupted_weeks):
    """Does this persona receive this decision's message in this week?"""
    if week < decision["week"]:
        return False
    rule = decision.get("target_rule", {"all": True})
    if rule.get("all"):
        return True
    ok = True
    if "strike_exposed" in rule:
        ok &= persona["strike_exposed_original"] == rule["strike_exposed"]
    if "weeks" in rule:
        ok &= any(t["week"] in rule["weeks"] for t in persona["trips"])
    if "groups" in rule:
        ok &= persona["group"] in rule["groups"]
    if rule.get("disrupted"):
        ok &= any(w >= decision["week"] and w <= week for w in disrupted_weeks)
    return ok
