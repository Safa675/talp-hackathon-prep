#!/usr/bin/env python3
"""Check a TALP Simulation Lab submission before you upload it.

    python3 check.py team-NN_submission.zip
    python3 check.py path/to/folder          (the same layout, not zipped)

It only reads files; it never runs your code. Python 3.9+, no installs.
Exit code 0 = nothing missing, 1 = something to fix.
"""
import json
import math
import re
import sys
import zipfile
from pathlib import Path

RUNS = {
    "plan_1": "plan",
    "plan_2": "plan",
    "nodecision_1": "nodecision",
    "nodecision_2": "nodecision",
    "plan_nosurprises": "plan_nosurprises",
}
PROBE_RUNS = ("plan_1", "nodecision_1")
PROBE_QUESTIONS = ("1a", "1b", "2a", "2b", "3a", "3b", "4a", "4b")
WEEKS = range(1, 11)
MIN_PERSONAS, MIN_GROUPS, MIN_PER_GROUP = 24, 3, 4

# From each dossier: "What each persona reports every week" (first line per kind)
# and the number of board goals, leaving out the budget goal.
COMPANIES = {
    "cobalt": {"name": "Cobalt Bank", "goals": 3,
               "statuses": ["main bank", "second bank", "dormant", "left"]},
    "aisle": {"name": "Aisle", "goals": 4,
              "statuses": ["buys as usual", "buys less", "paused", "moved to a rival",
                           "active", "reduced", "left"]},
    "morsel": {"name": "Morsel", "goals": 3,
               "statuses": ["orders as usual", "orders less", "paused", "moved to a rival",
                            "active", "limited", "left",
                            "driving", "driving less", "protesting"]},
    "kestrel": {"name": "Kestrel Air", "goals": 4,
                "statuses": ["flies as planned", "rebooked", "moved to another airline",
                             "canceled the trip"]},
    "quillbook": {"name": "Quillbook", "goals": 4,
                  "statuses": ["stays", "stays but unhappy", "looking at rivals", "moved to a rival",
                               "recommends quillbook", "neutral", "steering clients away"]},
}
# Characters that change when text is copied between apps; compared as their plain form.
PLAIN = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                       "…": "...", " ": " "})


def is_int(x, lo, hi):
    """A JSON whole number in [lo, hi]; true/false and 3.0 do not count."""
    return type(x) is int and lo <= x <= hi


def ref(x):
    """An id as text, so 7, "7" and 7.0 are the same persona; null stays None."""
    if x is None:
        return None
    return str(int(x)) if isinstance(x, float) and x.is_integer() else str(x)


def norm(text):
    """Lowercase words only, so 'Moved to a rival.' matches 'moved_to_a_rival'."""
    return " ".join(re.sub(r"[^a-z0-9$%]+", " ", str(text).lower()).split())


def norm_msg(text):
    """Whitespace-, quote- and dash-insensitive form for word-for-word checks; undoes JSON escapes."""
    t = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), str(text))
    t = t.replace("\\n", " ").replace("\\t", " ").replace('\\"', '"')
    return " ".join(t.lower().translate(PLAIN).split())


def contains_words(haystack_norm, needle):
    return f" {norm(needle)} " in f" {haystack_norm} "


class Report:
    def __init__(self):
        self.lines = []
        self.failed = False

    def ok(self, text):
        self.lines.append("  ok  " + text)

    def bad(self, text):
        self.failed = True
        self.lines.append(" FIX  " + text)

    def note(self, text):
        self.lines.append("      " + text)

    def section(self, text):
        self.lines.append("\n" + text)


def load_files(path):
    """Map 'relative/path' -> callable returning bytes. ZIPs are read in memory, never extracted."""
    p = Path(path)
    files = {}
    if p.is_dir():
        for f in p.rglob("*"):
            if f.is_file():
                files[f.relative_to(p).as_posix()] = f.read_bytes
        return files
    z = zipfile.ZipFile(p)
    if sum(i.file_size for i in z.infolist()) > 3_000_000_000:
        raise ValueError("the ZIP unpacks to more than 3 GB")
    for info in z.infolist():
        name = info.filename.replace("\\", "/")  # some Windows tools write backslashes
        if not info.is_dir() and not name.startswith("__MACOSX/"):
            files[name] = (lambda i=info: z.read(i))
    return files


