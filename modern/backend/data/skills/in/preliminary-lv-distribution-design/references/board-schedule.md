---
description: Convert room and equipment loads to circuits, occupied board modules, phase currents, feeder demand and payable wiring.
---

# From rooms to board and BOQ

Give each outlet or equipment group a room, input W or VA, PF, operating scenario, source and isolation point. Split normal, essential and UPS loads. Use the [project-specific circuit limits and measurement rules](gestimator://skills/in/electrical-measurement-estimation/references/wiring.md) once per building. Assign every outlet to one final circuit. Show room SDB or accessible room isolator and any circuits that stay live. Select phase by simultaneous current; apply diversity once at its documented level. Check the heaviest phase and neutral, including nonlinear loads.

Example floor of a two-storey office, normal 230 V L–N. Three independently used rooms each have six 30 W lights at PF 0.90 and one dedicated unity-PF socket appliance drawing the stated input. Each room has a single-phase SDB with linked isolation. Assume all loads operating. The socket branch is a surface run and lighting branches are recessed in ordinary masonry. For this example each local board has a separate neutral and PE bar.

| Room | Floor DB outgoing | Local circuits | Input by circuit | Phase demand |
|---|---|---|---|---:|
| A | F-A, L1 | A-L, A-P | 180 W, 2.30 kW | 10.87 A |
| B | F-B, L2 | B-L, B-P | 180 W, 1.84 kW | 8.87 A |
| C | F-C, L3 | C-L, C-P | 180 W, 1.38 kW | 6.87 A |

Values sum load current magnitudes conservatively per phase. For real electronic loads use input current/VA and starting duty. Total connected real load is 6.06 kW. Size the incoming feeder for at least the highest simultaneous phase current plus any agreed allowance; check the neutral separately. A second identical floor in the same phase order takes the upstream phase maxima to 21.74, 17.74 and 13.74 A. Assign distinct floor and circuit IDs. Check redistribution before selecting an incomer. Select an available rating against the feeder, switchgear and fault study.

For a worked branch, take A-P at 10 A over 20 m, 4 mm² Cu PVC L/N/PE, separate surface conduit, bent route, 30 °C and one circuit. Trial 16 A device, supplied I2 23.2 A. B1 capacity 32 A, resistive drop 2 × 20 × 10 × .0225 / 4 = 2.25 V (0.98%). Add actual upstream drop. Bent conduit is 25 mm. For A-L at 0.87 A, 1.5 mm² singles, same ambient and a separate bent masonry run with three equal wires, B1 is 17.5 A and 20 mm conduit fits. Recount wires after the switch. Select protection including applicable additional shock protection and verify disconnection.

Per floor return three floor-board outgoing feeders, three room SDBs, six final circuits, eighteen luminaires and three power outlets. If all six lights in each room share one switch, measure three first points and fifteen group-controlled points. Measure DB-to-switch circuit wiring and socket wiring from the actual routes. For each SDB list one incoming isolating device, two outgoing devices and agreed spares. Count actual module widths including linked poles, RCBO/RCCB, SPD and blanks; confirm phase positions and usable enclosure capacity from the product. Carry one upstream protective device per room feeder. Identify inclusions before costing the board and devices separately.

Whole-building count for these two identical floors: 2 × 3 = 6 room boards, 6 × 2 = 12 final circuits, 2 floor boards and 6 room feeders. Prefix room and circuit IDs with the floor. Exclude room feeders from the final-circuit count and keep head counts in the luminaire schedule.
