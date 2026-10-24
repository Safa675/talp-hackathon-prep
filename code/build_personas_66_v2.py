#!/usr/bin/env python3
"""Build a compact, behaviorally focused persona panel from the 66 fixed records.

The IDs, trips, groups, and scenario weights stay identical. No new flight,
benefit, right, or recovery option is invented. The old panel remains available
so completed simulations retain their original input.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "personas_66.jsonl"
OUTPUT = HERE / "personas_66_v2.jsonl"


def party_size(description):
    """Return only a party size stated or arithmetically clear in the source."""
    s = description.lower()
    number = re.search(r"(?:group of|party of|group of) (\d+)|(?:wedding|conference) (?:party|group) of (\d+)", s)
    if number:
        return int(next(x for x in number.groups() if x))
    if re.search(r"\b(?:30|32) senior\b|\b(?:22) (?:guests|clients)\b|\b(?:12) (?:attendees|clients)\b", s):
        return int(re.search(r"\b(30|32|22|12)\b", s).group(1))
    if re.search(r"\btwo\b.*\bchildren\b", s) and ("mother" in s or "elderly" in s):
        return 5
    if re.search(r"\btwo\b.*\bchildren\b", s):
        return 4
    if "child" in s and "elderly" in s and ("spouse" in s or "husband" in s or "wife" in s):
        return 4
    if "unaccompanied minor" in s or "child flying alone" in s:
        return 1
    if "group of five" in s:
        return 5
    if s.strip() in {"alone", "child (8-14) flying alone"}:
        return 1
    if any(x in s for x in ("spouse", "husband", "wife", "partner", "one friend", "close friend", "best friend")):
        return 2
    return None


def payer(text):
    s = text.lower()
    if "parent" in s:
        return "family-funded"
    if "client" in s or "tour participant" in s or "tour package" in s or "travel agency" in s:
        return "client/group-funded"
    if "employer" in s or "reimburs" in s or "travel nursing agency" in s:
        return "employer-funded or reimbursed"
    return "self-funded"


def checked_bags(text):
    """The world model expects positive bag descriptions to start with 'yes'."""
    s = text.strip()
    if re.match(r"(?i)^(no\b|never\b)", s):
        return "no"
    if re.match(r"(?i)^yes\b", s):
        return s
    return "yes: " + s


def compact(p):
    out = {
        "id": p["id"],
        "group": p["group"],
        "name": p["name"],
        "occupation": p["occupation"],
        "home_area": p["home_area"],
        "trips": p["trips"],
        "trip_reason": p["trip_reason"],
        "travel_party": p["travel_party"],
        "date_flexibility": p["date_flexibility"],
        "schedule_constraint": p["flexibility_reason"],
        "checks_bags": checked_bags(p["checks_bags"]),
        # 'other' supplied no actual assistance requirement, so avoid
        # inventing wheelchair service for this group coordinator.
        "airport_assistance": "none" if p["airport_assistance"] == "other" else p["airport_assistance"],
        "money_pressure": p["money_pressure"],
        "payer": payer(p["who_pays"]),
        "booking_channel": p["booking_channel"],
        "knows_refund_rights": p["knows_refund_rights"],
        "loyalty_member": p["loyalty_tier"] != "none",
        "also_flies_rivals": p["also_flies_rivals"],
        "social_media_activity": p["social_media_activity"],
        "past_kestrel_experience": p["past_kestrel_experience"],
        # These fields are hidden from the persona prompt and used for analysis.
        "segment": p["segment"],
        "window": p["window"],
        "represents_trips": p["represents_trips"],
    }
    size = party_size(p["travel_party"])
    if size is not None:
        out["party_size"] = size
    return out


def main():
    people = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = [compact(p) for p in people]
    assert len(people) == len(result) == 66
    for old, new in zip(people, result):
        for field in ("id", "group", "trips", "represents_trips", "segment", "window"):
            assert old[field] == new[field], (old["id"], field)
    OUTPUT.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in result), encoding="utf-8")
    print(f"Wrote {len(result)} personas to {OUTPUT}")


if __name__ == "__main__":
    main()