def read_text(files, name):
    try:
        data = files[name]()
    except Exception as e:  # bad CRC, password, unsupported compression
        raise ValueError(f"cannot read it from the ZIP ({str(e)[:60]}); zip it again without a password")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("not UTF-8; save it as UTF-8")


def read_json(files, name, rep, label):
    try:
        return json.loads(read_text(files, name))
    except Exception as e:
        rep.bad(f"{label}: not valid JSON ({str(e)[:80]})")
        return None


def read_jsonl(files, name, rep, label):
    try:
        text = read_text(files, name)
    except ValueError as e:
        rep.bad(f"{label}: {e}")
        return []
    rows, errors = [], []
    for n, line in enumerate(text.split("\n"), 1):  # not splitlines(): model text may hold U+2028
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("not an object")
            rows.append(row)
        except Exception:
            errors.append(n)
    if errors:
        rep.bad(f"{label}: {len(errors)} lines are not JSON objects (first: line {errors[0]})")
    return rows


def decision_list(run):
    decs = run.get("decisions")
    return [d for d in decs if isinstance(d, dict)] if isinstance(decs, list) else []


def decision_key(d):
    acts = d.get("actions") if isinstance(d.get("actions"), list) else []
    acts = tuple(sorted((norm(a.get("action", "")), norm(a.get("level", "")))
                        for a in acts if isinstance(a, dict)))
    return (str(d.get("week")), norm_msg(d.get("message", "")), acts)


def check_decisions(decisions, kind, rep, label):
    if not isinstance(decisions, list):
        rep.bad(f"{label}: 'decisions' must be a list")
        return
    want = 0 if kind == "nodecision" else 2
    if len(decisions) != want:
        rep.bad(f"{label}: {len(decisions)} decisions, expected {want}")
    for i, d in enumerate(decisions, 1):
        if not isinstance(d, dict):
            rep.bad(f"{label}: decision {i} is not an object")
            continue
        if not is_int(d.get("week"), 1, 10):
            rep.bad(f"{label}: decision {i} 'week' must be a whole number from 1 to 10")
        msg = d.get("message")
        if not isinstance(msg, str) or not msg.strip():
            rep.bad(f"{label}: decision {i} has no 'message'")
        elif len(msg) > 600:
            rep.bad(f"{label}: decision {i} message is {len(msg)} characters (max 600)")
        acts = d.get("actions")
        if not isinstance(acts, list) or not 1 <= len(acts) <= 3 or not all(
                isinstance(a, dict) and a.get("action") and a.get("level") not in (None, "") for a in acts):
            rep.bad(f"{label}: decision {i} needs 1 to 3 'actions', each with 'action' and 'level' "
                    f"(\"on\" if the action has no levels)")
        for field in ("target", "channels", "why"):
            if not d.get(field):
                rep.bad(f"{label}: decision {i} has no '{field}'")


