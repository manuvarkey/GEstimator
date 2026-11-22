---
description: Worked example - preliminary lighting design for a 6 x 4 m office (NBCS 2026 criteria, lumen method, ECSBC 2024 check), handoff record, draft electrical measurement lines and proposed DSR (E&M) 2025 item matches.
---

# Worked example: office

The values below show the method. The luminaire flux and utilisation factor are assumed, not from a real datasheet. Replace them with project data before you rely on the count.

## Brief

"Prepare a preliminary estimate for the lighting of Office 1 on plan A-101 rev B. No electrical drawings yet." The adopted schedule is DSR (E&M) 2025 (`get_state` shows it attached; `describe_source` confirms the edition).

## Inputs

| Input | Value | Source |
|---|---|---|
| Room | Office 1, first floor, general office | Plan A-101 rev B |
| Size | L = 6.00 m, W = 4.00 m, A = 24.00 sqm | Plan A-101 rev B |
| Ceiling height | 3.00 m, false ceiling | Section S-1 rev B |
| Working plane | 0.85 m (task height not known) | NBCS 2026, Part D Section 1, 4.1.4.4 |
| Reflectances | ceiling 0.7 (white), walls 0.5 (light colour), floor 0.2 | NBCS 2026 reflection factors 4.3.2.3(b)(2) for ceiling and walls; floor assumed |
| Criteria | Ēm 500 lux (range 300-500-750, middle value), Uo 0.60, Ra 80, RUGL 19 | NBCS 2026, Table 6 ref. 26.2 and 4.1.4.3 |
| Luminaire | Recessed LED panel 2×2 ft, 36 W, 4400 lm (122 lm/W) | Assumption, no datasheet |
| Utilisation factor | 0.60 at kr ≈ 1.1 for the reflectances above | Assumption, no datasheet |
| Maintenance factor | 0.8 (fairly clean interior, office) | IS 3646 (Part 1):1992, 6.2.1 (NBCS 2026 gives no value) |
| Control | Two switch groups at the entrance, one row each, rows parallel to the window wall | Assumption; the window row can be switched off in daylight (ECSBC 2024, 7.2.2(c)) |
| Energy code | ECSBC 2024, ECSBC building level (office, connected load over 100 kW) | Assumption, to confirm |

## Calculation

1. `Hm = 3.00 - 0.85 = 2.15 m`
2. `kr = (6.00 × 4.00) / ((6.00 + 4.00) × 2.15) = 24.00 / 21.50 = 1.12` (L is under 5W, so no cap).
3. `N = (500 × 24.00) / (0.60 × 0.8 × 4400) = 12000 / 2112 = 5.68`, rounded up to **6**.
4. Check: `Eav = 6 × 4400 × 0.60 × 0.8 / 24.00 = 528 lux`, which meets 500 lux.
5. Layout: 2 rows × 3 luminaires. Along the 6.00 m wall: spacing 2.00 m, 1.00 m to the end walls. Across the 4.00 m width: row spacing 2.00 m, 1.00 m to the side walls. Spacing 2.00 m ≈ Hm 2.15 m and end distance 1.00 m = 0.5 × spacing, as NBCS 4.3.2.4(a) describes. Confirm the datasheet's maximum spacing to height ratio.
6. Quality: the proposed DSR (E&M) panel specification requires CRI > 80 and UGR < 19, which meets Ra 80 and RUGL 19. Uniformity Uo 0.60 is not verified (needs a point calculation).
7. Load: `6 × 36 W = 216 W`; LPD `216 / 24.00 = 9.0 W/sqm`. This is within the ECSBC 2024 space function limit for an enclosed business space, 10.0 W/sqm (Table 7.4). It exceeds the ECSBC+ limit of 8.6 W/sqm (Table 7.5), so an ECSBC+ building needs fewer or more efficient luminaires.
8. Controls (ECSBC 2024, 7.2.2):
   - The room is a habitable space under 30 sqm enclosed by walls, so it needs an **occupancy sensor** (7.2.2(b)2.i). The sensor must switch off or dim by at least 80 % within 15 minutes, and the fittings keep a wall-mounted manual switch (7.2.2(a)2).
   - The two switch groups give the one control device per enclosed space (7.2.2(b)1).
   - The window row is in the daylight area; its separate manual switch meets 7.2.2(c).
   - The 30 sqm limit is close: an office over 30 sqm would instead need control zones of at most 60 sqm (7.2.2(b)1.ii).

## Handoff record

| Field | Value |
|---|---|
| Room / location | Office 1, first floor |
| Fixture type | LED panel 2×2 ft, recessed |
| Count | 6 (2 rows × 3) |
| Rating | 36 W, 4400 lm assumed (efficacy 122 lm/W, band at least 120 and under 135 lm/W) |
| Control assumptions | 2 switch groups of 3 luminaires at the entrance, window row separately switched; one ceiling occupancy sensor over both groups, with the wall switches kept (ECSBC 2024, 7.2.2(a)2 and (b)2.i) |
| Associated work | Point wiring for 6 luminaires; occupancy sensor; circuit wiring from the floor DB to the switchboard |
| Sources | A-101 rev B, S-1 rev B, NBCS 2026 Part D Section 1 (Table 6 ref. 26.2, 4.1.4.3, 4.1.4.4, 4.3.2), IS 3646 (Part 1) 6.2.1, ECSBC 2024 Table 7.4 and 7.2.2 |
| Unresolved inputs | Luminaire datasheet (flux, UF, spacing ratio, photometry for uniformity); efficacy band and body construction required by the specification; ECSBC compliance level; sensor coverage and mounting (one sensor may not cover the room); DB location and circuit route; wiring specification (assumed PVC conduit, modular switches) |
| Status | Provisional (preliminary design) |

