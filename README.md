# Kestrel Air customer simulation: 1st place, Talp Simulation Hackathon

Team 09 "Pegasus" (Safa Öksüz, Ahmet Berat Aydemir, Çağlar Kurt), Istanbul, 24 October 2026.

The client was Kestrel Air, a fictional US low-cost airline facing ten hard weeks: engine inspections, a government shutdown and a two-day ground-handling strike in week 8. We built its customers as LLM personas, lived through the ten weeks with them, and made two decisions on the company's behalf. The model decides what each persona says and does; code only builds the world facts the persona observes, validates the answer and counts it.

## What is here

| Part | Files | What it does |
|---|---|---|
| Simulation | [`code/sim.py`](code/sim.py), [`code/engine.py`](code/engine.py) | One model call per persona per week. Every week ends in a checkpoint keyed by a hash of everything that can change it (prompts, personas, model, seed, decisions in force, announcements so far), so a late announcement or a changed decision replays only the weeks it touches. |
| Control room | [`code/server.py`](code/server.py), [`code/ui/simple.html`](code/ui/simple.html) | Plays a live session with the company calendar, week by week; between weeks you can interview any persona about what has happened to it. |
| Persona panel | [`code/personas_66_v2.jsonl`](code/personas_66_v2.jsonl), [`code/build_personas_66_v2.py`](code/build_personas_66_v2.py), [`PERSONAS_66_V2.md`](PERSONAS_66_V2.md) | 66 travellers in five groups (family visitors, students, vacationers, business travellers, agency coordinators) on a social graph. Each has a concrete journey: dates, route, party, bags, payer, booking path, loyalty, rivals. Behaviour is not prewritten: the model decides whether to complain, forgive, post or switch after seeing the week. |
| Persona research | [`KESTREL_PERSONA_RESEARCH.md`](KESTREL_PERSONA_RESEARCH.md), [`PEGASUS_RESEARCH.md`](PEGASUS_RESEARCH.md) | Behavioural mechanisms from public filings of comparable airlines (Frontier, Allegiant, JetBlue, Spirit, Pegasus). They shape the personas; they do not set population shares. |
| Validation | [`TEAM09_ENGINE_VALIDATION.md`](TEAM09_ENGINE_VALIDATION.md), [`code/test_engine_consistency.py`](code/test_engine_consistency.py) | Causal controls: remove one event or decision, keep everything else, and check that the earlier weeks are identical and the first change appears in the right week. |
| Decision comparisons | [`team09-strike-comparison.md`](team09-strike-comparison.md), [`team09-decision-retest.md`](team09-decision-retest.md), [`team09-model-check-3.7-flash.md`](team09-model-check-3.7-flash.md) | Week-8 strike packages across seeds, and a check with a second model. |

## Result

Relative to no week-8 action, the package of backup ground handling, partner-airline rebooking and double loyalty points ($0.85M) moved week 8-9 complaints from 18 to 5, week-10 trust from 3.41 to 3.76 and the directly measured end-survey NPS from -31.8 to -3.0 (66 personas, seed 1, Gemini 3.5 Flash Lite). These are one-seed panel experiments, not forecasts, and this package still misses the board's +12 NPS and 98% flight-operation targets. Details and limits are in [`TEAM09_ENGINE_VALIDATION.md`](TEAM09_ENGINE_VALIDATION.md).

## Run

```bash
pip install google-genai
cd code
echo 'TALP_KEY=...' > .env      # a Gemini key with Vertex access
python server.py                # control room at http://localhost:8765
python engine.py plan_1 --type plan --seed 1 --decisions decisions.example.json --probe
```

The case material (challenge, client dossier, checker) belonged to Talp and is not in this repository.

## Prep: public data package (22 October)

Everything below is public statistics, gathered before the event. Nothing from Bilun or any patient/claims data.

| Path | Source | Content | Refresh |
|---|---|---|---|
| `data/eurostat/isoc_ec_ib20.csv` | TÜİK ICT household survey via Eurostat | Online purchases 2020-2025: age, sex, education, urban/rural, activity; recency and frequency | `python3 fetch_eurostat_tr.py` |
| `data/eurostat/isoc_ci_ifp_iu.csv`, `isoc_ci_ac_i.csv`, `isoc_ci_dev_i.csv` | same | Internet use, activities (internet banking, social media, streaming...), devices | same |
| `data/eurostat/demo_pjan.csv` | TÜİK population via Eurostat | Population on 1 Jan, single year of age x sex, 1960-2025 | same |
| `data/eurostat/lfsa_pgaed.csv` | TÜİK labour force survey via Eurostat | Education level x age band x sex (thousand persons) | same |
| `data/eurostat/ilc_*.csv` | TÜİK income and living conditions survey (SILC) via Eurostat | Income distribution, deprivation, ability to meet unexpected expense | same |
| `data/eurostat/hbs_str_t211.csv` | TÜİK household budget survey via Eurostat | Spending shares by category, 2005-2020 | same |
| `data/tuik_cip/provinces_latest.csv`, `provinces_long.csv` | TÜİK geo portal (cip.tuik.gov.tr, unofficial JSON endpoints) | 81 provinces: population (sum 2025 = 86,092,168 = ADNKS headline), schooling, labour market, household size, age dependency, cars, GDP per capita | `python3 fetch_tuik_provinces.py` |
| `data/globalopinionqa_turkey.json` | Anthropic/llm_global_opinions (Pew Global Attitudes + World Values Survey wave 7) | 962 questions with Turkey's answer distribution (751 Pew, 211 WVS): politics, society, values; mostly not consumer behaviour | re-download from Hugging Face |
| `data/tuik_2026_bulletin_58006.csv` | TÜİK bulletin no. 58006 (ICT household survey 2026, published 2026-08-05 10:00), read in the browser pane 2026-10-22 | Official 2026 numbers: online-order recency 2025-26, e-Devlet by age x sex, internet use, apps | hand-copied from the bulletin's text and charts |
| `data/us/nhts2022/`, `data/us/nhts_air_profile.py` | FHWA National Household Travel Survey 2022 (public) | US long-distance trip files and a weighted profile of air travellers (`nhts_air_profile.json`) | `python3 -I data/us/nhts_air_profile.py <ldtv2pub.csv> <codebook.xlsx>` |

### Traps
- TÜİK's press headline "online purchase 55.7% (2025) / 60.0% (2026)" is "ever ordered online". Eurostat's `I_BLT12` is "in the last 12 months" (50.7% in 2025). 2025 check: 42.3 (last 3 months) + 8.4 (3-12 months) + 5.0 (older) = 55.7. Match the question you ask the personas to the column you compare with.
- Eurostat's "2025" population is 1 Jan 2025. The province file's "2025" is 31 Dec 2025.
- No open province x age x sex x education table. Province-level age/education must be approximated from national tables plus province indicators (say so on the slide).
- The geo-portal endpoints are undocumented; keep the CSV copies. TÜİK's SDMX service returns 401 and microdata need a university-partner application, so neither is usable this week.
- Cite: "Source: TÜİK (via Eurostat)" and "Source: TÜİK Coğrafi İstatistik Portalı".
- Official bulletin confirms the trap: its chart splits the headline into last 3 months + 3-12 months + older than 1 year, and the headline is their sum (2026: 48.3 + 7.8 + 3.9 = 60.0). Last 12 months = 56.1 (2026) and 50.8 (2025). Survey reference period: first quarter of the year (the personas should be told it is spring 2026).
- The bulletin's online-ordering tables are by sex only. Age/education splits exist for internet use and (as a chart) for e-Devlet. For an age split of online ordering use the Eurostat file (to 2025).