def check(path):
    """Return (report, data). data holds the parsed runs for the organizer's tools."""
    rep = Report()
    data = {"runs": {}, "company": None, "root": None}
    try:
        files = load_files(path)
    except Exception as e:
        rep.bad(f"cannot open {path}: {e}")
        return rep, data

    rep.section("Hand-in")
    if Path(path).is_file() and not re.fullmatch(r"team-\d{2}_submission\.zip", Path(path).name):
        rep.note(f"the upload is named team-NN_submission.zip (this file is {Path(path).name})")
    found = {}
    for f in files:
        m = re.match(r"^((?:[^/]+/)*)runs/([^/]+)/run\.json$", f)
        if m:
            found.setdefault(m.group(1), set()).add(m.group(2))
    if not found:
        rep.bad("no runs/<name>/run.json found; see 'How to save your runs' in the challenge")
        return rep, data
    # The folder holding most of the five runs; an old copy elsewhere is ignored.
    root = min(found, key=lambda r: (-len(found[r] & set(RUNS)), len(r)))
    data["root"] = root
    if root:
        rep.note(f"reading the submission in {root}")
    others = sorted(r or "the top of the ZIP" for r in found if r != root)
    if others:
        rep.note("also found runs/ in " + ", ".join(others) + " (ignored)")
    for doc in ("CLIENT_MEMO.md", "TEAM_DOC.md"):
        try:
            ok = root + doc in files and read_text(files, root + doc).strip()
        except ValueError:
            ok = False
        rep.ok(doc) if ok else rep.bad(f"{doc} is missing or empty (put it next to runs/)")
    for f in files:
        try:
            leaked = re.search(rb"AQ\.[A-Za-z0-9_-]{40}", files[f]())
        except Exception:
            leaked = None
        if leaked:
            rep.bad(f"your Vertex key is written in {f}; delete it and read the key from an environment variable")
    if not any(f.startswith(root + "code/") for f in files):
        rep.bad("no code/ folder next to runs/ (put your code there)")
    present = found[root]
    for name in RUNS:
        if name not in present:
            rep.bad(f"run folder runs/{name}/ is missing")
    extra = sorted(present - set(RUNS))
    if extra:
        rep.note("extra run folders (ignored): " + ", ".join(extra))

    companies = set()
    for name, kind in RUNS.items():
        if name not in present:
            continue
        base = f"{root}runs/{name}/"
        rep.section(f"runs/{name}")
        need = ["run.json", "personas.jsonl", "calls.jsonl", "weekly.jsonl", "metrics.json"]
        if name in PROBE_RUNS:
            need.append("probe.jsonl")
        missing = [f for f in need if base + f not in files]
        for f in missing:
            rep.bad(f"{f} is missing")
        if missing:
            continue
        run = read_json(files, base + "run.json", rep, "run.json")
        if not isinstance(run, dict):
            if run is not None:
                rep.bad("run.json must be a JSON object")
            continue
        if run.get("type") != kind:
            rep.bad(f"run.json 'type' is {run.get('type')!r}, expected {kind!r}")
        company = str(run.get("company", "")).lower()
        if company not in COMPANIES:
            rep.bad(f"run.json 'company' must be one of {', '.join(COMPANIES)}")
            continue
        companies.add(company)
        for field in ("seed", "model"):
            if run.get(field) in (None, ""):
                rep.bad(f"run.json has no '{field}'")
        check_decisions(run.get("decisions"), kind, rep, "run.json")
        metrics = read_json(files, base + "metrics.json", rep, "metrics.json")
        if metrics is not None and not isinstance(metrics, dict):
            rep.bad("metrics.json must be a JSON object with goal_1, goal_2 and so on")
        r = {
            "run": run,
            "personas": read_jsonl(files, base + "personas.jsonl", rep, "personas.jsonl"),
            "calls": read_jsonl(files, base + "calls.jsonl", rep, "calls.jsonl"),
            "weekly": read_jsonl(files, base + "weekly.jsonl", rep, "weekly.jsonl"),
            "metrics": metrics if isinstance(metrics, dict) else {},
            "probe": read_jsonl(files, base + "probe.jsonl", rep, "probe.jsonl") if name in PROBE_RUNS else [],
        }
        data["runs"][name] = r
        check_run(name, company, r, rep)

    if len(companies) > 1:
        rep.bad("runs name different companies: " + ", ".join(sorted(companies)))
    data["company"] = next(iter(companies)) if len(companies) == 1 else None
    check_across(data["runs"], rep)
    return rep, data


