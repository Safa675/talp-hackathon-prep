"""Render persona cards as one self-contained HTML page.

    python scripts/render_cards.py [--personas clusters|curated]              # personas only
    python scripts/render_cards.py --personas curated outputs/persona_tests/<run>/results.jsonl
"""
import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kestrel_sim import config  # noqa: E402
from kestrel_sim.personas import load_personas  # noqa: E402

CSS = """
:root{--bg:#f4f3ee;--card:#fbfaf7;--ink:#14141a;--muted:#6b6b76;--line:#e4e2dc;--accent:#3b3bf0;
--accent2:#7c7cf7;--chip:#f1f0eb;--live:#22c55e;--warn:#d97706;--bad:#dc2626}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111116;--card:#1a1a21;--ink:#ececf1;
--muted:#9a9aa6;--line:#2b2b35;--chip:#23232c}}
:root[data-theme="dark"]{--bg:#111116;--card:#1a1a21;--ink:#ececf1;--muted:#9a9aa6;--line:#2b2b35;--chip:#23232c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 24px;font-size:14px}
h2{font-size:15px;margin:28px 0 4px}.arch{color:var(--muted);font-size:13px;margin:0 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;
box-shadow:0 6px 24px rgba(0,0,0,.06)}
.top{display:flex;gap:14px;align-items:center}
.av{width:52px;height:52px;border-radius:14px;display:grid;place-items:center;color:#fff;font-weight:700;
background:linear-gradient(135deg,var(--accent),var(--accent2));flex:none}
.name{font-weight:700;font-size:19px}.meta{font-family:ui-monospace,Consolas,monospace;color:var(--muted);font-size:12.5px}
.q{border-left:3px solid var(--accent);margin:16px 0;padding:2px 0 2px 12px;font-style:italic;font-size:15px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.tag{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;border:1px solid var(--line);
background:var(--chip);border-radius:999px;padding:3px 10px}
.row{display:flex;justify-content:space-between;gap:12px;border-top:1px solid var(--line);padding:9px 0;font-size:13.5px}
.k{font-family:ui-monospace,Consolas,monospace;font-size:11px;letter-spacing:.06em;color:var(--muted);
text-transform:uppercase;flex:none;padding-top:2px}.v{text-align:right}
.bar{height:6px;border-radius:99px;background:var(--line);overflow:hidden;margin:6px 0 12px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.foot{font-family:ui-monospace,Consolas,monospace;font-size:11px;letter-spacing:.06em;color:var(--accent2)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--live);margin-right:6px;
box-shadow:0 0 6px var(--live)}
.st-rebooked{color:var(--warn)}.st-moved,.st-canceled{color:var(--bad)}
details{margin-top:10px;font-size:13px;color:var(--muted)}summary{cursor:pointer}
"""


def esc(x):
    return html.escape(str(x)) if x is not None else ""


def card(p, r):
    intent = r.get("intent") if r else None
    s = (r or {}).get("strike") or {}
    status = s.get("status")
    st_cls = "st-" + status.split()[0] if status else ""
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in p["tags"][:3])
    trips = "<br>".join(f"{esc(t['date'])} · {esc(t['from'])}→{esc(t['to'])}" for t in p["trips"])
    rows = [(k, esc(v)) for k, v in p["card_rows"]]
    rows += [("Trips", trips + (" · strike-exposed" if p["strike_exposed"] else "")),
             ("Stands for", f"{p['weight']:,} trips")]
    if r:
        rows.append(("W8 test", f'<span class="{st_cls}">{esc(status)}</span> · again: {esc(s.get("book_again"))}'))
    rows_html = "".join(f'<div class="row"><span class="k">{k}</span><span class="v">{v}</span></div>' for k, v in rows)
    bar = ""
    if intent is not None:
        bar = (f'<div class="row" style="border-bottom:0"><span class="k">Would book again</span>'
               f'<span class="v">{intent}%</span></div><div class="bar"><i style="width:{intent}%"></i></div>')
    extra = ""
    if r:
        extra = (f"<details><summary>What {esc(p['name'].split()[0])} said</summary>"
                 f"<p>{esc(r.get('interview'))}</p><p><b>W8:</b> {esc(s.get('thoughts'))}</p>"
                 f"{'<p><b>Post:</b> ' + esc(s.get('post')) + '</p>' if s.get('post') else ''}</details>")
    quote = f'<div class="q">“{esc(p["quote"])}”</div>' if p.get("quote") else '<div style="height:14px"></div>'
    return f"""<div class="card"><div class="top"><div class="av">{esc(p['name'][0])}</div><div>
<div class="name">{esc(p['name'].split()[0])}, {p['age']}</div>
<div class="meta">{esc(p['tagline'])} · {esc(p['home'])}</div></div></div>
{quote}<div class="tags">{tags}</div>{rows_html}{bar}
<div class="foot"><span class="dot"></span>SIMULATED PERSONA · {esc(p['id'])}</div>{extra}</div>"""


def render_cards(personas, results, path):
    by_id = {r["persona"]: r for r in (results or [])}
    sections, current = [], None
    for p in personas:
        if p["archetype"] != current:
            if current is not None:
                sections.append("</div>")
            current = p["archetype"]
            note = f" · {esc(p['core_tension'])}" if p.get("core_tension") else ""
            sections.append(f"<h2>{esc(p['archetype_label'])}</h2><p class='arch'>{esc(p['group'])}{note}</p>"
                            f"<div class='grid'>")
        sections.append(card(p, by_id.get(p["id"])))
    sections.append("</div>")
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Kestrel Personas</title>
<style>{CSS}</style></head><body><h1>Kestrel Air · simulated passengers</h1>
<p class="sub">{len(personas)} personas · {len({p['archetype'] for p in personas})} {'archetypes' if personas and personas[0]['set'] == 'curated' else 'segments'} · {len({p['group'] for p in personas})} groups · team-09 Pegasus</p>
{''.join(sections)}</body></html>"""
    Path(path).write_text(doc, encoding="utf-8")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?", help="results.jsonl from scripts/test_personas.py")
    ap.add_argument("--personas", choices=sorted(config.PERSONA_SETS), default=config.DEFAULT_PERSONA_SET)
    args = ap.parse_args()
    results = []
    if args.results:
        results = [json.loads(l) for l in Path(args.results).read_text(encoding="utf-8").splitlines() if l.strip()]
        target = Path(args.results).with_name("cards.html")
    else:
        target = config.OUTPUT_DIR / f"cards-{args.personas}.html"
        target.parent.mkdir(parents=True, exist_ok=True)
    print(render_cards(load_personas(args.personas), results, target))
