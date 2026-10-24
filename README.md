# Kestrel Air passenger simulation

Team-09 (Pegasus), TALP Simulation Lab, 24 October 2026.

Kestrel Air passengers are simulated as Gemini personas through ten company weeks, including the week 8 ground-handling strike. We compare business as usual against the two board decisions we lock.

Two persona sets share one package:

| Set | Size | How it is built | Use |
|---|---|---|---|
| `clusters` (default) | 66 | 17 segments × 4 travel windows, raked to the NHTS 2022 air-trip mix and the dossier calendar; one Gemini-generated persona per cluster, weighted by the trips it stands for | Runs and metrics |
| `curated` | 30 | 10 hand-written archetypes × 3 members, with social connections, "wins over" and "breaks at" | Social-network experiments, board demo |

```bash
echo "TALP_KEY=<your key>" > .env                          # never commit this
python scripts/test_personas.py --personas clusters --variant nodecision
python scripts/test_personas.py --personas curated --variant plan
python scripts/chat.py S-A-2                               # interview one persona
python tools/check.py team-09_submission.zip
```

Python 3.9+ and the standard library only: Gemini is called over REST.

See `CLAUDE.md` for the layout, rules and commit conventions, and `data/README.md` for the public data sources.
