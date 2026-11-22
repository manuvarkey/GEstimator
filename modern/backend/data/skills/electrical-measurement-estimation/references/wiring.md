---
description: Point wiring, group and twin control counting, circuit/submain and socket wiring runs (CPWD Electrical Part I Internal 2023, 3.3-3.4), circuit capacity checks, and DSR (E&M) 2025 WIRING item selection.
---

# Wiring, points and sockets

Governing specification for DSR (E&M) work: **CPWD General Specifications for Electrical Works Part I Internal 2023** (released 12.07.2023). The clauses below were checked against that text. Follow the project specification where it differs. Other schedules may count points differently: read their notes and item descriptions.

## Inputs

- Lighting and power layouts with switch positions and control groups.
- Building type (it sets the point group).
- Conduit (steel or PVC, surface or recessed) and switch type (piano or modular).
- DB locations, the circuit schedule and the conduit routes, for circuit and submain runs.

## Points (unit Point)

- **Definition (3.4.1).** A point (other than a socket outlet point) is all the wiring from the controlling switch or MCB to the outlet: a ceiling rose or connector (fan points, prewired fittings, call bells), a ceiling rose for pendants, a back plate for stiff pendants, or a lamp holder for fittings that are not prewired.
- **Included in point wiring (3.4.2).** Conduit and wiring between the switch box and the outlet, loop protective earthing of each fixture, switch boxes and covers, outlet and junction boxes, the control switch or MCB, connections, and terminations. Where there is a false ceiling, the flexible metallic conduit from the ceiling junction box to the fitting is part of the point (Note to 3.4.2). Do not measure any of these separately.
- **Counted, not measured (3.4.3).** Light, fan, exhaust fan and call bell points are counted per unit, with no linear measurement, unless otherwise specified.
- **Group A, B, C follow the building type (3.4.4):** Group A for Type I, II and III residential quarters and hostels; Group B for Type IV and above quarters and barracks; Group C for all non-residential buildings (offices, hospitals, laboratories, educational institutions, libraries). For any other building, the Chief Engineer (Elect.) decides; mark the match **ambiguous** until the group is confirmed. The group belongs to the **building**, not to each room: use one group for all point wiring in a building (an office room inside a residential block takes the block's group). A building that is neither listed type, such as a security post with a guard dormitory, falls under "any other type": propose one group, mark it ambiguous and state why.
- **Several points on one switch (3.4.6).** The run from the switch to the first outlet is one normal point. Each further outlet (outlet to next outlet) is a group-controlled point, counted per unit.
- **Twin control (3.4.7).** A light controlled by two 2-way switches is measured as two points, from the fitting to the switch on each side. The DSR (E&M) twin-control items are priced per point, so the light takes 2 × the twin-control item. No recovery is made for providing only one ceiling rose (3.4.7(b)).
- **Call bell from several places (3.4.8).** The bell outlet to the nearest bell-push ceiling rose is one point; each further rose is another point.

## Socket outlet wiring (unit Metre)

- 6 A light plug and 16 A power point wiring is **measured per metre**, from the tapping point of the live cable (switch box, another socket outlet or the sub-distribution board) up to the socket (3.4.5(a)).
- The box with cover, switch or MCB and socket are a **separate item** (3.4.5(b)).

## Circuit and submain wiring (unit Metre)

- **Submain wiring** runs from one main or distribution board to another. **Circuit wiring** runs from the distribution board to the first tapping point inside the switch box where point wiring starts (3.3.1).
- **Measure along the run (3.3.2(a)):** all lengths from end to end of the conduit or channel, excluding interconnections inside switchboards. Do **not** add for diversions or slack.
- Two-wire circuit wiring runs from the DB to the nearest switch box where point wiring starts. **Looping between switch boxes counts as circuit wiring**, measured along the conduit (3.3.2(b)).
- Wires of different circuits in one conduit are measured by the actual number and sizes of wires run (3.3.2(c)).
- Protective conductors run along circuit and submain wiring are measured per metre (3.3.2(d)). The DSR (E&M) circuit and submain items 1.7 and 1.14 already include the earth wire, so do not add it again with those items.
- Submain, circuit and point wiring run in separate conduits (Note to 3.3.2). Each conduit run is therefore one kind of wiring only.
- Any other wiring is measured per metre along the run by the actual number and sizes of wires (3.3.3).

## Circuit capacity (design check)

The number of circuits sets the number of circuit wiring runs and MCB ways. NBCS 2026 (SP 7:2026, Part D Section 2, 5.4.4.3) limits sub-circuits as follows:

- A mixed sub-circuit of lights, fans and 6 A sockets: no more than 10 points and 800 W.
- A dedicated light circuit: 800 W or 20 points, whichever is less.
- A dedicated 6 A socket circuit: 800 W or 8 sockets, whichever is less.
- A separate fan circuit: no more than 10 fans.
- A power sub-circuit: no more than two 16 A outlets.

The CPWD Electrical Part I Internal 2023 specification, which governs DSR (E&M) work, has matching rules: a lighting circuit of no more than 800 W or 20 points (3.10.1); one outlet per power circuit in non-residential buildings, or three 6 A computer outlets (3.10.2); in residential buildings up to two 16 A, or three 6 A, or one 16 A and two 6 A outlets, with geysers, AC outlets, ovens and washing machines on their own circuits (3.10.3). Rate 6 A and 16 A sockets at 100 W and 1000 W unless actual loads are given (3.9.3). Where the project specification sets stricter limits, use them and state which you applied.

## Selecting DSR (E&M) 2025 items

Read `describe_source section=category:WIRING`. In summary:

| Work | Steel conduit | PVC conduit |
|---|---|---|
| Point, piano switch, single control | 1.1 | 1.8 |
| Point, piano switch, twin control | 1.2 | 1.9 |
| Point, modular switch, single control | 1.3 | 1.10 |
| Point, modular switch, twin control | 1.4 | 1.11 |
| Group-controlled (looped) point | 1.54 | 1.55 |
| Socket wiring per metre | 1.5, 1.6 | 1.12, 1.13 |
| Circuit and submain wiring per metre | 1.7 | 1.14 |

The children of 1.10, 1.55 and similar items are Group A, B and C. Socket boxes, switches and sockets are 1.29 to 1.32, 1.56 and 1.57. Fitting and fan installation-only items are 1.35 to 1.51. Do not use them with an SITC luminaire or fan item, which already includes installation.

## Worked count

Office (non-residential, so Group C), PVC conduit, modular switches. Six ceiling luminaires on two switches, three luminaires each:

| Work | Location | Count | Unit | Proposed item | Note |
|---|---|---|---|---|---|
| Light point, first outlet on each switch | Office 1 | 2 | Point | 1.10.3 | one normal point per switch (3.4.6) |
| Group-controlled light point | Office 1 | 4 | Point | 1.55.3 | outlet to next outlet (3.4.6) |
| Circuit wiring DB to switchboard | Office 1 | route pending | Metre | 1.14.x by wire size | DB to first switch box, along the conduit, no slack (3.3.2) |