def check_run(name, company, r, rep):
    personas = r["personas"]
    ids = [ref(p.get("id")) for p in personas]
    if None in ids or len(set(ids)) != len(ids):
        rep.bad("personas.jsonl: every persona needs a unique 'id'")
    groups, no_group = {}, 0
    for p in personas:
        g = norm(p["group"]) if isinstance(p.get("group"), str) else ""
        if g:
            groups.setdefault(g, []).append(p)
        else:
            no_group += 1
    small = sorted(g for g, ps in groups.items() if len(ps) < MIN_PER_GROUP)
    if no_group:
        rep.bad(f"personas.jsonl: {no_group} personas have no 'group' (a group from your dossier)")
    if len(personas) < MIN_PERSONAS:
        rep.bad(f"{len(personas)} personas (at least {MIN_PERSONAS})")
    if len(groups) < MIN_GROUPS:
        rep.bad(f"{len(groups)} groups (at least {MIN_GROUPS})")
    if small:
        rep.bad(f"groups with fewer than {MIN_PER_GROUP} personas: {', '.join(small)}")
    if len(personas) >= MIN_PERSONAS and len(groups) >= MIN_GROUPS and not small and not no_group:
        rep.ok(f"{len(personas)} personas in {len(groups)} groups")

    pid = set(ids) - {None}
    calls = {}
    bad_calls = 0
    for c in r["calls"]:
        c["persona"] = ref(c.get("persona"))
        okc = (c.get("id") is not None and isinstance(c.get("prompt"), str) and c["prompt"].strip()
               and isinstance(c.get("response"), str) and is_int(c.get("week"), 0, 11)
               and c.get("model") not in (None, "") and (c["persona"] is None or c["persona"] in pid))
        if not okc:
            bad_calls += 1
            continue
        calls[ref(c["id"])] = c
    if bad_calls:
        rep.bad(f"calls.jsonl: {bad_calls} calls lack 'id', 'persona' (a persona id or null), "
                f"'week' (a whole number 0-11), 'prompt', 'response' or 'model'")
    if len(calls) != len(r["calls"]) - bad_calls:
        rep.bad("calls.jsonl: call ids must be unique")
    rep.ok(f"{len(calls)} LLM calls") if calls else rep.bad("calls.jsonl has no usable calls")
    r["calls_by_id"] = calls

    allowed = {norm(s) for s in COMPANIES[company]["statuses"]}
    seen, untraced = {}, []
    problems = {"an unknown persona": [], "a week that is not a whole number from 1 to 10": [],
                "the same persona and week twice": [],
                "a status not in this list: " + ", ".join(COMPANIES[company]["statuses"]): []}
    kinds = list(problems)
    for w in r["weekly"]:
        w["persona"] = ref(w.get("persona"))
        key = (w["persona"], w.get("week"))
        example = f"persona {key[0]} week {key[1]!r}"
        if key[0] not in pid:
            problems[kinds[0]].append(example)
            continue
        if not is_int(key[1], 1, 10):
            problems[kinds[1]].append(example)
            continue
        if key in seen:
            problems[kinds[2]].append(example)
        seen[key] = w
        st = norm(w["status"]) if isinstance(w.get("status"), str) else None
        if st not in allowed:
            problems[kinds[3]].append(f"{example}: {w.get('status')!r}")
            continue
        c = calls.get(ref(w.get("call")))
        if (c is None or c["persona"] != key[0] or c.get("week") != key[1]
                or not contains_words(norm(c["response"]), st)):
            untraced.append(example)
    missing = [(p, wk) for p in pid for wk in WEEKS if (p, wk) not in seen]
    if missing:
        rep.bad(f"weekly.jsonl: {len(missing)} persona-weeks missing (every persona, weeks 1-10)")
    for kind, rows in problems.items():
        if rows:
            rep.bad(f"weekly.jsonl: {len(rows)} lines with {kind}; e.g. {rows[0]}")
    if untraced:
        rep.bad(f"weekly.jsonl: {len(untraced)} statuses do not come from a model answer, e.g. "
                f"{untraced[0]}: 'call' must be a call for that persona and week whose response "
                f"contains the status words")
    if seen and not untraced and not any(problems.values()):
        rep.ok("every weekly status comes from a model answer")
    r["traced"] = (len(seen) - len(untraced), len(seen))

    goals = COMPANIES[company]["goals"]
    m = r["metrics"]
    gaps = [f"goal_{i}" for i in range(1, goals + 1)
            if not isinstance(m.get(f"goal_{i}"), (int, float)) or isinstance(m.get(f"goal_{i}"), bool)
            or not math.isfinite(m.get(f"goal_{i}"))]
    if gaps:
        rep.bad(f"metrics.json: needs a finite number for {', '.join(gaps)}")
    elif not m.get("units"):
        rep.bad("metrics.json: add 'units' saying what each number means")
    else:
        rep.ok(f"metrics.json has goal_1 to goal_{goals}")

    if name in PROBE_RUNS:
        got, bad_rows = set(), 0
        for row in r["probe"]:
            row["persona"] = ref(row.get("persona"))
            c = calls.get(ref(row.get("call")))
            when = row.get("when")
            key = (row["persona"], when, row.get("question"))
            okr = (row["persona"] in pid and when in ("start", "end")
                   and row.get("question") in PROBE_QUESTIONS and is_int(row.get("score"), 1, 5)
                   and c is not None and c["persona"] == row["persona"]
                   and c.get("week") == (0 if when == "start" else 11) and key not in got)
            if okr:
                got.add(key)
            else:
                bad_rows += 1
        want = len(pid) * 2 * len(PROBE_QUESTIONS)
        if bad_rows:
            rep.bad(f"probe.jsonl: {bad_rows} bad lines (persona, when start/end, question 1a-4b, "
                    f"score a whole number 1-5, call for that persona in week 0 or 11, each answer once)")
        if len(got) < want:
            rep.bad(f"probe.jsonl: {len(got)} of {want} answers (every persona, start and end, 8 questions)")
        elif not bad_rows:
            rep.ok("check-in questions answered by every persona, start and end")

    decs = [d for d in decision_list(r["run"]) if isinstance(d.get("message"), str) and d["message"].strip()
            and is_int(d.get("week"), 1, 10)]
    prompts = [(c["week"], c["persona"], norm_msg(c["prompt"])) for c in calls.values()]
    r["message_reach"] = []  # (decision number, week, personas reached, early, their ids, target)
    for i, d in enumerate(decs, 1):
        msg = norm_msg(d["message"])
        others = [norm_msg(o["message"]) for o in decs if o is not d and norm_msg(o["message"]) != msg]
        reached = {p for wk, p, t in prompts if p is not None and 1 <= wk <= 10 and wk >= d["week"] and msg in t}

        def strip_others(t):
            for o in others:  # a sentence shared with the other decision is not an early leak
                t = t.replace(o, " ")
            return t
        early = any(msg in strip_others(t) for wk, p, t in prompts if wk < d["week"])
        r["message_reach"].append((i, d["week"], len(reached), early, reached, str(d.get("target", ""))))
        if not reached:
            rep.bad(f"decision {i}: the message never appears word for word in a persona's prompt "
                    f"from week {d['week']}")
        else:
            rep.ok(f"decision {i}: message reaches {len(reached)} personas word for word from week {d['week']}")
        if early:
            rep.bad(f"decision {i}: the message appears in prompts before week {d['week']}")


