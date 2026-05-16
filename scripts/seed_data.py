"""
Seed the Anomaly Wiki database with S.T.A.L.K.E.R.-themed records.

Usage (backend stack must be running):
    python scripts/seed_data.py
    python scripts/seed_data.py --gateway http://localhost:8000 --opensearch http://localhost:9200
"""

import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request
import json

GATEWAY = "http://localhost:8000"
OPENSEARCH = "http://localhost:9200"
OPENSEARCH_INDEX = "anomaly-wiki-pages"
SEED_EMAIL = "seed@zone.int"
SEED_PASSWORD = "stalker2026"

# ---------------------------------------------------------------------------
# S.T.A.L.K.E.R. page data – 2 entries per type
# ---------------------------------------------------------------------------
PAGES = [
    # ── Anomaly ──────────────────────────────────────────────────────────────
    {
        "slug": "gravity-funnel",
        "type": "Anomaly",
        "visibility": "Public",
        "title": "Gravity Funnel",
        "summary": "A self-sustaining gravitational vortex concentrated in a 3–4 m radius, capable of compressing organic matter to a fraction of its original volume.",
        "tags": ["gravimetric", "lethal", "cordon", "tier-4"],
        "content": """## Classification
**Threat tier:** IV — Lethal
**Zone region:** Cordon, Garbage
**Discovery date:** 2006-04-26

## Description
The Gravity Funnel is one of the Zone's most studied and most feared anomalies. It manifests as an invisible, near-spherical gravitational singularity that draws all matter within a 3–4 m radius toward its centre at accelerating velocity. Objects reaching the core are compressed with forces estimated at 40–80 kN/m².

Visually the anomaly is detectable only by the spiral distortion it induces on loose debris — dust, leaves, and scraps of metal perpetually orbit its periphery in a slow gyre. At night, faint bioluminescent discharge is sometimes observed at the compression point.

## Hazard profile
- **Entry threshold:** Any mass crossing ~1.5 m from centre accelerates uncontrollably.
- **Lethal radius:** 0.8 m from core; no recorded survival beyond this point without Compass artifact.
- **Evasion:** Anomaly drifts 0.3–1.2 m/h in unpredictable direction. Bolts thrown ahead of each step remain the standard detection method.

## Research notes
Gravity Funnel cores have yielded two artifact types on record: **Soul** and **Gravi**. Extraction requires a Nimble-class suit rated for 12+ kgf lateral stress and a minimum two-person team with signal cord.

> *"I watched Petrenko walk into one during a smoke break. Not a scream. Just gone."*
> — Field note, Cordon outpost Zulu-3, 2024
""",
    },
    {
        "slug": "electric-blossom",
        "type": "Anomaly",
        "visibility": "Public",
        "title": "Electric Blossom",
        "summary": "A cluster anomaly emitting erratic electrostatic discharges up to 180 kV; named for the corona flower-pattern visible at night.",
        "tags": ["electrostatic", "cluster", "wildlands", "tier-3"],
        "content": """## Classification
**Threat tier:** III — Severe
**Zone region:** Wildlands, Rostok industrial
**Discovery date:** 2007-11-03

## Description
Electric Blossoms present as dense clusters of electrostatic field nodes spaced 0.4–1.8 m apart. Each node discharges independently on a 2–8 second cycle, producing branching arc patterns up to 180 kV. The discharge arcs between adjacent nodes, creating dynamic corridors of safe passage that shift on every cycle.

The anomaly derives its name from the visual effect observed after dark: each node emits a pale violet corona that collectively resembles a blossoming flower when viewed from elevation.

## Hazard profile
- **Primary hazard:** Electrocution. Standard body armour provides negligible protection.
- **Secondary hazard:** Induced cardiac arrhythmia at sub-lethal exposure.
- **Detection:** Geiger counters are unresponsive. Electromagnetic field probes (EMF-3 grade or above) reliably map node positions.

## Research notes
Extended proximity — without direct contact — correlates with artifact formation in the adjacent soil layer. The **Flash** and **Sparkler** artifacts are both harvested exclusively from Electric Blossom fields.

Stalkers working the Rostok cluster report that a discharged node takes exactly 6 seconds to recharge. Timing a crossing to pass through immediately after a discharge gives roughly 4 seconds of margin.
""",
    },

    # ── Artifact ──────────────────────────────────────────────────────────────
    {
        "slug": "artifact-soul",
        "type": "Artifact",
        "visibility": "Public",
        "title": "Soul",
        "summary": "A luminescent gravitational artifact that accelerates cellular regeneration in surrounding tissue. High demand; extreme extraction risk.",
        "tags": ["artifact", "gravimetric", "healing", "tier-2"],
        "content": """## Classification
**Origin anomaly:** Gravity Funnel
**Rarity:** Rare
**Institute designation:** GA-7 "Soul"

## Physical description
The Soul is a near-perfectly spherical object, approximately 4 cm in diameter, with an inner glow that shifts between deep amber and pale gold over a 12-second cycle. Surface texture is glass-smooth with faint concentric micro-banding. Mass is anomalously low for its apparent density: 18 g.

## Properties
| Property | Value |
|---|---|
| Radiation emission | 0.02 µSv/h (negligible) |
| Regenerative field radius | 0.6 m |
| Healing rate boost | +35% baseline |
| Shelf-life (outside Zone) | Indefinite if stored in lead-lined container |

## Effects
Continuous proximity to the Soul measurably accelerates clotting and cellular repair. Field medics in several stalker factions prize it above all pharmaceutical supplies for treating blunt-force trauma and radiation burns.

**Negative effect:** Prolonged unshielded exposure (>72 h) causes progressive hyperosteogenesis — abnormal bone density increase — in the carrier's extremities.

## Extraction
Recovery from a Gravity Funnel requires compression-rated equipment and careful timing. The artifact forms at the anomaly's core and must be extracted with a modified Wrenching Tool before the next gravitational pulse cycle (approximately every 4 minutes).
""",
    },
    {
        "slug": "artifact-compass",
        "type": "Artifact",
        "visibility": "Public",
        "title": "Compass",
        "summary": "A gravitational counter-artifact that negates inward acceleration, enabling safe traversal of Gravity Funnel anomalies.",
        "tags": ["artifact", "gravimetric", "navigation", "protective", "tier-3"],
        "content": """## Classification
**Origin anomaly:** Gravity Funnel (secondary formation)
**Rarity:** Very Rare
**Institute designation:** GA-12 "Compass"

## Physical description
A flattened ovoid approximately 6 × 4 cm, gun-metal grey with a faint iridescent sheen. A thin groove bisects the equator. The artifact slowly rotates in free suspension to align its long axis with the nearest gravitational anomaly — the behaviour that gives it its name.

## Properties
| Property | Value |
|---|---|
| Radiation emission | 0.08 µSv/h |
| Gravitational resistance | Reduces anomaly pull by ~80% on carrier |
| Magnetic interference | Strong — disrupts compass needles within 1.5 m |
| Weight | 94 g |

## Effects
A stalker carrying the Compass inside a Gravity Funnel experiences markedly reduced inward acceleration, enabling controlled movement and extraction of other artifacts from the anomaly core. The effect does not fully negate the pull at the innermost radius, but it extends survival time from seconds to minutes.

**Warning:** Two Compass artifacts carried simultaneously do not double the effect; they interfere destructively and cancel most of the protection.

## Known recoveries
Fewer than thirty confirmed Compass artifacts have been catalogued by Institute field teams since 2009. All known specimens originated from deep-tier Gravity Funnels in the Cordon and Garbage regions.
""",
    },

    # ── Location ──────────────────────────────────────────────────────────────
    {
        "slug": "red-forest",
        "type": "Location",
        "visibility": "Public",
        "title": "Red Forest",
        "summary": "A dense woodland north of the Chernobyl NPP where elevated radiation has stained the pine canopy a permanent auburn-red. One of the Zone's most dangerous transit corridors.",
        "tags": ["location", "high-radiation", "north-zone", "mutant-dense"],
        "content": """## Overview
**Coordinates:** N 51°26′ E 30°06′
**Radiation index:** 4.2–18.6 R/h (variable by sub-zone)
**Access status:** Restricted — requires long-range suit and Geiger monitoring

## Description
The Red Forest is a 10 km² stand of Scots pine and silver birch that received the heaviest direct fallout from the 1986 reactor explosion. Absorbed radiation killed the trees and stained their bark and needles a distinctive rust-red, giving the area its name. In the decades since the Zone's formation, this contamination has been amplified to levels far beyond the original deposition.

The forest floor is a patchwork of anomaly clusters — primarily Whirligig, Burner, and Electro variants — interspersed with relatively safe corridors that shift after every emission event. No permanent stalker camps exist inside the forest; the closest established position is the **Forester's Cabin** on the southern edge.

## Sub-zones
| Sub-zone | Radiation | Primary hazard |
|---|---|---|
| Southern edge | 4–6 R/h | Anomaly clusters |
| Central grove | 8–14 R/h | Bloodsucker territory |
| Northern approach to NPP | 12–18 R/h | Poltergeist activity |

## Fauna
The Red Forest hosts some of the Zone's highest concentrations of Bloodsuckers, Pseudodogs, and Burer. The elevated radiation appears to accelerate mutation cycles; specimens recovered here show greater mass and aggression than counterparts elsewhere.

## Transit notes
The shortest route from Yantar to the NPP passes through the eastern Red Forest corridor. Experienced stalkers time this crossing for the 4–6 hour post-emission window when anomaly drift is most predictable.
""",
    },
    {
        "slug": "pripyat-downtown",
        "type": "Location",
        "visibility": "Public",
        "title": "Pripyat Downtown",
        "summary": "The abandoned city centre of Pripyat — a Soviet-era ghost town frozen at the moment of the 1986 evacuation, now heavily anomalous and contested by all major factions.",
        "tags": ["location", "urban", "pripyat", "contested", "monolith"],
        "content": """## Overview
**Coordinates:** N 51°24′ E 30°03′
**Radiation index:** 0.8–3.4 R/h (street level); higher in basement zones
**Access status:** Contested — active Monolith presence on upper floors

## Description
Pripyat was a purpose-built city of 49,000 residents constructed to house workers of the Chernobyl NPP. Evacuated within 36 hours of the 1986 explosion, it has been uninhabited ever since — and in the Zone's context, that vacancy is deceptive.

The downtown core — centred on the Palace of Culture, Hotel Polissya, and the main square — is the most hotly contested urban territory in the Zone. Monolith fighters hold the upper floors and rooftops; independent stalkers and Freedom units contest the ground level for access to underground transit routes toward the NPP.

## Key landmarks
- **Palace of Culture Energetyk** — five-storey entertainment complex; ground floor clear, upper floors active Monolith sniper positions.
- **Hotel Polissya** — sixteen storeys; roof emits anomalous electromagnetic signature; artifact spawns confirmed on floors 4 and 11.
- **Amusement park** — Ferris wheel and bumper cars; low radiation, moderate anomaly density; used as a neutral meeting point by some factions.
- **Pripyat bus station** — underground passages connect to Jupiter factory and beyond.

## Artifact activity
Multiple artifact types spawn throughout the downtown area, concentrated near the sports complex pool (Bubble, Jellyfish) and the hotel upper floors (Crystals). Post-emission sweeps within 2 hours are most productive.
""",
    },

    # ── Incident ──────────────────────────────────────────────────────────────
    {
        "slug": "incident-yantar-signal",
        "type": "Incident",
        "visibility": "Public",
        "title": "Yantar Signal Anomaly — October 2024",
        "summary": "An unidentified broadband radio signal originating from Lake Yantar disrupted all electronic equipment within a 2 km radius for 14 hours.",
        "tags": ["incident", "yantar", "electromagnetic", "signal", "2024"],
        "content": """## Incident summary
**Date:** 2024-10-14, 03:22–17:09 local
**Location:** Lake Yantar and 2 km radius
**Classification:** Electromagnetic anomaly event
**Casualties:** None confirmed; 3 researchers disoriented, 1 equipment loss

## Timeline
| Time | Event |
|---|---|
| 03:22 | Mobile lab detects broadband signal, 0.3–900 MHz range |
| 03:31 | All GPS and radio equipment within 800 m ceases function |
| 04:15 | Expansion radius confirmed at 2 km; Ecologist camp loses power |
| 07:00–14:00 | Signal stable; psi-emitter readings elevated 340% above baseline |
| 17:09 | Signal ceases instantaneously; all equipment resumes normal function |

## Observed effects
- Complete radio blackout across all frequencies below 1 GHz
- Solid-state memory devices in the 2 km zone suffered 12–40% data corruption
- Three researchers reported auditory hallucinations during the peak intensity window (09:00–12:00)
- Anomaly density in Yantar increased measurably for 72 hours post-event

## Current assessment
The signal profile does not match any known natural Zone phenomenon. Cross-referencing with archived Psi-emission signatures from the Brain Scorcher event suggests a possible resonance effect involving the submerged laboratory structures beneath the lake. Investigation ongoing.

**Next action:** Institute requests deep-scan sonar survey of the lake bed; scheduled Q1 2025.
""",
    },
    {
        "slug": "incident-bloodsucker-village-attack",
        "type": "Incident",
        "visibility": "Public",
        "title": "Bloodsucker Pack Incursion — Krasnolesye Outpost",
        "summary": "A coordinated pack of eleven Bloodsuckers breached the perimeter of Krasnolesye outpost during a blowout, resulting in four fatalities and the loss of a forward observation post.",
        "tags": ["incident", "bloodsucker", "krasnolesye", "mutant-attack", "2025"],
        "content": """## Incident summary
**Date:** 2025-03-02, 21:44–23:17 local
**Location:** Krasnolesye outpost, northern perimeter
**Classification:** Hostile fauna incursion
**Casualties:** 4 KIA, 2 WIA, 1 observation post destroyed

## Background
Krasnolesye outpost maintains a four-point perimeter watch, with a two-person observation post (OP-North) positioned 120 m beyond the main fence line to provide early warning of movement from the Red Forest.

## Sequence of events
A Zone blowout was declared at 21:12. Standard protocol required recall of OP-North; the two-person team was en route when the blowout terminated early — an unusual occurrence subsequently logged as a secondary anomaly event.

In the 12 minutes between blowout termination and confirmation of the all-clear, a pack of eleven Bloodsuckers advanced from the northern treeline under cover of the post-blowout anomaly discharge. The pack, estimated at 6 adults and 5 juveniles, exploited the cloaking conditions — optical distortion from residual discharge masked their approach.

OP-North was overrun at 21:44. The main perimeter was breached at 22:01. Defenders engaged at close range in low-light conditions; four defenders were killed and two wounded before the pack was repelled with shotgun fire and grenades at 23:17.

## Post-incident review
- OP-North recalled too late relative to blowout termination
- Night-vision equipment unavailable to two of the four killed defenders
- Recommendation: mandatory NV issuance and perimeter floodlight installation

**Bloodsucker pack behaviour** during this incident — coordinated encirclement, use of cover, apparent communication — was documented by surviving witnesses as exceeding previously recorded pack intelligence levels. Tissue samples collected; forwarded to Institute xenobiology division.
""",
    },

    # ── Expedition ────────────────────────────────────────────────────────────
    {
        "slug": "expedition-northern-marshes-q2-2025",
        "type": "Expedition",
        "visibility": "Public",
        "title": "Northern Marshes Survey — Q2 2025",
        "summary": "A four-week mapping expedition to chart anomaly distribution and artifact yields in the Northern Marshes region following the February 2025 emission event.",
        "tags": ["expedition", "northern-marshes", "mapping", "q2-2025", "ecologists"],
        "content": """## Expedition brief
**Period:** 2025-04-07 — 2025-05-02
**Lead researcher:** Dr. V. Kovalenko (Ecologist faction)
**Team:** 6 researchers, 4 armed escort
**Mandate:** Post-emission anomaly mapping and artifact yield survey

## Objectives
1. Chart new anomaly formations in the Eastern Marsh sub-zone (grid refs. NM-4 through NM-9)
2. Compare artifact spawn density against pre-emission baseline (survey October 2024)
3. Collect water and soil samples from three designated monitoring points
4. Establish viability of Monitoring Station Bravo-7 for permanent occupation

## Findings summary

### Anomaly changes
The February emission substantially reorganised anomaly clusters in the eastern marsh. Seventeen previously mapped Whirligig clusters have shifted an average of 340 m northward. Four new Electro clusters were identified with no prior analogue. The safe transit corridor from Checkpoint Vega to Bravo-7 is no longer viable via Route Alpha; Route Delta is now recommended.

### Artifact yields
| Type | Q4 2024 | Q2 2025 | Change |
|---|---|---|---|
| Bubble | 14 | 22 | +57% |
| Jellyfish | 9 | 9 | 0% |
| Nightstar | 3 | 8 | +167% |
| Crystal Thorn | 0 | 4 | new |

### Station Bravo-7
Structure is intact. Radiation inside is 0.4 R/h — within acceptable limits for 30-day rotations with standard equipment. Power restoration feasible via portable generator. Recommended for reoccupation subject to perimeter anomaly clearance.

## Incidents
One team member (A. Moroz) treated for moderate radiation exposure on day 11 after deviation from planned route. No hostile fauna contact. Two Pseudodog sightings at range; no engagement.
""",
    },
    {
        "slug": "expedition-dead-city-recon-2024",
        "type": "Expedition",
        "visibility": "Public",
        "title": "Dead City Reconnaissance — November 2024",
        "summary": "A rapid 72-hour reconnaissance of the Dead City district to assess Monolith defensive positions and identify potential artifact caches ahead of a planned Freedom offensive.",
        "tags": ["expedition", "dead-city", "recon", "freedom", "monolith", "2024"],
        "content": """## Expedition brief
**Period:** 2024-11-18 — 2024-11-21
**Lead:** Sergeant O. Bondarenko (Freedom faction)
**Team:** 3 scouts
**Mandate:** Intelligence gathering — Monolith positions and artifact cache locations

## Mission parameters
This was a non-contact reconnaissance tasked by Freedom command ahead of Operation Clear Sky II. The team carried minimal equipment to maximise mobility: SEVA suits, suppressed SR-25 rifles, and two days' rations.

## Route and observations

### Day 1 (18 Nov)
Entry via the drainage channel on the southern approach. Three Monolith positions confirmed on the main avenue — two ground-level machine gun emplacements and one sniper position in the cinema tower. Estimated eight combatants total in the southern block.

### Day 2 (19 Nov)
Overnight observation of northern block. Patrol pattern: four-hour rotation, two-person pairs. A cache of approximately 30 Bubble artifacts was observed in a basement access point at grid ref DC-7-Alpha, left unguarded during the 02:00–04:00 window.

### Day 3 (20 Nov)
Extraction via northern drainage. Contact with single Monolith scout; evaded without engagement.

## Intelligence delivered
- Monolith strength in Dead City: 24–30 combatants
- Three confirmed cache positions
- Patrol rotation schedule provided to Freedom operations

## Outcome
Data used to plan Operation Clear Sky II (executed December 2024). Freedom forces recovered two of three identified caches. Bondarenko commended; team extracted without casualties.
""",
    },

    # ── Researcher Note ───────────────────────────────────────────────────────
    {
        "slug": "note-anomaly-drift-patterns",
        "type": "Researcher Note",
        "visibility": "Public",
        "title": "Field Note: Anomaly Drift Patterns Post-Emission",
        "summary": "Observations on the consistent northward drift of gravitational and thermal anomalies following Zone emission events, with a proposed predictive model.",
        "tags": ["researcher-note", "anomaly", "emission", "drift", "theory"],
        "content": """## Author
Dr. I. Shevchuk, Institute Field Research Division
*Submitted: 2025-01-09*

---

## Observation
Over 14 monitored emission events between 2022 and 2024, I have recorded the post-event displacement of 47 gravitational and thermal anomaly clusters in the Cordon and Garbage regions. The data reveals a statistically significant pattern: **87% of displaced clusters move in a northward or north-northeast direction** within the first 48 hours following an emission.

Mean displacement distance: **280 m** (σ = 94 m)
Mean displacement bearing: **N 22° E** (σ = 18°)

## Proposed mechanism
The Zone's magnetic anomaly — documented since 2008 — creates a persistent field gradient that intensifies post-emission. I propose that anomaly clusters, which appear to have a weak electromagnetic coupling with the substrate, are dragged along this gradient in the manner of a charged particle in a non-uniform field.

If this model holds, anomaly positions can be predicted 48 hours post-emission with approximately ±120 m accuracy by applying the mean displacement vector to the last-known position.

## Implications for field operations
- Transit maps should be considered unreliable for 48–72 hours following any emission
- Search operations for newly spawned artifacts should prioritise areas 200–400 m north of known anomaly cluster positions
- Permanent installations should avoid siting within 500 m north of known clusters if the region is within 30 km of the NPP epicentre

## Limitations
Sample size is limited to two sub-regions. Replication in the Wildlands and Yantar zones is needed. Additionally, the mechanism proposed is speculative and should not be cited as established theory pending peer review.
""",
    },
    {
        "slug": "note-bloodsucker-cloaking-mechanism",
        "type": "Researcher Note",
        "visibility": "Public",
        "title": "Field Note: Bloodsucker Optical Cloaking — Tissue Analysis",
        "summary": "Preliminary analysis of skin chromatophore structures in two Bloodsucker specimens, proposing a biophotonic mechanism for their visual cloaking ability.",
        "tags": ["researcher-note", "bloodsucker", "biology", "cloaking", "xenobiology"],
        "content": """## Author
Dr. A. Petrenko, Institute Xenobiology Division
*Submitted: 2025-02-28*

---

## Background
The Bloodsucker's ability to render itself visually transparent has been observed since the early Zone expeditions. No satisfactory mechanistic explanation has been published. Following the Krasnolesye incident (see incident report KR-2025-03), tissue samples from three neutralised specimens were made available. This note summarises preliminary findings.

## Method
Skin sections from dorsal and lateral surfaces were examined under electron microscopy. Biochemical staining was performed for photopigment markers. Samples were also tested for bioluminescent activity.

## Findings

### Chromatophore distribution
Bloodsucker skin contains chromatophores at a density of approximately 12,000/cm² — roughly four times the density found in cephalopod skin, the terrestrial benchmark for active camouflage. The cells contain multiple pigment vesicles and show evidence of rapid vesicle repositioning via actin-myosin contractile units.

### Photonic layering
Beneath the chromatophore layer is a previously undescribed structure: a tessellated array of guanine microplatelets arranged at angles that vary by body region. This is functionally analogous to the iridophore layer in cephalopods but with a significantly more complex geometry.

### Proposed mechanism
The chromatophores actively sample ambient light via photoreceptors on the outer membrane, compute a real-time approximation of the background, and redistribute pigment to project a counter-image on the skin surface. The guanine layer functions as a beam-director, ensuring the projected pattern is coherent from multiple viewing angles simultaneously.

## Limitations and open questions
- How the computation occurs — whether neural or distributed — is unknown
- The cloaking fails under ultraviolet illumination (practical implication: UV torches are effective countermeasures)
- Energy cost of sustained cloaking has not been estimated

## Recommendation
UV-spectrum flashlights should be issued as standard equipment to all field teams operating in Bloodsucker territory.
""",
    },

    # ── Article ───────────────────────────────────────────────────────────────
    {
        "slug": "article-zone-emission-primer",
        "type": "Article",
        "visibility": "Public",
        "title": "Zone Emissions: A Primer for New Researchers",
        "summary": "An introductory guide to Zone emission events — what they are, how to predict them, and how to survive them.",
        "tags": ["article", "emission", "guide", "safety", "primer"],
        "content": """# Zone Emissions: A Primer for New Researchers

Zone emissions are periodic, Zone-wide atmospheric discharge events that represent the single greatest equaliser of stalker mortality. Experienced veterans and first-week rookies die in emissions with roughly equal frequency when caught unprepared. This article is intended for researchers new to Zone fieldwork.

---

## What is an emission?

An emission is a simultaneous release of anomalous energy across the entire Zone, originating from an epicentre in or beneath the Chernobyl NPP. The event typically lasts 4–18 minutes and is characterised by:

- A visible crimson-orange wave propagating outward from the NPP at approximately 40 km/h
- Lethal exposure to unshielded individuals caught in the open — death within 90 seconds of wave contact
- Massive reorganisation of anomaly clusters throughout the Zone
- Accelerated artifact formation in the 2–6 hours following the event

Emissions occur with no regular schedule. Intervals range from 6 hours to several weeks. No reliable long-range prediction method exists; all warnings are short-range (< 20 minutes).

---

## Warning signs

Experienced stalkers recognise several precursors:

1. **Geiger counter spike** — Background radiation rises sharply 5–15 minutes before an emission.
2. **Anomaly agitation** — Established anomaly clusters become visually unstable; Whirligigs accelerate, Burners pulse irregularly.
3. **Fauna behaviour** — Animals flee toward structures. A sudden absence of mutant activity is considered a reliable warning sign.
4. **Radio interference** — Communication channels degrade. Many faction radios carry an automatic emission-warning tone broadcast by monitoring stations.

---

## Shelter protocols

Any solid structure provides adequate protection if:
- You are fully inside (no open windows or doors facing the wave)
- You remain inside for the full duration plus a 3-minute margin

**Do not** shelter in:
- Vehicles with broken windows
- Open drainage ditches or foxholes
- Structures with collapsed roofs

Most stalker casualties occur when individuals attempt to reach shelter after the wave is already visible. **If you can see the wave, shelter must already be within 30 seconds' sprint.** Prioritise proximity over quality of shelter.

---

## Post-emission

The 2 hours following an emission are among the most productive and most dangerous in the Zone:

- Anomaly clusters are displaced and unpredictable — routes you trust are unverified
- Artifact spawn rates are elevated; competition from other stalkers increases
- Dazed or injured mutants may behave erratically

Recommended procedure: remain in shelter for 15 minutes post-emission, perform a brief perimeter check with bolts, then proceed with heightened caution.
""",
    },
    {
        "slug": "article-factions-overview",
        "type": "Article",
        "visibility": "Public",
        "title": "Factions of the Zone: An Overview",
        "summary": "A concise reference guide to the major factions operating within the Zone — their goals, territories, and relations with independent researchers.",
        "tags": ["article", "factions", "guide", "politics", "lore"],
        "content": """# Factions of the Zone: An Overview

Understanding the Zone's political landscape is as important to survival as anomaly awareness. Faction affiliation determines access to safe houses, trade networks, and medical support. This article provides a neutral summary of each major group.

---

## Loners (Free Stalkers)

The largest informal grouping in the Zone, Loners are independent operators bound by no organisation. Collectively they share information, trade supplies, and maintain a loose code of mutual aid — but there is no hierarchy, no command structure, and no formal membership.

**Territory:** Cordon, Garbage, southern Rostok
**Relations with researchers:** Generally cooperative; information exchange common

---

## Duty (Dolg)

A paramilitary faction holding that the Zone is an existential threat that must be contained. Duty maintains strict hierarchy, military discipline, and a standing agreement with Ukrainian government forces to limit Zone expansion. They control key chokepoints and impose order with force.

**Territory:** Rostok, Agroprom
**Relations with researchers:** Cooperative if accredited; hostile to unsanctioned entry

---

## Freedom (Svoboda)

Ideologically opposed to Duty: Freedom holds that the Zone belongs to no government and that its secrets should be freely accessible to all humanity. Anarchist in structure; funded primarily by artifact sales to Western buyers.

**Territory:** Wildlands, Dead City approaches
**Relations with researchers:** Cooperative; particularly welcoming to academics

---

## Ecologists

A research faction operating under nominal Institute affiliation. Ecologists are primarily scientists and support personnel; they maintain fortified laboratories and hire stalker escorts for field operations.

**Territory:** Yantar, Limansk research complex
**Relations with researchers:** Natural allies; best source of equipment and medical supplies

---

## Monolith

A fanatical faction devoted to reaching and protecting the Zone's centre — the Monolith, as they call it. Members exhibit signs of severe psychological alteration; most appear incapable of negotiation or surrender. Origin and organisation remain poorly understood.

**Territory:** Pripyat, NPP approaches, Chernobyl-2
**Relations with researchers:** Hostile on sight

---

## The Institute

Not a Zone faction per se, but the primary civilian authority conducting research. The Institute funds Ecologist operations, maintains the Anomaly Wiki (this system), and coordinates with Duty for safe-zone establishment. Field researchers operating under Institute credentials receive guaranteed extraction in most Duty and Loner territories.
""",
    },
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def get(url: str, token: str | None = None) -> dict:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {url}: {e.read().decode()}") from e


def put(url: str, body: dict) -> None:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="PUT")
    try:
        with urllib.request.urlopen(req):
            pass
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {url}: {e.read().decode()}") from e


