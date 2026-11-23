---
name: preliminary-lighting-design
description: Preliminary indoor lighting design (lumen method, NBCS 2026 criteria, ECSBC 2024 power and control checks) when the user explicitly asks for one and no lighting layout exists - derives provisional fixture counts and layouts per room and hands them to the electrical measurement skill. Do not use when a lighting layout or luminaire schedule is supplied.
---

# Preliminary lighting design

Use this skill only when the user asks for a preliminary lighting design, for example "estimate the lighting for this floor plan, no electrical drawings yet". When a lighting layout or luminaire schedule exists, measure from it with the `electrical-measurement-estimation` skill instead.

Read a linked reference as an MCP resource, or with `describe_source section=<its gestimator:// link>`. Record the design results through the electrical measurement skill as GEstimator measurements, not in a separate spreadsheet. Use the criteria in this skill; do not search the web for lighting standards. For a room type the table does not list, follow section 2.

Every output of this skill is **provisional**. It is a planning estimate, not a lighting design for construction. Say so in the draft, and keep the assumptions with the quantities.

## 1. Inputs per room

| Input | Source | If missing |
|---|---|---|
| Room name, use and location | Plan, room schedule | Ask; the use decides the criteria |
| Length, width, ceiling height | Plan and section | Cannot size the room: list it as unresolved |
| Working plane height | Project criteria | 0.85 m above floor where the task height is not known; 0.75 m for industrial work places (NBCS 2026, Part D Section 1, 4.1.4.4) |
| Mounting (recessed, surface, suspended) and suspension length | Ceiling design | Assume recessed or surface at ceiling height |
| Surface reflectances (ceiling, walls, floor) | Finish schedule | Use the NBCS 2026 reflection factors (4.3.2.3(b)(2)): 0.7 white and very light colours, 0.5 light colours, 0.3 middle tints, 0.1 dark colours. Allow for windows, shelves and doors on the walls. Say which you assumed |
| Lighting criteria | Project brief, adopted code | Use the NBCS 2026 Table 6 middle value for the room use (section 2) |
| Luminaire data: type, wattage, luminous flux, utilisation factor table, maximum spacing to height ratio, CRI, UGR | Manufacturer datasheet, project luminaire schedule | Use a stated typical value and mark it provisional |
| Control intent (switch groups, sensors, daylight zones) | Brief, energy code | Assume manual switching per row parallel to the windows, plus the sensors ECSBC 2024 requires (section 4) |
| Energy code status | Brief: ECSBC 2024 applies to commercial and office buildings with a connected load of 100 kW or more, or a contract demand of 120 kVA or more, at the ECSBC, ECSBC+ or Super ECSBC level | Ask; it sets the power limit and the sensors |

## 2. Criteria

**National Building Construction Standards (NBCS) 2026, SP 7:2026, Part D Section 1, Table 6** gives, for each task or activity area, a range of maintained average illuminance Ēm with the minimum uniformity Uo, minimum colour rendering Ra and unified glare rating limit RUGL. For working interiors the **middle value** of the range is the recommended service illuminance (4.1.4.3). Use the higher value when the task has low contrast, errors are costly, visual work is critical, accuracy or productivity matters, or the workers' vision needs it (4.1.4.3.1). The lower value may be used when contrast is high, speed and accuracy are not important, or the task is occasional (4.1.4.3.2).

Examples from Table 6 (checked against the published text):

