# Pegasus Airlines research for the TALP airline simulation

**Research date:** 24 October 2026  
**Purpose:** Use Pegasus Airlines as a real-world reference to improve the realism of our fictional Kestrel Air persona simulation. Pegasus is an analogue, not a proxy for Kestrel: its geography, network, rules, operations, and customer mix differ.

## Executive read

Pegasus is a Turkish low-cost airline whose offer is built around affordable base fares, a broad domestic and international network, digital self-service, and optional paid extras. Recent company reporting shows substantial growth and a material ancillary-revenue stream. Its customers therefore should not be modeled as a single “cheap-fare traveler”: route purpose, baggage and seat purchases, flexibility, booking channel, disruption exposure, and ability to use digital self-service all shape what they value.

For TALP, the most useful transfer is a **behavioral design**, not Pegasus-specific operational numbers. Build personas with varied trip urgency, price sensitivity, add-on choices, digital confidence, loyalty engagement, and access to alternatives. Simulate how disruption information and recovery choices affect trust and repeat intent. Keep the existing Kestrel dossier’s two-base strike and decision menu as the governing facts unless the client itself changes to Pegasus.

## What the public sources say

### Scale and network

- Pegasus reports **43.3 million passengers in 2025**, an **87.7% load factor**, and an **average fleet of 124 aircraft** for 2025 in its 2026 Q1 investor presentation. Its fleet stood at **129 aircraft on 31 March 2026**. The same presentation shows **€1.275 billion ancillary revenue** for 2025 and ancillary revenue per passenger of **€29.5**. This supports modeling a carrier where optional services are commercially important, alongside ticket sales. [Pegasus 2026 Q1 investor presentation](https://www.pegasusinvestorrelations.com/medium/image/pgsus-2026-q1-investor-presentation_1617/view.aspx)
- Pegasus’s consumer network page describes a network of **54 countries and 156 scheduled destinations**, including 38 domestic destinations in Türkiye. Its sustainability page currently says 56 countries and 160 destinations. These pages may reflect different update dates or counting methods; use dated investor reports for historical numbers and don’t treat live web counters as a single consistent series. [Network](https://www.flypgs.com/en/useful-info/info-about-flights/our-network), [Sustainability overview](https://www.flypgs.com/en/sustainability)
- Pegasus’s public materials position Istanbul Sabiha Gökçen as its core hub, with domestic and international connections. For a Turkey scenario, a hub-and-spoke or connecting itinerary can make missed connections and alternative-flight availability more consequential than in a simple point-to-point model. Verify route-specific assumptions before encoding them. [Pegasus investor relations](https://www.pegasusinvestorrelations.com/en/)

### Low-cost offer and digital behaviors

- Pegasus describes its low-cost model as letting guests tailor travel to their needs. Its extras include seat selection, baggage, food, and flexible change/refund options; package combinations bundle some choices. [Travel extras](https://www.flypgs.com/en/useful-info/info-about-flights/travel-extras)
- Online check-in opens seven days before departure and closes 45 minutes before domestic departures and one hour before international / Northern Cyprus departures, with airport exceptions. Online check-in, app, website, counters, kiosks, and bag drop create distinct passenger journeys. [Check-in and airport services](https://www.flypgs.com/en/help-center)
- BolBol lets members earn points on flights and extras and redeem for tickets or services. Pegasus says tickets bought through online travel agencies do not earn BolPoints (some add-ons booked directly can). BolBol Extra adds benefits after qualifying thresholds, including a free cancellation/change right, discounted baggage, and extra points. This gives the simulation meaningful variation in loyalty familiarity, booking channel, and perceived value of credits versus flexibility. [BolBol FAQ](https://www.flypgs.com/en/useful-info/other-info/frequently-asked-questions), [BolBol rewards](https://www.flypgs.com/en/bolbol/what-is-bolbol)

### Customer rights in Türkiye

- SHGM’s SHY-YOLCU regulation governs minimum passenger rights for covered flights. SHGM’s passenger page describes rights around denied boarding, cancellation, and delay, including service, refund or rerouting, and in some circumstances compensation. Exact eligibility depends on the situation and the current regulation; this is not discretionary goodwill. [SHGM passenger rights](https://web.shgm.gov.tr/tr/yolcular-icin/3889-index), [SHY-YOLCU regulation (PDF)](https://web.shgm.gov.tr/documents/sivilhavacilik/files/mevzuat/SHY-YY.pdf)
- SHGM directs passengers to complain to the airline first; if the airline does not answer within six weeks or the passenger is dissatisfied, they may submit a complaint to SHGM for covered issues. This can inform “knows rights / willing to escalate / channel choice” attributes, but the simulation should not make legal determinations from a persona prompt. [SHGM complaint process](https://web.shgm.gov.tr/tr/s/3935-sikayet-formu)

## How to use this in the simulated airline

### 1. Add useful persona dimensions

Use these as fixed attributes or narrative details, with plausible variation rather than stereotypes:

| Dimension | Why it matters in an airline simulation | Example values |
|---|---|---|
| Trip purpose and urgency | A missed flight has different costs for a family visit, holiday, exam, or work trip. | family visit, leisure, work, education/medical appointment |
| Flexibility and alternatives | Captures ability to accept a later flight, another airport, another carrier, or cancel. | fixed date / some flexibility; low / medium / high alternatives |
| Price sensitivity and budget pressure | Makes fare changes, refunds, add-ons, and replacement tickets consequential. | low / medium / high; tight budget flag |
| Add-on profile | Models low-cost product choices and perceived fairness. | cabin bag only; checked bag; paid seat; meal; flexible bundle |
| Booking and contact channel | Direct app users may receive or act on messages differently from agency customers. | airline app/site; OTA; travel agency; phone |
| Digital confidence and access | A digital rebooking offer only helps a passenger who can receive and complete it. | confident app user; needs help; limited connectivity |
| Loyalty relationship | Points matter to some travelers but may feel irrelevant during urgent disruption. | non-member; occasional points user; engaged tier member |
| Connection / airport complexity | Hub transfers and alternative airports can change the impact of delays. | direct; domestic connection; international connection; airport transfer needed |
| Baggage and assistance needs | Affects airport queue exposure and who bears extra friction during handling disruptions. | no checked bag; checked bag; travelling with children; requests mobility assistance |
| Rights awareness and trust | Shapes expectations for rerouting, refund, compensation, and escalation. | low / medium / high awareness; prior claim experience |

Use only traits that change choices or outcomes. Don’t add nationality, ethnicity, religion, health, or income beyond what is necessary to represent the concrete travel constraint. Assistance needs can be modeled as an operational requirement without inventing a diagnosis.

### 2. Give personas believable choices

Have the LLM decide among actions that a passenger could actually take: check the app, wait, contact support, accept rerouting, request a refund, buy a replacement ticket, switch carrier, travel with cabin baggage only, ask family for help, or complain. Anchor choices in the persona’s trip constraints, budget, prior experience, trust, and the information that reached them. Keep the final status output machine-readable, but do not script the outcome from the persona label.

### 3. Make the world model reflect low-cost trade-offs

- Separate base fare from optional services in persona profiles and revenue interpretation.
- Treat a points bonus, travel credit, cash refund, free change, and useful reroute as different offers; ask personas which one actually solves their problem.
- Model direct digital messages as available only if the passenger has usable contact details / app access; agency-booked passengers may have a different service path.
- During disruption, include queues and uncertainty as well as flight cancellation. A flight can operate while passengers still face baggage, connection, accessibility, or communication failures.
- Keep safety and statutory rights outside experimental trade-offs. Simulate service choices only after required rights are met.

### 4. Improve the measurement plan

Alongside the board’s required goals, track by persona segment:

- completion time to rebook, refund, or reach a confirmed next step;
- share accepting the first offered recovery option;
- lost-trip / self-rebook / carrier-switch behavior;
- trust, fairness, and next-booking intent;
- complaints and escalation channel;
- ancillary revenue at risk or preserved, clearly separated from ticket revenue;
- differences for checked-bag travelers, connections, families, agency bookings, and assistance requests.

Report ranges and segment counts, not just one aggregate average. A tiny persona group should not imply precise population estimates. The personas show plausible mechanisms and trade-offs; they do not predict Pegasus customer counts or actual operational performance.

## What transfers to Kestrel, and what does not

**Transfers well:** low-cost fare/add-on trade-offs; direct versus agency booking; app and self-service capability; the importance of trip urgency, baggage, flexibility, and loyalty; the tension between affordable fares and disruption recovery; customer-rights awareness.

**Does not transfer without evidence:** Pegasus’s passenger volume, fleet, load factor, route map, hub concentration, Türkiye-specific regulations, customer demographics, disruption rates, revenue or cost assumptions, and recovery capacity. Kestrel’s Orlando/Philadelphia footprint and known contractor strike remain its own scenario facts. If the team is actually switching the client to Pegasus, first replace the Kestrel dossier, geography, legal baseline, dates, metrics, and action menu rather than relabeling existing assumptions.

## Recommended next step for the team

Keep Kestrel as the simulation client and use the dimensions above to strengthen the existing personas and customer journey. Add a clearly labeled “Pegasus-inspired design rationale” to `TEAM_DOC.md`; cite public sources and state that Pegasus provides an industry reference, not a source for Kestrel’s numeric distributions. If time permits, make one small experiment that compares a flexibility/rebooking offer against a points or credit offer for passengers with fixed versus flexible trips.

## Sources

1. Pegasus Airlines, [2026 Q1 Investor Presentation](https://www.pegasusinvestorrelations.com/medium/image/pgsus-2026-q1-investor-presentation_1617/view.aspx).
2. Pegasus Airlines, [Our Network](https://www.flypgs.com/en/useful-info/info-about-flights/our-network).
3. Pegasus Airlines, [Sustainability overview](https://www.flypgs.com/en/sustainability).
4. Pegasus Airlines, [Help Center: check-in and airport services](https://www.flypgs.com/en/help-center).
5. Pegasus Airlines, [Travel extras](https://www.flypgs.com/en/useful-info/info-about-flights/travel-extras).
6. Pegasus Airlines, [BolBol FAQ](https://www.flypgs.com/en/useful-info/other-info/frequently-asked-questions), and [BolBol rewards](https://www.flypgs.com/en/bolbol/what-is-bolbol).
7. Türkiye SHGM, [Passenger rights](https://web.shgm.gov.tr/tr/yolcular-icin/3889-index), [SHY-YOLCU regulation](https://web.shgm.gov.tr/documents/sivilhavacilik/files/mevzuat/SHY-YY.pdf), and [complaint process](https://web.shgm.gov.tr/tr/s/3935-sikayet-formu).