def check_across(runs, rep):
    rep.section("Across runs")
    names = [n for n in RUNS if n in runs]
    if len(names) < 2:
        return

    def canon(r):
        return sorted(json.dumps(p, sort_keys=True) for p in r["personas"])

    first = canon(runs[names[0]])
    diff = [n for n in names[1:] if canon(runs[n]) != first]
    if diff:
        rep.bad("personas.jsonl differs between runs: " + ", ".join(diff) + " (use the same personas in all five)")
    else:
        rep.ok("the same personas in every run")

    plans = [n for n in ("plan_1", "plan_2", "plan_nosurprises") if n in runs]
    keys = {n: sorted(decision_key(d) for d in decision_list(runs[n]["run"])) for n in plans}
    if len({json.dumps(k) for k in keys.values()}) > 1:
        rep.bad("the plan runs use different decisions (plan_1, plan_2 and plan_nosurprises must match)")
    elif plans:
        rep.ok("the plan runs use the same two decisions")

    plan_msgs = [norm_msg(d["message"]) for n in plans for d in decision_list(runs[n]["run"])
                 if isinstance(d.get("message"), str) and d["message"].strip()]
    for n in ("nodecision_1", "nodecision_2"):
        if n in runs and plan_msgs:
            texts = [norm_msg(c["prompt"]) for c in runs[n].get("calls_by_id", {}).values()]
            if any(m in t for m in plan_msgs for t in texts):
                rep.bad(f"{n}: your decision message appears in its prompts (this run has no decisions)")

    def texts(n, field):  # weeks 1-10 only: the check-in calls are in plan_1 and nodecision_1 alone
        return sorted(c[field] for c in runs[n].get("calls_by_id", {}).values() if 1 <= c["week"] <= 10)

    for a, b in (("plan_1", "plan_2"), ("nodecision_1", "nodecision_2")):
        if a in runs and b in runs and texts(a, "response") and texts(a, "response") == texts(b, "response"):
            rep.bad(f"{a} and {b} have identical model answers in weeks 1-10; run the second seed for real "
                    f"(give the model the seed, temperature above 0)")
    if "plan_1" in runs and "plan_nosurprises" in runs and texts("plan_1", "prompt") \
            and texts("plan_1", "prompt") == texts("plan_nosurprises", "prompt"):
        rep.bad("plan_1 and plan_nosurprises send the same prompts in weeks 1-10; with the surprises off "
                "the personas must read something different")


def main(argv):
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if len(argv) == 2 else 2
    print(f"Checking {argv[1]}")
    try:
        rep, _ = check(argv[1])
    except Exception as e:  # a file we did not expect: say so instead of a traceback
        print(f" FIX  check.py could not read part of the submission ({type(e).__name__}: {str(e)[:120]}).\n"
              "      Compare your files with 'How to save your runs'; if they match, show this line to an organizer.")
        return 1
    print("\n".join(rep.lines))
    print("\nNothing to fix." if not rep.failed else "\nFix the FIX lines, then run this again.")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
