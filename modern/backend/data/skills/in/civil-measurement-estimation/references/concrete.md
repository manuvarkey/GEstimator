---
description: Concrete takeoff rules (IS 1200 Part 2 concrete, Part 5 formwork, reinforcement) - element classification, column/beam/slab junctions, deductions, contact-area formwork, and DSR item selection for PCC and RCC.
---

# Concrete, formwork and reinforcement

Governing parts:

- **IS 1200 (Part 2):1974 Concrete works, third revision** (reaffirmed). Clauses checked against that text. BIS has circulated a draft fourth revision.
- **IS 1200 (Part 5):1982 Formwork, third revision** (reaffirmed). Clauses checked against that text.
- Reinforcement: IS 1200 (Part 8) Steel work and iron work, called up by Part 2, 4.1.5. Part 8:1993, 11.1–11.3, covers bars, authorised laps and chairs, fabric and binding wire. Measure reinforcement to the project specification and the adopted item.

## Inputs

- General arrangement and structural drawings: element sizes, levels, grid.
- Concrete grade or nominal mix, design mix or nominal mix, aggregate type.
- Location: up to plinth, above plinth up to floor five, higher floors.
- Openings, sleeves, embedded pipes and conduits.
- Bar bending schedules or detailing, with the steel grade.
- Finish: fair-face, plastered, or a special finish.

## Concrete (Part 2)

- Unit: **cum** unless otherwise stated (4.1.2). Measure net as fixed. Dimensions to 0.01 m, except slab thickness to **0.005 m** (2.4.1). Ignore work done beyond the specified dimensions (2.4).
- Measure plain, reinforced and prestressed concrete separately. Keep precast and cast-in-situ work separate (4.1.1).
- Classify cast-in-situ work by element: foundations and footings, walls, slabs, chajjas, lintels and beams, columns, stairs, and so on (4.2.1). Projections belong to the main item.
- **Formwork** is measured separately unless otherwise stated (4.1.3). **Reinforcement** is measured separately unless otherwise stated (4.1.5). Special finishes other than those from formwork are measured separately in sqm (4.1.4).

### Junctions (4.2.2, 4.2.3)

- Columns: from the top of the column base to the underside of the first floor slab, then from the top of each floor slab to the underside of the slab above (4.2.2.1). Include the flare of a flat-slab column with the column (4.2.2.2).
- Beams: from face to face of columns, including haunches. Beam depth runs from the bottom of the slab to the bottom of the beam. For an inverted beam it runs from the top of the slab to the top of the beam (4.2.2.3).
- Chajja with a beam or lintel: measure the common portion as chajja. A chajja continuing a roof or suspended slab is measured up to the centre line of the bearing (4.2.3).

### No deduction (4.1.8)

- ends of dissimilar materials (beams, posts, girders, rafters, purlins, corbels, steps) up to **500 cm²** in cross-section;
- openings up to **0.1 sqm**;
- the volume of reinforcement;
- pipes, conduits and sheathing up to **100 cm²** each in cross-section;
- small voids up to **40 cm²** each in cross-section;
- moulds, chamfers, splays, grooves and rebates up to 10 cm wide or 15 cm in girth.

Include the thickness of a separate lintel or sill in the height of an opening. No extra labour is measured for forming openings or voids (Note to 4.1.8).

## Formwork (Part 5)

- Unit: **sqm of the actual surface in contact with the concrete** (6.1). Enumerate formwork to small features such as cantilever ends, brackets and caps.
- No deduction for openings up to **0.4 sqm** (6.4).
- The item includes supports, props, ties, working scaffolds, oiling, and striking and removal (3.1).
- Classify separately (5.1): foundations; flat soffits (state the thickness of floors over 200 mm); vertical surfaces; sloping surfaces; sides and soffits of beams (beams 1 m deep and over separately); columns (by shape); edges of slabs (running metres where under 200 mm); chajjas; stairs; and so on.
- Measure the contact faces only. A beam typically has its soffit and two sides less the slab thickness. A column has its perimeter faces less the beam faces at the junction.

## Reinforcement

- Usual unit: **kg** (DSR 5.22 children), from the bar bending schedule: number × cut length × unit weight per bar diameter.
- Laps, chairs and spacers: follow the project specification and the item text. They change from contract to contract. State what you assumed.
- Where reinforcement is part of a composite concrete item, measure items with different reinforcement separately (Part 2, 4.1.5).
- The `civil_steel_table` measurement template records bar tables.

## Selecting DSR 2023 items

Read `describe_source section=category:CONCRETE WORK` and `category:REINFORCED CEMENT CONCRETE`. An RCC member is priced as concrete + formwork + reinforcement + finishing:

- Concrete: nominal mix 5.1 to 5.8 by element and location, or design mix 5.33 / 5.33A by location and grade. PCC 4.1 (up to plinth), 4.2 (above plinth); design mix PCC 4.20.
- Formwork: 5.9 by element (5.9.1 foundations, 5.9.3 slabs, 5.9.5 beams, 5.9.6 columns, 5.9.19 chajjas). Use 4.3 for PCC.
- Reinforcement: 5.22.6 for TMT bars (5.22, 5.22A); 5.22B or 5.22C for factory cut-and-bend bars.
- Finishing: 5.23 or 5.24, or plaster from FINISHING.
- Floor-level extra 5.38 above floor five; work in or under water 5.31.

## Worked line

First floor beam B1, 300 × 450 mm overall, under a 125 mm slab, clear span 4.20 m between columns, M25 design mix.

| Work | Location | No × L × B × H | Unit | Quantity | Note |
|---|---|---|---|---|---|
| RCC beam below slab | FF B1 | 1 × 4.20 × 0.30 × 0.325 | cum | 0.41 | depth 0.450 - 0.125 below slab (4.2.2.3); proposed 5.33.2 child for M25, confirm the grade and location |
| Formwork, beam soffit | FF B1 | 1 × 4.20 × 0.30 | sqm | 1.26 | contact area (Part 5, 6.1) |
| Formwork, beam sides | FF B1 | 2 × 4.20 × 0.325 | sqm | 2.73 | sides below slab; proposed 5.9.5 |
| Reinforcement | FF B1 | from BBS | kg | pending | needs the bar bending schedule; proposed 5.22.6 |
