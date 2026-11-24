---
name: civil-measurement-estimation
description: Civil building takeoff for a GEstimator estimate (earthwork, concrete, formwork, reinforcement, masonry, plaster and finishes). Read before measuring civil quantities from drawings or schedules, matching them to DSR/SOR items, or writing civil measurements and BOQ items.
---

# Civil measurement estimation

Use this skill to turn civil drawings, schedules or model quantities into measurement lines and proposed schedule items. Measure to the applicable part of IS 1200, the project specification and the full description of the adopted schedule item. Record the contract’s order of precedence. If two payment rules conflict and the contract does not resolve them, show both quantities and flag the disputed item. Establish statutory and local design requirements separately.

**Work inside GEstimator.** The estimate is the GEstimator project: schedule items with linked measurement sheets. Record each quantity as measurement records with its dimensions or counts, deductions, location and source, so the project shows how it was derived. Do not compute quantities in a script or spreadsheet and enter only totals, and do not keep the estimate in a separate workbook; when a workbook is wanted, use `project action=export_xlsx`.

**Order of work.** Read the reference for each trade you actually measure. Reuse its rules and the category notes across matching items within the same source edition. Then read the database notes (`describe_source` overview, then `section=category:<name>` for each category) **before** searching for or choosing items, not afterwards to check them. Read a linked reference as an MCP resource, or with `describe_source section=<its gestimator:// link>`.

**Sources.** Use the GEstimator sources, their notes and these skills. Do not search the web for rates, schedule books, item texts or standards: the attached source is the adopted schedule, and these skills carry the standards checked for this work. Cite the schedule by the book and edition its notes give (`describe_source` overview). Where an item, criterion or clause is not covered, state the assumption and list it for review instead of looking it up.

## 1. Establish the basis

1. Call `get_state`. Note the open project and the attached sources. Skills are readable without an open project, but measurements need one.
2. Identify the adopted schedule (DSR, state SOR) and its edition. Call `describe_source` on that source and read its About section: edition, rate basis and the specification it follows. For DSR 2023 this is CPWD Specifications 2019 Vol. I and II.
3. Read `describe_source section=category:<name>` for each chapter you will use. Category notes say what items include and which item to pick.
4. Record the project specification clauses that change measurement or inclusions (for example "plaster measured both faces", "formwork included in RCC rate").

If the user has not said which schedule applies, list the attached sources and ask. Do not assume an edition.

## 2. Take off the quantities

Work drawing by drawing, location by location (block, floor, grid, room). For each work item:

- **Unit.** Use the unit of the adopted item. It normally follows IS 1200: cum for concrete and full-brick or thicker masonry, sqm for half-brick walls, formwork and plaster, kg for reinforcement. A compound unit ("cum per metre depth", "per bag of cement") means the quantity is that product.
- **Dimensions.** Measure net as fixed in place. Book length, breadth or width, then height, depth or thickness. Use the adopted trade rule for precision. For concrete, dimensions generally go to 0.01 m, areas to 0.01 sqm, volumes to 0.01 cum and slab thickness to 0.005 m (IS 1200 Part 2, 2.4.1).
- **Gross quantity first, then deductions.** Measure the gross element, then list each deduction as its own line with the rule that requires it. Record openings that fall below a deduction threshold too, marked "not deducted (threshold)", so a reviewer can check them.
- **Stages and conditions.** Keep work below and above ground or datum level separate where the item or specification requires it (IS 1200 Parts 2, 3 and 5, measurement in stages). Measure work in or under water, in liquid mud or in foul positions separately. Floor-level extras (for example DSR "above floor five level, for each four floors") are separate items for the same quantity.
- **Included or separately payable.** Before you add a line, check whether the item already includes the work. Use the item text, the specification and the category notes. Examples: a DSR RCC item excludes formwork, reinforcement and finishing. Brickwork includes raking out joints for plaster and building in lintel ends (IS 1200 Part 3, 3.1.1). Give each excluded component its own line. Never measure an included component again.

Work-category rules and their checks are in the references:

