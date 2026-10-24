"""Prompt builders and reply parsers. Every prompt starts with the same role-play frame."""
import re

from . import config
from .personas import profile_text

FRAME = """You are role-playing one real customer of {company}, a US low-cost airline based in \
Orlando and Philadelphia. Stay fully in character: speak and decide as this person would, \
with their money, patience and habits. Be realistic, not dramatic: most travelers grumble \
but do not overreact, and switching airlines during Christmas week is expensive. \
All companies and people are fictional."""

# Check-in questions from the challenge, exactly as worded there.
PROBE_QUESTIONS = {
    "1a": "How much do you trust {company}? 1 = not at all, 5 = completely.",
    "1b": "\"I can count on {company} to treat me right.\" 1 = strongly disagree, 5 = strongly agree.",
    "2a": "How likely are you to keep using {company} over the next three months? 1 = very unlikely, 5 = very likely.",
    "2b": "\"I am thinking about leaving {company}.\" 1 = strongly disagree, 5 = strongly agree.",
    "3a": "How likely are you to recommend {company} to a friend or colleague? 1 = very unlikely, 5 = very likely.",
    "3b": "If a friend asked you about {company} today, what would you tell them? 1 = stay away, 5 = go for it.",
    "4a": "How fairly has {company} treated you? 1 = very unfairly, 5 = very fairly.",
    "4b": "\"{company} takes advantage of people like me.\" 1 = strongly disagree, 5 = strongly agree.",
}


def parse_status(text):
    """The dossier status in a reply. Prefers a 'Status: ...' line, then any status phrase."""
    low = (text or "").lower()
    m = re.search(r"status:\s*([a-z ]+)", low)
    candidates = [m.group(1).strip()] if m else []
    candidates.append(low)
    for c in candidates:
        for s in config.PASSENGER_STATUSES:
            if s in c:
                return s
    return None


def _head(p):
    return FRAME.format(company=config.COMPANY) + "\n\n=== WHO YOU ARE ===\n" + profile_text(p)


def probe_prompt(p, context="It is November 1, before any of the events of the next ten weeks."):
    qs = "\n".join(f"{k}: {q.format(company=config.COMPANY)}" for k, q in PROBE_QUESTIONS.items())
    return f"""{_head(p)}

=== SITUATION ===
{context}

=== CHECK-IN QUESTIONS ===
Answer each question as yourself with a whole number from 1 to 5. Read each scale carefully: \
some statements are worded the other way round.
{qs}

Reply in JSON: {{"1a": n, "1b": n, "2a": n, "2b": n, "3a": n, "3b": n, "4a": n, "4b": n, \
"comment": "one sentence in your own voice"}}"""


def interview_prompt(p, question):
    return f"""{_head(p)}

=== INTERVIEW ===
A member of {config.COMPANY}'s board asks you: "{question}"
Answer in the first person, in your own voice, in 3 to 5 sentences. Do not mention that you are an AI."""


def scenario_prompt(p, scenario, message=None):
    statuses = " | ".join(config.PASSENGER_STATUSES)
    msg = f"\n=== MESSAGE FROM {config.COMPANY.upper()} ===\n\"{message}\"\n" if message else ""
    return f"""{_head(p)}

=== WHAT HAPPENS TO YOU ===
{scenario}
{msg}
=== STATUS MEANINGS ===
- flies as planned: you travel on your original Kestrel booking (late or not).
- rebooked: Kestrel moves you to another flight, including a seat on a partner airline that Kestrel arranges.
- moved to another airline: you give up on Kestrel and buy a ticket on a rival airline yourself.
- canceled the trip: you do not travel at all.

=== RESPOND IN JSON ===
{{"thoughts": "2-3 sentences in your own voice",
  "actions": ["what you actually do, e.g. wait, call support, rebook in the app, buy a ticket on another airline, post online, tell friends, file a DOT complaint"],
  "post": "what you post publicly, or null",
  "trust_1to5": n,
  "book_again": "yes | maybe | no",
  "status_line": "Status: <one of: {statuses}>"}}"""


TEST_PLAN_MESSAGE = (
    "Kestrel Air: we are sorry your trip was disrupted. If you are stranded overnight, for any reason, "
    "we have a hotel room held for you - show this message at the Kestrel desk. Extra staff are at the "
    "Orlando and Philadelphia airports and on our phone lines. You will also receive a $75 Kestrel travel "
    "credit. You can rebook or request a refund in the app; your refund rights under DOT rules are unchanged."
)


def strike_scenario(p, variant="nodecision"):
    """A test scenario for week 8 that depends on whether the trip is strike-exposed.

    variant "plan" assumes partner rebooking, hotels and extra staff are in place.
    """
    t = p["trip"]
    if p["strike_exposed"] and variant == "plan":
        return (f"It is {t['date']}, Christmas week. Ground handling workers (baggage, cleaning, wheelchair "
                f"agents, fuelers) are on a 48-hour strike in Orlando and Philadelphia; Kestrel brought in "
                f"backup ground crews. Your flight {t['route']} on {t['date']} has been CANCELED. The app "
                f"offers you a seat on a partner airline the same day, departing 21:40, at no extra cost, "
                f"or a full refund. The phone wait is about 15 minutes.")
    if p["strike_exposed"]:
        return (f"It is {t['date']}, Christmas week. Ground handling workers (baggage, cleaning, wheelchair "
                f"agents, fuelers) are on a 48-hour strike in Orlando and Philadelphia. Your flight "
                f"{t['route']} on {t['date']} has been CANCELED. The app says the next Kestrel flight with "
                f"free seats is on Dec 26. The phone line has a 2-hour wait. Meal vouchers and hotels are only "
                f"given for delays Kestrel itself causes.")
    return (f"It is Dec 23, Christmas week. Ground handling workers are on a 48-hour strike at Kestrel's "
            f"Orlando and Philadelphia bases. News and social media show long lines and canceled flights. "
            f"Your own trip ({t['date']}, {t['route']}) is not directly affected so far.")