| Area (Table 6 ref.) | Ēm range, lux | Design (middle) | Uo | Ra | RUGL |
|---|---|---|---|---|---|
| Offices: writing, typing, reading (26.2) | 300-500-750 | 500 | 0.60 | 80 | 19 |
| Offices: private cabins (26.3) | 300-500-750 | 500 | 0.70 | 80 | 19 |
| Offices: CAD work stations (26.4) | 300-500-750 | 500 | 0.60 | 80 | 19 |
| Offices: conference and meeting rooms (26.6) | 300-500-750 | 500 | 0.60 | 80 | 19 |
| Offices: filing, copying (26.1) | 200-300-500 | 300 | 0.40 | 80 | 19 |
| Offices: reception desk (26.8) | 200-300-500 | 300 | 0.60 | 80 | 22 |
| Offices: archiving (26.9) | 150-200-300 | 200 | 0.40 | 80 | 25 |
| Offices: cloakroom, washroom (26.13) | 150-200-300 | 200 | 0.40 | 80 | 25 |
| Offices: corridors and circulation (26.18) | 75-100-150 | 100 | 0.40 | 70 | 28 |
| Offices: stairs, escalators (26.19) | 75-100-150 | 100 | 0.40 | 70 | 25 |
| Area in front of lifts and escalators (1.4) | 150-200-300 | 200 | 0.40 | 70 | - |
| Classroom, general activities (36.1) | 300-500-750 | 500 | 0.60 | 80 | 19 |
| Practical rooms and laboratories (36.14) | 300-500-750 | 500 | 0.60 | 80 | 19 |
| Teachers' rooms (36.22) | 200-300-500 | 300 | 0.60 | 80 | 19 |
| Library reading areas (36.24) | 300-500-750 | 500 | 0.60 | 80 | 19 |
| Surveillance station (3.3) | 200-300-500 | 300 | 0.60 | 80 | 19 |
| Plant rooms, switchgear rooms (3.1) | 150-200-300 | 200 | 0.40 | 80 | 25 |
| Canteens and break areas (2.1) | 150-200-300 | 200 | 0.40 | 80 | 22 |
| Resting rooms (2.2) | 75-100-150 | 100 | 0.40 | 80 | 22 |
| Cloakrooms, washrooms, toilets, showers (2.4) | 150-200-300 | 200 | 0.40 | 80 | 25 |
| Store and stockrooms (4.1) | 75-100-150 | 100 | 0.40 | 80 | 25 |
| Corridors and circulation areas (1.1) | 75-100-150 | 100 | 0.40 | 70 | 28 |
| Wards, general lighting (39.1) | 75-100-150 | 100 | 0.70 | 80 | 19 |
| Wards, reading lighting (39.2) | 200-300-500 | 300 | 0.70 | 80 | 19 |

**Rooms not listed.** Table 6 has no row for dormitories, barracks, hostels or other sleeping rooms, or for residences. Use the values for a similar, comparable situation (4.1.4.1(b)) and name the row you used. For example: a security post or guard office as a surveillance station (3.3); a dormitory or barrack as resting rooms (2.2) for general lighting, with reading lighting (39.2) at beds or desks where reading is expected. State the choice as an assumption for review.

Use NBCS 2026, the current code. Older documents give other values for some rooms: the CPWD Electrical Part I Internal 2023 specification refers to NBC 2016 Part 8 Section 1 (its Table 8: general offices 300-500-750, teaching spaces 200-300-500, corridors 50-100-150), and SP 30:2023, Part 3 Section 19, Table 1 gives single values (general offices 300 lux). Use an older value only when the contract adopts that document, and say so in the handoff.

## 3. Method (lumen method, NBCS 2026, 4.3.2)

For each room:

1. Mounting height above the working plane: `Hm = mounting height - working plane height`.
2. Room index (2.1.35): `kr = (L × W) / ((L + W) × Hm)`. Where L exceeds 5 × W, take L = 5W.
3. Utilisation factor `μ`: use the selected luminaire's photometric data for the room geometry and reflectances. If those data are unavailable, use the [typical CU reference](gestimator://skills/preliminary-lighting-design/references/typical-cu.md) for a comparable fitting at 70% ceiling, 50% wall and 20% effective floor-cavity reflectance. Look up CU by room cavity ratio (RCR). Record the fitting type, reflectances, RCR and the resulting CU as provisional inputs.
4. Maintenance factor `d` (2.1.26 defines it; NBCS gives no value). IS 3646 (Part 1):1992, 6.2.1, recommends a light loss factor of 0.8 for fairly clean interiors (offices, air-conditioned interiors), 0.7 for interiors that collect dust faster (most industrial interiors), and allows 0.6 for interiors highly prone to dirt. Use the luminaire's lumen maintenance data where given.
5. Number of luminaires (4.3.2.3(c)): `N = (Eav × A) / (μ × d × Φ)`, where Eav is the design illuminance (lux), A the working plane area (sqm) and Φ the luminous flux of one luminaire (lumens).
6. Round N up to a count that fits a regular grid. Recompute Eav for the chosen count and report it.
7. Layout (4.3.2.4): space luminaires about `x ≈ Hm` apart in each direction, with the end luminaires `0.5 x` from the wall. Where kr is less than 1, keep x below Hm; two or four luminaires usually suit such rooms. Do not exceed the datasheet's maximum spacing to height ratio.
8. Quality: check that the luminaire's CRI meets Ra and its UGR meets RUGL for the area. The lumen method gives the average only; the uniformity Uo needs a point calculation, so list it as unverified.
9. Load: connected load = N × wattage; lighting power density (LPD) = load / A. Compare it with the energy code (section 4).