def index_page(opensearch: str, page: dict, revision: dict, tags: list[str]) -> None:
    page_id = page["id"]
    doc = {
        "page_id":      page_id,
        "slug":         page["slug"],
        "type":         page["type"],
        "status":       page["status"],
        "visibility":   page["visibility"],
        "tags":         tags,
        "title":        revision["title"],
        "summary":      revision["summary"],
        "content_text": revision["content"],
        "aliases":      [],
    }
    url = f"{opensearch}/{OPENSEARCH_INDEX}/_doc/{page_id}"
    put(url, doc)


def post(url: str, body: dict, token: str | None = None, form: bool = False) -> dict:
    data = (urllib.parse.urlencode(body) if form else json.dumps(body)).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} {url}: {body_text}") from e


def get_token(base: str) -> str:
    print(f"  Registering seed account ({SEED_EMAIL})…")
    try:
        post(f"{base}/auth/register", {"email": SEED_EMAIL, "password": SEED_PASSWORD})
        print("  Account created.")
    except RuntimeError as e:
        if "400" in str(e) or "409" in str(e):
            print("  Account already exists, continuing.")
        else:
            raise

    print("  Logging in…")
    resp = post(f"{base}/auth/login", {"username": SEED_EMAIL, "password": SEED_PASSWORD}, form=True)
    token = resp["access_token"]
    print("  Token obtained.")
    return token


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

