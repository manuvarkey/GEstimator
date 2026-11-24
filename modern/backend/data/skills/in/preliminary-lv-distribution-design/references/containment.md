---
description: Select masonry or insulated-wall cable ratings and size conduits, trays, ducts and busbar riser quantities by route segment.
---

# Wall construction and containment

Record route ID, segment length, wall build-up, conductor construction, number loaded, ambient and neighbours. IS 732:2019 Table 19 items 59/60 and note 15 give B1 for singles and B2 for multicore in conduit in brick, concrete or plaster of thermal resistivity ≤2 K·m/W. Use the [B1/B2 ratings and corrections](gestimator://skills/in/preliminary-lv-distribution-design/references/feeder-selection.md). Conduit material alone does not identify its thermal method.

For the thermally insulated wall described in Annex S-6 (conduit near inner skin of thermal conductance ≥10 W/m²K, heat leaves through that skin), select A1 for insulated singles or A2 for multicore. Below are copper PVC ratings in A at 30 °C air, 70 °C conductor. Entries show two / three loaded conductors, IS 732 Tables 21 and 23.

| mm² | A1 | A2 |
|---:|---:|---:|
| 1.5 | 14.5 / 13.5 | 14 / 13 |
| 2.5 | 19.5 / 18 | 18.5 / 17.5 |
| 4 | 26 / 24 | 25 / 23 |
| 6 | 34 / 31 | 32 / 29 |
| 10 | 46 / 42 | 43 / 39 |
| 16 | 61 / 56 | 57 / 52 |
| 25 | 80 / 73 | 75 / 68 |

Check every segment. Example: one 230 V circuit, 18 A load, 20 A breaker with I2 = 29 A, two loaded Cu PVC singles, 40 °C, two bunched equally loaded circuits. At 4 mm², masonry gives 32 × .87 × .80 = 22.27 A. An insulated-wall segment gives 26 × .87 × .80 = 18.10 A. Carry 6 mm² through both sections (A1 gives 23.66 A) subject to drop and fault checks. For an unknown wall or cable fully buried in insulation outside the reference arrangement, request construction or applicable thermal data and leave capacity open.

## Conduit selection

CPWD Internal 2023 Table 4.1, §§4.3.1 and 5.3.1, for simultaneous pulling of same-size IS 694 PVC insulated singles. Each cell is the maximum **physical wire count** for straight / bent runs. Count L, N, PE, switched lives and travellers in each segment. For heating, count the conductors actually carrying load separately.

| wire mm² | 20 mm conduit | 25 mm conduit | 32 mm conduit |
|---:|---:|---:|---:|
| 1.5 | 5 / 4 | 10 / 8 | 18 / 12 |
| 2.5 | 5 / 3 | 8 / 6 | 12 / 10 |
| 4 | 3 / 2 | 6 / 5 | 10 / 8 |
| 6 | 2 / — | 5 / 4 | 8 / 7 |

Diameters are nominal outside sizes. Straight column applies to ≤4.25 m between draw boxes with deflection ≤15°. Bent column applies above 15°. For longer straight pulls establish draw boxes or verified pulling data. A dash supplies no capacity. Three equal 4 mm² wires on a bent run require 25 mm. For mixed sizes or other constructions obtain the approved fill rule and actual wire outside and conduit inside diameters. Verify bend radius, pull lengths, segregation and earth continuity. Price the conduit separately only if the chosen wiring item excludes it. [CPWD Internal 2023](https://cpwd.gov.in/Publication/CPWD_General_Specification_for_Electrical_Works_Part-I_Internal_2023.pdf)

## Tray, duct and riser quantities

For a single-layer tray use actual cable ODs, thermal spacing, edge clearance and project spare width. Three 24 mm cables, two specified 24 mm gaps and two 10 mm margins require 140 mm usable width before spares. A 150 mm usable tray fits that layout. Check load per metre, span, support details, bends and thermal grouping against the selected system. For ducts check actual bore, pulling geometry and tension at each chamber, thermal rating and spare ways. Record duct metres per way and cable metres per occupied run.

For a riser spanning three 3.2 m storey intervals, book 9.6 m on the vertical centreline before offsets. A supplier layout of three straight lengths plus a separate end feed and three protected floor tap-offs yields two intermediate straight joints. Record end connection kits, supports at the actual fixing levels and fire stops at each rated penetration. Check which components the assembly price includes.