Rooms with an irregular shape, high ceilings, strong daylight or special tasks need a point-by-point calculation or lighting software. Flag them instead of applying the lumen method.

## 4. Energy code checks (ECSBC 2024)

The Energy Conservation and Sustainable Building Code 2024 applies to commercial and office buildings with a connected load of 100 kW or more, or a contract demand of 120 kVA or more; residential buildings are not covered (Scope, 2). When it applies:

- **Lighting quantity and quality (7.2.1)** must comply with the latest IS 3646 (Part 1). Check that the NBCS 2026 values used agree with it for the room, or name the difference.
- **Lighting power (7.3.3, space function method, Table 7.4 for an ECSBC building):** business enclosed or open plan 10.0 W/sqm, conference and meeting 11.5, corridor 7.1, restroom 7.7, stairway 5.5, lobby 9.1, classroom 13.8, laboratory 15.1. ECSBC+ (Table 7.5) and Super ECSBC (Table 7.6) are lower, for example business 8.6 and 5.4 W/sqm. The building area method (7.3.2, Table 7.1) allows 9.5 W/sqm for an office building (7.6 for ECSBC+, 5.0 for Super ECSBC, Tables 7.2 and 7.3).
- **Automatic shutoff (7.2.2(a)):** at least 90 % of interior lighting by wattage needs a scheduled control (one schedule per 2,500 sqm and floor) or occupancy sensors that switch off or dim by at least 80 % within 15 minutes. Sensor-controlled fittings also need a wall-mounted manual switch.
- **Space control (7.2.2(b)1):** at least one control device per space enclosed by ceiling-height partitions, each controlling at most 250 sqm (spaces up to 1,000 sqm). In offices over 30 sqm, general lighting control zones are limited to 60 sqm.
- **Occupancy sensors (7.2.2(b)2):** required in all habitable spaces under 30 sqm enclosed by walls or ceiling-height partitions, storage and utility spaces over 15 sqm, public toilets over 25 sqm, hospitality corridors, and all conference and meeting rooms.
- **Daylight areas (7.2.2(c)):** luminaires within the daylight extent need a manual switch-off control or an automatic control (minimum 5 minute delay, switch off or dim to 10 %).
- **ECSBC+ and Super ECSBC (7.2.4):** a centralised lighting control system (switching, dimming and scheduling, occupancy feedback, failure feedback, energy monitoring).

A design over the power limit needs fewer or more efficient luminaires. The control clauses add sensors, switch groups and control zones, which change the point and equipment counts.

## 5. Decisions this design leaves open

The design gives fixture type, count, rating and layout. These quantities still depend on other decisions. List them as unresolved in the handoff:

- **Point counts:** depend on the switch grouping (each switch group gives one normal point; further fittings are group-controlled points under the CPWD counting rules).
- **Circuit and submain wiring lengths:** depend on DB locations, routing and the circuit capacity rule.
- **Sensors and dimming:** depend on the control strategy and the energy code.
- **Item choice:** the efficacy band, body construction and mounting accessory depend on the specification and energy code.
- **Uniformity and glare:** need a point calculation with real photometric data.
- **Emergency lighting:** not covered by this method.

## 6. Handoff to electrical measurement

Hand each room to the `electrical-measurement-estimation` skill as a record with these fields:

| Field | Example |
|---|---|
| Room / location | Office 1, first floor |
| Fixture type | LED panel 2×2 ft, recessed |
| Count | 6 |
| Rating | 36 W, about 4400 lm (provisional, no datasheet) |
| Control assumptions | 2 switch groups of 3 at the entrance, window row separately switched, one occupancy sensor (ECSBC 7.2.2(b)2) |
| Associated work | point wiring for 6 fittings, occupancy sensor, circuit wiring from the DB |
| Sources | Plan A-101 rev B (dimensions), NBCS 2026 Table 6 ref. 26.2 (criteria), stated assumptions |
| Unresolved inputs | DB location and route, luminaire datasheet, body construction, efficacy band in the specification |
| Status | Provisional (preliminary design) |

The electrical skill then counts points, matches items and records measurement lines. It keeps the status provisional.

A full example from room data to draft measurement and proposed schedule items: [worked example, office](gestimator://skills/preliminary-lighting-design/references/worked-example.md).

Standards status: [standards register](gestimator://skills/preliminary-lighting-design/references/standards.md).
