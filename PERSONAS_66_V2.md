# Kestrel persona panel v2

The versioned panel is [`code/personas_66_v2.jsonl`](code/personas_66_v2.jsonl), built reproducibly by [`code/build_personas_66_v2.py`](code/build_personas_66_v2.py). It keeps all 66 IDs, five groups, itinerary dates/routes, and `represents_trips` values from the original panel. New engine runs default to v2; existing runs keep their saved persona input.

## Why these fields

The persona's weekly choice should turn on a concrete journey: arrival timing, travel party, luggage, assistance, ability to pay, booking path, refund awareness, loyalty value, rivals, and prior Kestrel experience. This follows the Kestrel dossier and the behavioral design in [`KESTREL_PERSONA_RESEARCH.md`](KESTREL_PERSONA_RESEARCH.md) and [`PEGASUS_RESEARCH.md`](PEGASUS_RESEARCH.md). The airline research supplies mechanisms, not Kestrel population shares or policies. US DOT's [refund guidance](https://www.transportation.gov/individuals/aviation-consumer-protection/refunds) and [family seating guidance](https://www.transportation.gov/resources/individuals/aviation-consumer-protection/tips-families-and-links-airline-webpages) support treating a usable reroute, a refund, and keeping children with their party as distinct issues. Rights and available seats remain world facts, not fabricated persona entitlements.

V2 removes repeated biography and household text, age/gender/income proxies, news-source lists that the current world does not use for differential exposure, and prewritten `complaint_tendency`, `patience`, `forgiveness`, and `reaction_to_disruption`. The model still decides whether to complain, forgive, post, or switch after seeing the actual week. It retains occupation because a work deadline or a federal/postal employer may matter to a shutdown, but does not infer behavior from occupation alone.

The two useful structural additions are `party_size` where the original description gives a clear number (64 of 66 records), and a normalized `payer`. `schedule_constraint` replaces the long flexibility explanation without adding an invented deadline. The original `loyalty_tier` becomes a boolean `loyalty_member`: the dossier offers double points but does not establish a Kestrel tier program. Positive `checks_bags` now always begins with `yes`, matching the existing world's baggage parser. Four checked-bag travelers previously missed that parser because their text began with “Checks”. The sole vague `airport_assistance: other` is mapped to `none`; no specific service was documented for that coordinator.

## Measurement limits

The `represents_trips` values are preserved solely for comparability with prior experiments. Their exact group shares are scenario assumptions, not measured Kestrel demand. One agency coordinator may represent a group booking in the persona panel and many journeys in the scenario weight; those are different quantities. The 66 cases are a stress-test panel, not a random sample. Report raw panel counts by group alongside any weighted board estimate, and avoid presenting either as a confidence interval.

Changing to v2 changes the simulation input fingerprint. A live or official run using v2 must replay from week 1; all five hand-in runs must use the same version. Do not splice v2 weeks onto a v1 history. Previous finished runs remain read-only evidence of the v1 experiment.

## Checks

The build script asserts identical IDs, groups, trips, weights, segments, and windows. The panel keeps five dossier groups and the same social graph. Archived Gemini 3.5 Flash Lite runs completed 10 weeks with all 66 personas and zero call errors. Their causal controls are in [`TEAM09_ENGINE_VALIDATION.md`](TEAM09_ENGINE_VALIDATION.md). On merged `main`, the known week-8 strike may be discussed earlier because the dossier already disclosed it; its flight disruption and the week-8 decision still start in week 8. The merged engine passes eight focused regression tests and an eight-week, 66-person mock smoke run with zero errors. Its changed prompts require fresh model runs for new outcome estimates.
