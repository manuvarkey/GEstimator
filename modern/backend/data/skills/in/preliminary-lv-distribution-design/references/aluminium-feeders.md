---
description: Select aluminium XLPE feeder sizes for duct, burial or free-air duty and specify compatible MCCB or enclosed Al-to-Cu transition terminations.
---

# Aluminium feeder shortlist

Prefer copper through 25 mm² inclusive and at MCBs. Above that copper size, compare independently sized aluminium and copper options, including lugs, enclosure space, losses and permitted equipment. The boundary is a project material preference. Apply CPWD Internal 3.12.1 copper-only wiring where that clause governs. Use aluminium only for an eligible feeder with suitable equipment at **both** ends.

## Current and drop

IS 732:2019 Annex S, Tables 20, 24 and 32. Preliminary amperes below are for a single multicore aluminium XLPE cable, three loaded conductors, 90 °C conductor rating. D1 is in underground duct, D2 direct in ground (20 °C reference ground; 2.5 K·m/W). E is a qualifying free-air installation at 30 °C. Confirm cable construction, terminal temperature, burial depth, grouping, soil drying and the worst route segment before accepting a rating. For a heavily loaded neutral, single-phase duty, other insulation or installation, obtain the matching data.

| Al mm² | D1 | D2 | E |
|---:|---:|---:|---:|
| 35 | 90 | 98 | 120 |
| 50 | 106 | 117 | 146 |
| 70 | 130 | 144 | 187 |
| 95 | 154 | 172 | 227 |
| 120 | 174 | 197 | 263 |

For D1 XLPE at 25/30/35 °C ground use 0.96/0.93/0.89 (Table 34). At soil resistivity 3 K·m/W, Table 35 gives 0.96 for buried ducts or 0.90 for direct burial under its stated conditions. Apply applicable circuit spacing/grouping and depth factors. For free-air XLPE at 35/40/45 °C use 0.96/0.91/0.87 and the applicable tray arrangement/grouping factor. Keep burial and air corrections separate.

For each corrected capacity Iz, require IB ≤ In ≤ Iz and I2 ≤ 1.45Iz (4.4.4.1). Take settings and I2 from the device data. Under Annex Y, for a balanced lagging three-phase feeder, line-to-line drop in volts = √3 × I × L × (0.036 × PF / S + 0.00008 × sin φ), with one-way L in metres and Al area S in mm². Prefer measured/supplier impedance at operating conditions. Include upstream and downstream drop. Verify short-circuit withstand, PE and automatic disconnection separately.

Example: 400 V balanced feeder, design current 90 A, PF 0.9, 100 m of D1 cable, 30 °C ground, reference soil, one circuit and all other reference conditions. An Al-compatible MCCB has illustrative setting 100 A and supplied I2 of 130 A. At 50 mm², 106 × 0.93 = 98.58 A, below setting. At 70 mm², 130 × 0.93 = 120.90 A and both overload checks pass. Drop is about 7.76 V (1.94%); add 0.50% upstream to get 2.44% against this project's 3% budget. Carry one 100 m run, matched ends and the separately verified protective path. Hold breaking-capacity/clearing checks open until fault levels and curves are known.

## Device interface

For aluminium select an MCCB with manufacturer-approved Al-compatible terminals/lugs for the exact conductor size, strand class and breaker model. Verify fault duty, settings, pad dimensions, enclosure temperature/space, bending radius, tightening torque and installation instructions. MCCB construction alone gives no assurance of Al suitability. IS 732 Table 9 note 1 requires Al connectors approved and tested for the purpose.

If an existing MCB endpoint is unavoidable, this office requires a separate accessible enclosed transition: incoming Al → rated Al/Cu clamping connector or distribution block → sized copper tail → MCB. Verify temperature, short-circuit withstand, tail overload and fault protection including the section ahead of the MCB, segregation, enclosure/IP, gland support and torque at both interfaces. Include the box, connectors, Cu tails, lugs/glands and labels in the BOQ where excluded from the panel rate. If the interface or tail protection cannot be substantiated, retain the copper option or redesign the termination.
