---
description: Luminaires, fans and lighting controls - counting by type and rating, LED efficacy bands, supply versus installation, and DSR (E&M) 2025 LED LIGHT, BLDC FAN and LIGHTING CONTROLS item selection.
---

# Luminaires, fans and lighting controls

Item codes and inclusions come from the DSR (E&M) 2025 database notes, checked against the printed book. Read the category notes with `describe_source` before choosing items.

## Inputs

- Luminaire schedule: type, wattage, system lumen efficacy, mounting, colour temperature.
- Lighting layout: fixture positions and counts by room.
- Energy code status (ECSBC 2024 compliance level) and any efficacy requirement of the project specification.
- Fan schedule: sweep, regulator or remote control.
- Control schedule: occupancy sensors, daylight dimming, time switches.

## Counting

- Count fittings **each** by type and rating per room. Keep each wattage and efficacy band separate.
- Each fitting also needs its point wiring. Count the points from the control arrangement (see the [wiring reference](gestimator://skills/in/electrical-measurement-estimation/references/wiring.md)).
- Count sensors, regulators and time switches each.

## Supply and installation

- DSR (E&M) LED LIGHT items (8.x) are **supply, installation, testing and commissioning**, including external connections and earthing. Do not add the installation-only fitting items (1.35, 1.41, 1.42) for the same fittings.
- BLDC FAN items (9.1 remote, 9.2 regulator) are SITC by sweep. Installation-only fan items in WIRING (1.44, 1.45) are for fans supplied by others.
- When the client supplies the fittings, use the installation-only items and say so.

## Selecting DSR (E&M) 2025 items

- LED fittings by type: down lighters 8.1 to 8.5, 2×2 ft panels 8.6 to 8.8, battens 8.9 to 8.11, street lights 8.12 to 8.14, flood lights 8.15 to 8.17.
- Each type has three efficacy bands as separate headings: at least 105 and under 120, at least 120 and under 135, and at least 135 lm/W. Use the band the design or energy code requires. If the band is not given, mark the match **ambiguous** and name the missing input.
- Children are wattages and, for panels, body construction (die-cast or extruded aluminium, or powder-coated CRCA sheet). The body is part of the specification; ask if the schedule does not state it.
- Occupancy sensors: PIR 7.1, PIR with daylight dimming 7.2, microwave 7.3. Astronomical time switches 7.4.

## Energy code checks (ECSBC 2024)

The Energy Conservation and Sustainable Building Code 2024 applies to commercial and office buildings with a connected load of 100 kW or more, or a contract demand of 120 kVA or more (Scope, 2). When the project must comply, it affects item choice and counts:

- **Lighting power (7.3).** The installed interior lighting power must not exceed the allowance by the building area method (Table 7.1; office building 9.5 W/sqm for an ECSBC building) or the space function method (Table 7.4; business, enclosed or open plan 10.0 W/sqm). ECSBC+ and Super ECSBC buildings have lower limits (Tables 7.2, 7.3, 7.5, 7.6). A design over the limit needs fewer or more efficient fittings, which changes the wattage children or the efficacy band.
- **Controls (7.2.2).** At least 90 % of interior lighting by wattage needs scheduled control or occupancy sensors (7.2.2(a)). Each enclosed space needs its own control device, and offices over 30 sqm need control zones of at most 60 sqm (7.2.2(b)1). Occupancy sensors are required in habitable spaces under 30 sqm, storage and utility spaces over 15 sqm, public toilets over 25 sqm, hospitality corridors and all conference and meeting rooms (7.2.2(b)2). Daylit luminaires need a manual or automatic control (7.2.2(c)). ECSBC+ and Super ECSBC buildings need a centralised lighting control system (7.2.4).
- Count the sensors these clauses require (DSR (E&M) 7.1 to 7.3) and the extra switch groups and zones they create. Check each sensor item's rated mounting height and coverage against the room: 7.1 and 7.2 are rated for mounting up to 2.8 m and 5 m diameter coverage, 7.3 for 2.6 m and 5 m × 20 m.
- The CPWD Electrical Part I Internal 2023 specification (2.10.2, Tables 2.1 to 2.6) still quotes the earlier ECBC tables. Use ECSBC 2024.

## Checks

- Fitting count per room equals the layout or the design output.
- Wattage × count matches the room's lighting load in the circuit schedule, where one exists.
- No fitting has both an SITC item and an installation-only item.
