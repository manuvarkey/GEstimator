---
description: Masonry takeoff rules (IS 1200 Part 3 brickwork) - units by wall thickness, deductions and thresholds, separately measured work, and DSR item selection for brick and block walls.
---

# Masonry

Governing part: **IS 1200 (Part 3):1976 Brickwork, third revision** (reaffirmed). Clause numbers below were checked against the text of that edition. BIS has circulated a draft fourth revision (2025). Confirm which edition the contract adopts, and confirm that the project specification does not override these rules.

## Inputs

- Wall schedule or plans: wall type, material and brick class, thickness, mortar mix.
- Location: foundation and plinth, superstructure, floor level (for floor-level extras), below or above datum.
- Sections and elevations: wall heights between floor and soffit, parapets, plinth height.
- Door and window schedule: opening sizes, lintel and sill details.
- Finish scope: plastered, pointed or exposed (fair face), which faces.

## Units and thickness

- Brickwork is measured in **cum** unless otherwise stated (4.1).
- Walls **one brick thick and less** are measured separately in **sqm**, stating the thickness (4.1.1). In DSR 2023, half-brick masonry is per sqm (6.12, 6.13). Full-brick and thicker walls are per cum (6.1 to 6.4).
- Walls over one brick and up to three bricks thick are measured in **multiples of half a brick**, including mortar joints (4.1.2). For the remaining fraction, measure up to and including a quarter brick at actual thickness. Count a larger remainder as a half brick.
- Walls over three bricks thick are measured at their actual thickness (4.1.3).
- Measure net as built, to 0.01 m, with areas to 0.01 sqm and volumes to 0.01 cum (2.3).

## Deductions (4.1.4)

Make **no** deduction or addition for:

- ends of dissimilar materials (joists, beams, lintels, posts, girders, rafters, purlins, trusses, corbels, steps) up to **0.1 sqm** in section;
- openings up to **0.1 sqm** in area;
- wall plates, bed plates and bearings of slabs and chajjas up to 10 cm thick, where the bearing does not extend over the full wall thickness;
- concrete blocks for holdfasts and holding-down bolts;
- iron fixtures, wall ties, pipes up to 300 mm diameter, and holdfasts for doors and windows;
- chases up to 50 cm in girth.

Deduct openings over 0.1 sqm, and ends of dissimilar materials over 0.1 sqm in section. When you calculate an opening's area, include a separate lintel or sill in the opening size. Leave out the end portions of the lintel and any extra width of a rebated reveal (Note to 4.1.4). The minimum area for a deduction applies only to an opening within the space measured (2.6).

Record each lintel or beam that passes through a wall as a deduction from the masonry. Measure it in its own concrete item.

## Included in general brickwork (3.1.1, 3.1.2)

Raking out joints for plaster or pointing (or finishing joints flush), rough cutting, plumbing angles, forming reveals without fair cutting, leaving holes for pipes, building in holdfasts and the ends of beams, joists, slabs, lintels and sills, forming openings that are not deducted, bedding wall plates and lintels, and chases up to 50 cm in girth. Footings, eaves fillings, pilasters, plain copings and sills are included with general brickwork. Do not measure any of these again.

## Measured separately

- Battered surfaces: an extra-over in sqm (3.1.2(b)).
- Pillars, in cum, kept separate by shape (4.1.6).
- Circular work to a mean radius of 6 m or less (5.1).
- Honeycomb walls in sqm, openings not deducted (7.1).
- Cavity forming in sqm at the centre plane of the cavity (9.1, 9.2).
- Reinforced brickwork, with its reinforcement measured separately (10.1).
- Fair face or architectural brickwork (12.1).
- Arches, vaults and staircases; centering over 2 m span (13.1).
- Fair cutting, brick edgings, damp-proof courses (sqm, vertical and horizontal separately), and chases over the stated girth (15, 16, 19, 23).
- Work in or under water, in liquid mud or in foul positions (2.7). Work below and above ground or datum (2.9).

## Selecting DSR 2023 items

Read `describe_source section=category:MASONRY WORK` first. In summary:

- Burnt clay brick in foundation and plinth: 6.1 (F.P.S.), 6.2 (modular), 6.3 (perforated). Superstructure up to floor five: 6.4. The children are by mortar.
- Half-brick masonry (sqm): 6.12 foundation, 6.13 superstructure. Add 6.15 where bars are built in, and 6.14 above floor five.
- AAC blocks: 6.38 for 100 or 125 mm walls (sqm), 6.47 for 150 to 300 mm (cum).
- Floor-level extra: 6.5 for each four floors above floor five, for the same quantity.

Plaster and pointing are separate items. See [finishes](gestimator://skills/in/civil-measurement-estimation/references/finishes.md).

## Worked line

Ground floor, grid A/1-3, 230 mm wall in 1:6 mortar, 8.40 m long, 3.00 m from floor to beam soffit, with one window W1 of 1.50 × 1.20 m.

| Work | Location | No × L × B × H | Unit | Quantity | Note |
|---|---|---|---|---|---|
| 230 mm brick wall 1:6, superstructure | GF A/1-3 | 1 × 8.40 × 0.23 × 3.00 | cum | 5.80 | gross |
| Deduct W1 | GF A/1-3 | -1 × 1.50 × 0.23 × 1.20 | cum | -0.41 | opening > 0.1 sqm (4.1.4) |
| Net | | | cum | 5.38 | proposed DSR 2023 6.4 child for 1:6 mortar; confirm the mix and brick class |
