# Public data package (public statistics only, no Bilun data)

Built 2026-10-22. Everything here is public statistics. Nothing from Bilun or any patient/claims data.

## What is here
| Path | Source | Content | Refresh |
|---|---|---|---|
| `data/tr/eurostat/isoc_ec_ib20.csv` | TÜİK ICT household survey via Eurostat | Online purchases 2020-2025: age, sex, education, urban/rural, activity; recency and frequency | `python3 pipelines/tr_data/fetch_eurostat_tr.py` |
| `data/tr/eurostat/isoc_ci_ifp_iu.csv`, `isoc_ci_ac_i.csv`, `isoc_ci_dev_i.csv` | same | Internet use, activities (internet banking, social media, streaming...), devices | same |
| `data/tr/eurostat/demo_pjan.csv` | TÜİK population via Eurostat | Population on 1 Jan, single year of age x sex, 1960-2025 | same |
| `data/tr/eurostat/lfsa_pgaed.csv` | TÜİK labour force survey via Eurostat | Education level x age band x sex (thousand persons) | same |
| `data/tr/eurostat/ilc_*.csv` | TÜİK income and living conditions survey (SILC) via Eurostat | Income distribution, deprivation, ability to meet unexpected expense | same |
| `data/tr/eurostat/hbs_str_t211.csv` | TÜİK household budget survey via Eurostat | Spending shares by category, 2005-2020 | same |
| `data/tr/tuik_cip/provinces_latest.csv`, `provinces_long.csv` | TÜİK geo portal (cip.tuik.gov.tr, unofficial JSON endpoints) | 81 provinces: population (sum 2025 = 86,092,168 = ADNKS headline), schooling, labour market, household size, age dependency, cars, GDP per capita | `python3 pipelines/tr_data/fetch_tuik_provinces.py` |
| `data/tr/globalopinionqa_turkey.json` | Anthropic/llm_global_opinions (Pew Global Attitudes + World Values Survey wave 7) | 962 questions with Turkey's answer distribution (751 Pew, 211 WVS): politics, society, values; mostly not consumer behaviour | re-download from Hugging Face |
| `data/tr/tuik_2026_bulletin_58006.csv` | TÜİK bulletin no. 58006 (ICT household survey 2026, published 2026-08-05 10:00), read in the browser pane 2026-10-22 | Official 2026 numbers: online-order recency 2025-26, e-Devlet by age x sex, internet use, apps | hand-copied from the bulletin's text and charts |

## Traps
- TÜİK's press headline "online purchase 55.7% (2025) / 60.0% (2026)" is "ever ordered online". Eurostat's `I_BLT12` is "in the last 12 months" (50.7% in 2025). 2025 check: 42.3 (last 3 months) + 8.4 (3-12 months) + 5.0 (older) = 55.7. Match the question you ask the personas to the column you compare with.
- Eurostat's "2025" population is 1 Jan 2025. The province file's "2025" is 31 Dec 2025.
- No open province x age x sex x education table. Province-level age/education must be approximated from national tables plus province indicators (say so on the slide).
- The geo-portal endpoints are undocumented; keep the CSV copies. TÜİK's SDMX service returns 401 and microdata need a university-partner application, so neither is usable this week.
- Cite: "Source: TÜİK (via Eurostat)" and "Source: TÜİK Coğrafi İstatistik Portalı".
- Official bulletin confirms the trap: its chart splits the headline into last 3 months + 3-12 months + older than 1 year, and the headline is their sum (2026: 48.3 + 7.8 + 3.9 = 60.0). Last 12 months = 56.1 (2026) and 50.8 (2025). Survey reference period: first quarter of the year (the personas should be told it is spring 2026).
- The bulletin's online-ordering tables are by sex only. Age/education splits exist for internet use and (as a chart) for e-Devlet. For an age split of online ordering use the Eurostat file (to 2025).

## US data (used for Kestrel Air)
| Path | Source | Content | Refresh |
|---|---|---|---|
| `data/us/nhts2022/` | FHWA National Household Travel Survey 2022, public files (see `Citation.pdf`) | Households, persons, trips, long-distance trips, vehicles; codebook | download from nhts.ornl.gov |
| `data/us/nhts_air_profile.json` | NHTS 2022 long-distance trips by air (MAINMODE=14), weighted by WTPERFIN | Trip purpose, income, life cycle, age, party size, nights away, domestic vs international, home region | `python3 -I pipelines/grounding/nhts_air_profile.py data/us/nhts2022/ldtv2pub.csv data/us/nhts2022/codebook.xlsx data/us/nhts_air_profile.json` |

The Kestrel persona clusters (`data/personas/clusters/`) use the trip-purpose, party-size and age tables from this profile; see `pipelines/personas/make_clusters.py`.

## Turkish data (from the general prep, not used for Kestrel)
Everything in the table above under `data/tr/`.