def seed(base: str, opensearch: str) -> None:
    print(f"\nTarget: {base}  |  OpenSearch: {opensearch}\n")

    token = get_token(base)

    counts: dict[str, int] = {}
    skipped = 0
    created = 0

    for p in PAGES:
        slug = p["slug"]
        ptype = p["type"]
        print(f"  [{ptype}] {slug} … ", end="", flush=True)

        try:
            result = post(
                f"{base}/pages",
                {
                    "slug": slug,
                    "type": ptype,
                    "visibility": p["visibility"],
                    "title": p["title"],
                    "summary": p["summary"],
                    "content": p["content"],
                },
                token=token,
            )
        except RuntimeError as e:
            if "409" in str(e):
                print("already exists, re-indexing… ", end="", flush=True)
                try:
                    state = get(f"{base}/pages/slug/{slug}", token=token)
                    existing_page = state["page"]
                    existing_rev = state.get("current_published_revision") or state.get("current_draft_revision")
                    if existing_rev:
                        index_page(opensearch, existing_page, existing_rev, p.get("tags", []))
                        print("indexed.")
                    else:
                        print("no revision found, skipped.")
                except Exception as ie:
                    print(f"failed ({ie}).")
                skipped += 1
                continue
            raise

        page_id = result["page"]["id"]
        revision_id = result["revision"]["id"]
        version = result["page"]["version"]

        publish_result = post(
            f"{base}/pages/{page_id}/publish",
            {"revision_id": revision_id, "expected_page_version": version},
            token=token,
        )

        published_revision = publish_result.get("current_published_revision") or result["revision"]
        index_page(opensearch, result["page"], published_revision, p.get("tags", []))

        print("created, published, indexed.")
        created += 1
        counts[ptype] = counts.get(ptype, 0) + 1

    print(f"\nDone. {created} pages created, {skipped} skipped (already existed).")
    if counts:
        for t, n in sorted(counts.items()):
            print(f"  {t}: {n}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Anomaly Wiki with STALKER mock data.")
    parser.add_argument("--gateway", default=GATEWAY, help=f"API Gateway base URL (default: {GATEWAY})")
    parser.add_argument("--opensearch", default=OPENSEARCH, help=f"OpenSearch base URL (default: {OPENSEARCH})")
    args = parser.parse_args()
    try:
        seed(args.gateway, args.opensearch)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