## Draft measurement (electrical measurement skill)

The building is an office, so the point group is **Group C** (non-residential, CPWD Electrical Part I Internal 2023, 3.4.4). Each switch group gives one normal point (switch to first luminaire). The two further luminaires in each group are group-controlled (looped) points (3.4.6).

| # | Work | Location | Count / dimensions | Unit | Calculation | Source | Assumptions |
|---|---|---|---|---|---|---|---|
| 1 | LED panel 2×2 ft, 36 W, SITC | Office 1, FF | 2 rows × 3 | Each | `2 × 3 = 6` | Lighting design above | Provisional count; 36 W, 4400 lm assumed |
| 2 | Light point, switch to first luminaire | Office 1, FF | 2 switch groups | Point | `2 × 1 = 2` | Lighting design above | Two groups assumed; PVC conduit, modular switch |
| 3 | Group-controlled (looped) light point | Office 1, FF | 2 groups × 2 further luminaires | Point | `2 × 2 = 4` | Lighting design above | As line 2 |
| 4 | Occupancy sensor, ceiling | Office 1, FF | 1 | Each | `1` | ECSBC 2024, 7.2.2(b)2.i | Ceiling mounted at 3.00 m; one sensor assumed |
| 5 | Circuit wiring, DB to switchboard | Office 1, FF | route pending | Metre | not established | - | Needs the DB location and route |

## Proposed schedule item matches

Checked with `search_items` and `get_items` in DSR (E&M) 2025. The heading text holds the specification; the child holds the variant.

| Line | Proposed item | Unit | Status | Reason |
|---|---|---|---|---|
| 1 | 8.7.4 "LED Panel light 2x2 ft. (System lumen efficacy ≥120 <135 lm/Watt) ... Powder coated die cast / Extruded aluminium Body ... 36 watt" | Each | **Ambiguous** | Band matches 122 lm/W and the wattage matches. The body construction is not specified: 8.7.4 is the aluminium body, 8.7.10 the powder-coated CRCA body. The item is SITC and includes external connections and earthing. |
| 2 | 1.10.3 "Wiring for light point ... in surface / recessed medium class PVC conduit, with modular switch, modular plate, suitable GI box and earthing the point ... Group C" | Point | Proposed | Office is Group C; conduit and switch type follow the assumed wiring specification. |
| 3 | 1.55.3 "Wiring for group controlled (looped) light point ... ( without independent switch etc.) ... PVC conduit ... Group C" | Point | Proposed | Further luminaires on the same switch. |
| 4 | 7.1 "Supplying, installation, testing and commissioning of Passive Infrared (PIR) technology based occupancy sensor ... non regulating programmable type ... for mounting height up to 2.8 mtr and for 5 m diameter coverage area" | Each | **Ambiguous** | The item is rated for mounting up to 2.8 m and 5 m diameter coverage. The ceiling is 3.00 m and the room 6.00 × 4.00 m (7.2 m diagonal), so one ceiling sensor may not comply or cover the room. Options: a sensor rated for the height (from the datasheet, as a non-schedule item), a lower or wall mounting, or two sensors. 7.2 (PIR with daylight dimming) applies only if automatic daylight control is chosen. |
| 5 | 1.14.x "Wiring for circuit/ submain wiring alongwith earth wire ... PVC conduit", child by wire size | Metre | **Unmatched (input missing)** | The size depends on the circuit design; the length depends on the route. |

Not added, to avoid double counting:

- Fitting installation 1.35: item 8.7.4 already includes installation, testing and commissioning.
- Switch boxes and plates 1.27: item 1.10 includes the GI box, modular switch and plate.
- Loop earthing 5.16 to 5.19 for the points: point wiring includes earthing of the point.
- Separate wiring for the occupancy sensor: not added. Confirm with the specification whether the sensor connection needs a point or is part of item 7.1.

## Applying, only when the user asks

After review, and only when the user asks to apply the estimate:

1. `import_items` with `source` set to the DSR (E&M) 2025 source and `codes` for the chosen items (for example 8.7.4, 1.10.3, 1.55.3, and 7.1 once its mounting is resolved). Use the returned `code_map` for the project codes.
2. `get_measurements section=templates` to read the template IDs and columns.
3. `edit_measurements` to create one sheet per item, linked to the item, with one record per line above. Put the location and "provisional" in the description.
4. `recalculate what=quantities` with an explicit rounding choice. Then `get_summary`.

Group the writes in one `batch`. Leave line 5 out until its route and size are known.
