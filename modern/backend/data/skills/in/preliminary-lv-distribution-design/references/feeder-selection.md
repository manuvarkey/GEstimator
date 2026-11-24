---
description: Shortlist copper conductors by current and voltage drop, compare neighbouring sizes and hand a measured cable run to the BOQ.
---

# Select a preliminary copper feeder

Use the adopted IS 732:2019 basis below for ordinary LV AC circuits. Record board/circuit, voltage, design demand, power factor, phase loading, one-way length, upstream drop, remaining downstream allowance, device rating and installation conditions. For 1-phase use input watts/(V × PF); for balanced 3-phase use input watts/(√3 × line V × PF). Apply agreed demand factors once.

## Current shortlist

Reference ratings in amperes at 30 °C in air. Each cell gives **two / three loaded conductors**. B1 here is single-core insulated copper conductors in surface conduit; B2 is multicore cable in surface conduit. Both assume the wall installation conditions of Table 20. PVC ratings assume 70 °C conductors and XLPE 90 °C. Confirm terminations permit the design temperature. Source: IS 732:2019, Annex S, Tables 20–24.

| Copper mm² | B1 PVC | B2 PVC | B2 XLPE |
|---:|---:|---:|---:|
| 1.5 | 17.5 / 15.5 | 16.5 / 15 | 22 / 19.5 |
| 2.5 | 24 / 21 | 23 / 20 | 30 / 26 |
| 4 | 32 / 28 | 30 / 27 | 40 / 35 |
| 6 | 41 / 36 | 38 / 34 | 51 / 44 |
| 10 | 57 / 50 | 52 / 46 | 69 / 60 |
| 16 | 76 / 68 | 69 / 62 | 91 / 80 |
| 25 | 101 / 89 | 90 / 80 | 119 / 105 |

Start at the project minimum cross-section. For each candidate multiply the reference rating by ambient and applicable grouping factors. At 30/35/40/45 °C, PVC factors are 1/.94/.87/.79 and XLPE factors are 1/.96/.91/.87 (Table 33). For one, two or three uniformly and equally loaded circuits bunched/enclosed together, use 1/.80/.70 respectively (Table 36, item 1). Check the worst route segment. Obtain appropriate ratings for buried, thermally insulated, mixed/grouped or harmonic-loaded installations outside these conditions. Check each phase and neutral where loading is unbalanced.

Check IB ≤ In ≤ Iz and I2 ≤ 1.45 × Iz (4.4.4.1). IB is design current, In the device rating or setting, Iz corrected cable capacity and I2 the device's conventional operating current. If In is unspecified, trial the lowest available project-approved device rating at or above IB that supports starting duty. Obtain I2 from its device data; leave that check open if unknown. Use a candidate with margin where a rounded result is on a boundary. Check starting duty, fault withstand, breaking capacity, earth-fault disconnection and protective conductor separately. Unknown fault data leave a provisional selection.

## Voltage-drop shortlist

Prefer manufacturer coefficients at operating temperature and PF. For an Annex Y screen use copper service resistivity 0.0225 Ω·mm²/m and, absent better data, reactance 0.00008 Ω/m. For lagging PF, drop in volts = k × one-way metres × design amps × (0.0225 × PF / area_mm² + 0.00008 × √(1 − PF²)). Use k=2 and circuit volts for single phase, k=√3 and line-to-line volts for balanced three phase. Compute percentage on the same voltage basis. Where actual conductor service-temperature resistance is known, use it.

Add drop from the origin through the complete load path. Compare with the project budget. Annex Y Table 47 gives public LV origin-to-load guidance of 3% lighting and 5% other uses; identify supply type and any equipment-specific limits before adopting a budget. Keep the first **listed** size satisfying all available checks. If the shortlist runs out, request the next applicable size data.

## Worked decision

F1: 18 kW electrical input × 0.80 demand, 400 V balanced, PF 0.90 gives 23.09 A. One four-core PVC cable in B2, negligible neutral load, 40 °C, one 150 m run, upstream drop 0.70%, total project budget 3%, no further downstream run. Proposed device 32 A, supplied operating current 46.4 A.

| mm² | Corrected A | Total drop | Decision |
|---:|---:|---:|---|
| 6 | 29.58 | 5.81% | Below the device rating |
| 10 | 40.02 | 3.79% | Both overload conditions pass; drop exceeds budget |
| 16 | 53.94 | 2.65% | First passing candidate; drop governs |

Book F1 as one 150 m four-core 16 mm² copper run, with two ends identified. Record the separate protective path, installation method and any authorised additional length. Mark fault checks open pending prospective current and device data. Use the electrical measurement skill for schedule matching when pricing is requested.
