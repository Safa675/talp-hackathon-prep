# Kestrel Air passenger simulation

Team-09 (Pegasus), TALP Simulation Lab, 24 October 2026.

30 LLM personas of Kestrel Air passengers (5 dossier groups, 10 archetypes, 3 members each) are played by Gemini through ten company weeks, including the week 8 ground-handling strike, to compare the business-as-usual plan against the board decisions we lock.

```bash
pip install -r requirements.txt
echo "TALP_KEY=<your key>" > .env                     # never commit this
python scripts/test_personas.py --variant nodecision  # talk to every persona
python scripts/test_personas.py --variant plan        # same, with the test plan's message
python scripts/chat.py S-A-2                          # interview one persona
```

See `CLAUDE.md` for the layout, rules and commit conventions.