- [Concrete, formwork and reinforcement](gestimator://skills/in/civil-measurement-estimation/references/concrete.md)
- [Masonry](gestimator://skills/in/civil-measurement-estimation/references/masonry.md)
- [Plaster, pointing and finishes](gestimator://skills/in/civil-measurement-estimation/references/finishes.md)
- [Floor and roof layers, openings and bar schedules](gestimator://skills/in/civil-measurement-estimation/references/building-assemblies.md)
- [Earthwork](gestimator://skills/in/civil-measurement-estimation/references/earthwork.md)
- [Standards register and verification status](gestimator://skills/in/civil-measurement-estimation/references/standards.md)

## 3. Design inputs and checks

Collect these inputs before measuring. If one is missing, name the quantity or item match it blocks. Continue with the quantities you can establish and list the gap in the draft.

| Work | Inputs that set quantity or item choice |
|---|---|
| Masonry | Wall type and material (brick class, block), thickness, mortar mix, location (foundation, plinth, superstructure, floor level), wall lengths and heights, opening sizes and lintel or sill details, finish scope (plaster, pointing, exposed face) |
| Concrete | Element type (footing, column, beam, slab, chajja, stair), grade or nominal mix, design or nominal mix, location (up to plinth, above plinth up to floor five, higher), element dimensions, openings and embedded items, finish |
| Formwork | Contact faces of each element, slab thickness over 200 mm, beam depth 1 m and over, sloping or curved surfaces, exposed-finish requirement |
| Reinforcement | Bar bending schedule or detailing drawings, steel grade (Fe 500 TMT and so on), lap and chair rules of the specification |
| Plaster and finishes | Surfaces to be finished, plaster type, thickness and mix, both or one face, height above 10 m, ceiling or wall, paint system |
| Earthwork | Soil or rock classification, foundation plan and bottom levels, authorised working space, lift and lead, disposal location, filling material |

Checks before you present the draft:

- Every quantity can be traced to a drawing, schedule or stated assumption.
- Units match the proposed item, and the arithmetic in each line is shown.
- Deductions follow the threshold rules of the governing part. Openings below a threshold are listed and not deducted.
- Junctions are measured once (for example a column through a beam, or a slab over a wall).
- Each separately payable component has its own line (formwork, reinforcement, finishes, extras).

## 4. Record measurement lines

Record every line with these fields:

| Field | Content |
|---|---|
| Work | Short description of the work ("230 mm brick wall, 1:6, superstructure") |
| Location | Block, floor, grid or room |
| Count / dimensions | No × L × B × H, as booked |
| Unit | Unit of the proposed item |
| Calculation | The arithmetic, for example `2 × 4.20 × 0.23 × 3.00 = 5.80` |
| Deduction | Negative lines with the reason and rule ("D1 1.0 × 2.1 opening > 0.1 sqm, IS 1200 Part 3, 4.1.4(b)") |
| Source | Drawing number and revision, schedule row, model element ID or user statement |
| Assumptions | Any value not taken from a source, marked provisional |

Use separate records for each identifiable storey, room, grid, element or route. For IFC, check model units and storey containment, count placed instances and record element IDs or identifiable ranges. If the source lacks that detail, record the finest supported location and mark each assumed quantity with its basis. Verify that openings and junctions are accounted for once.

The source field is independent of how the quantity was obtained. A manual takeoff, a schedule row and a model export all enter the same line format. In the `_1_NLBH` template each record is No, L, B, H. Its total is the product of the non-empty fields. Enter a deduction as a record with a negative No.

## 5. Match schedule items

1. Search with `search_items` using the work, material, mix and location words ("brick work superstructure 1:6", "centering shuttering slab"). Results give the parent heading; children add only the variant.
2. Read the candidates with `get_items`. Compare the heading and child description, unit, specification reference and inclusions with the measured work.
3. Propose one item per line. Say why it fits. Mark it **ambiguous** when two items fit or an input decides between them. Mark it **unmatched** when no item fits. Never use a heading, a resource (basic rate), a mortar or a sub-analysis as a BOQ item.
4. Do not add GST, overheads, water charges or cess on top of a complete schedule rate.

## 6. Present, then apply on request

Present the draft as a table: measurement lines grouped by proposed item, totals, ambiguous and unmatched items, missing inputs and assumptions. Ask the user to review it.

Write only when the user asks you to apply the estimate:

- `import_items` to bring the matched items into the project (it keeps their ancestors and returns a `code_map`).
- `get_measurements` lists existing measurement categories as rows of type `Heading`. Group sheets by work package, phase or location. Reuse a suitable heading or use `edit_measurements` with `{"action":"create","description":"Ground-floor concrete","ref":"ground-floor"}` to create one. Set `category` on each sheet to the heading ID or the same-call reference (for example `$ground-floor` or `$lighting`). Verify each sheet's `category_id` with `get_measurements`.
- Use `get_measurements section=templates` to check editable columns and outputs, then `edit_measurements` to create and link the sheets and fill their records. For related quantities measured in the same rows, use `_2_LLLLL` (L1–L5) or `_3_NNNNNNNN` (N1–N8), linking each column to its schedule code in column order. Use `_1_NLBH` when a quantity needs a product of dimensions, and use the appropriate specialised template for reinforcement and other template-specific calculations.
- `recalculate what=quantities` with an explicit rounding choice.
- `edit_analysis` only when the user asks for a rate analysis change.
- Group related writes in `batch` so they are one undo step. Pass `if_revision` from the last response. Use `preview: true` where a tool offers it before a large change.

Fix validation errors from the field and hint they return. Do not retry the same call unchanged. Check `get_summary` after writing. The deliverable is the saved GEstimator project (`project action=save_copy` for a new project, then `save`). Make a workbook only when the user asks for one: export it with `project action=export_xlsx` and do not edit the exported file, because its total is GEstimator's total. The Schedule sheet ends with the imported analysis dependencies (the SUB ANALYSIS category) at zero quantity; they add nothing to the total. If a total looks different from `get_summary`, report it rather than correcting the file.

For an early brief without structural drawings, use [concept quantities](gestimator://skills/in/civil-measurement-estimation/references/concept.md). Reconcile [shared building and site items](gestimator://skills/in/civil-measurement-estimation/references/package-interfaces.md) before combining BOQs.
