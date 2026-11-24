---
name: electrical-measurement-estimation
description: Electrical installation takeoff for a GEstimator estimate (point wiring, circuit and submain wiring, sockets, switchgear and distribution boards, luminaires, fans, cables, earthing). Read before counting points or equipment, measuring wiring runs, matching DSR (E&M)/SOR items, or writing electrical measurements and BOQ items.
---

# Electrical measurement estimation

Use this skill to turn electrical layouts, schedules or model quantities into measurement lines and proposed schedule items. The project specification, the electrical specification the schedule follows and the full description of the adopted item decide what each item includes and how it is counted.

**Work inside GEstimator.** The estimate is the GEstimator project: schedule items with linked measurement sheets. Record each quantity as measurement records with its dimensions or counts, deductions, location and source, so the project shows how it was derived. Do not compute quantities in a script or spreadsheet and enter only totals, and do not keep the estimate in a separate workbook; when a workbook is wanted, use `project action=export_xlsx`.

**Order of work.** Read this skill and the references for the work first. Then read the database notes (`describe_source` overview, then `section=category:<name>` for each category) **before** searching for or choosing items, not afterwards to check them. Read a linked reference as an MCP resource, or with `describe_source section=<its gestimator:// link>`.

**Sources.** Use the GEstimator sources, their notes and these skills. Do not search the web for rates, schedule books, item texts or standards: the attached source is the adopted schedule, and these skills carry the standards checked for this work. Cite the schedule by the book and edition its notes give (`describe_source` overview). Where an item, criterion or clause is not covered, state the assumption and list it for review instead of looking it up.

## 1. Establish the basis

1. Call `get_state`. Note the open project and the attached sources. Skills are readable without an open project, but measurements need one.
2. Identify the adopted schedule and edition. Call `describe_source` on it and read its About section. DSR (E&M) 2025 follows the CPWD General Specifications for Electrical Works Part I Internal 2023, Part II External 2023 and the other parts its notes list.
3. Read `describe_source section=category:<name>` for each chapter you use. The WIRING notes explain point classification, groups and twin control. Read them before counting points.
4. Record the project specification clauses that change counting or inclusions (wire size, conduit type, switch type, earthing).

If the user has not said which schedule applies, list the attached sources and ask.

## 2. Take off the quantities

Work location by location (block, floor, room or area):

- **Points (unit Point).** Count from the layout. A point is counted, not measured. Count by point type (light, fan, exhaust fan, call bell, socket where the schedule counts sockets as points) and by control arrangement. Under the CPWD Electrical Part I Internal 2023 specification (3.4.3 to 3.4.8), a group-controlled light, a twin-controlled light and a multi-push bell are counted differently, and socket wiring is measured per metre. Apply the rules in the [wiring reference](gestimator://skills/in/electrical-measurement-estimation/references/wiring.md).
- **Equipment (unit Each or Set).** Count luminaires, fans, switches, distribution boards, MCBs, isolators, RCCBs, sensors and earth electrodes from the layout and the schedules. Record the type and rating of each: wattage or efficacy band, sweep, current rating and poles, number of ways.
- **Runs (unit Metre).** Measure circuit wiring, submain wiring, socket wiring, cables and trays only where the item is per metre. Take the length along the conduit or cable route on the drawing, including drops and rises to the switchboard or equipment. Under the CPWD specification, exclude interconnections inside switchboards and any allowance for diversion or slack (3.3.2). State the route you assumed when no routing drawing exists.
- **Capacity units.** For an item "Per TR" or "Per HP", the quantity is capacity × number of units.

Before you add a line, read the item description and check what it includes. In the DSR (E&M), point wiring includes conduit, switch box, switch, cover and loop earthing. An SITC luminaire item includes installing and connecting the fitting. An "installation only" item excludes the equipment. A DB item is the empty board, and each MCB is a separate item. Give each excluded component its own line and never count an included one again.

Category references:

- [Wiring, points and sockets](gestimator://skills/in/electrical-measurement-estimation/references/wiring.md)
- [Distribution, cables and earthing](gestimator://skills/in/electrical-measurement-estimation/references/distribution.md)
- [Luminaires, fans and lighting controls](gestimator://skills/in/electrical-measurement-estimation/references/luminaires.md)
- [Standards register and verification status](gestimator://skills/in/electrical-measurement-estimation/references/standards.md)

When the user explicitly asks for a preliminary lighting design (no lighting layout exists), read the `preliminary-lighting-design` skill. Treat its fixture counts and layout as provisional inputs to this skill.

## 3. Design inputs and checks

Collect these inputs before measuring. If one is missing, name the quantity or item match it blocks. Continue with the quantities you can establish and list the gap in the draft.

| Input | What it decides |
|---|---|
| Lighting and power layouts | Point counts by type and room, socket positions, fan positions |
| Building type | The point wiring group in the DSR (E&M) (Group A, B or C) |
| Luminaire schedule | Fixture type, wattage, efficacy band, mounting, and whether supply is in the electrical item |
| Switching and control arrangement | Single, twin or group control; sensors and dimming; the number of normal and looped points |
| Wiring specification | Conductor size, conduit type (steel or PVC), surface or recessed, switch type (piano or modular) |
| DB and circuit schedules, single-line diagram | DB type and ways, MCB ratings and poles, RCCBs, circuit and submain sizes |
| Circuit capacity rule | Number of lighting and power circuits, so the number of circuit runs and MCB ways (NBCS 2026 Part D Section 2, 5.4.4.3; CPWD 3.10: a light circuit at most 800 W or 20 points) |
| Routing (conduit, cable, tray) | Lengths of circuit, submain, socket and cable runs |
| Equipment ratings | Fan sweep, exhaust fan size, sensor type, earth electrode type |

Checks before you present the draft:

- Point totals per room match the layout; group, twin and bell points follow the counting rules.
- Each lighting circuit stays within the adopted capacity limit; the circuit count matches the MCB ways.
- Every metre-based quantity states its route or its assumption.
- Supply and installation are neither missing nor counted twice (SITC against installation-only items).
- Each DB has its MCBs, RCCBs and isolators counted.
- Units match the proposed item, and the arithmetic in each line is shown.

## 4. Record measurement lines

Record every line with these fields:

| Field | Content |
|---|---|
| Work | Short description ("light point, PVC conduit, modular switch") |
| Location | Block, floor, room or area |
| Count / dimensions | Number of points or items, or the run length breakdown |
| Unit | Unit of the proposed item |
| Calculation | The arithmetic, for example `2 + 4 = 6` or `3.5 + 12.0 + 2.5 = 18.0` |
| Deduction | Rarely needed; record any adjustment with its reason |
| Source | Drawing number and revision, schedule row, model element ID, design output or user statement |
| Assumptions | Any value not taken from a source, marked provisional |

Use separate records for each identifiable storey, room, grid, element or route. For IFC, check model units and storey containment, count placed instances and record element IDs or identifiable ranges. If the source lacks that detail, record the finest supported location and mark each assumed quantity with its basis. Verify that openings and junctions are accounted for once.

The source field is independent of how the quantity was obtained. A layout count, a schedule row and a model export all enter the same line format. Use `elec_tableofpoints` (Lights, Fans, Ex.Fans, Call Bells, Other) when those counts contribute to one schedule item. Use one `_3_NNNNNNNN` sheet for related counts from the same locations that have separate schedule codes, such as normal points and group-controlled points. Use `_2_LLLLL` for related run lengths. Enter links in N1–N8 or L1–L5 order. Check the editable columns and number of outputs with `get_measurements section=templates`.

## 5. Match schedule items

1. Search with `search_items` using the work and its variant ("light point PVC conduit modular switch", "SPN MCB distribution board 8 way"). Children carry only the variant ("Group C", "36 watt"); the heading holds the specification.
2. Read candidates with `get_items`. Compare heading + child description, unit, specification and inclusions with the measured work.
3. Propose one item per line and say why it fits. Mark it **ambiguous** when an input (building type, efficacy band, conduit type) decides between items. Mark it **unmatched** when no item fits. Never use a heading or a resource (basic rate) as a BOQ item.
4. Do not add GST, overheads, cartage or cess on top of a complete schedule rate.

## 6. Present, then apply on request

Present the draft as a table: measurement lines grouped by proposed item, totals, ambiguous and unmatched items, missing inputs and assumptions. Mark lines that come from a preliminary design as provisional. Ask the user to review it.

Write only when the user asks you to apply the estimate:

- `import_items` to bring the matched items into the project.
- `get_measurements` lists existing measurement categories as rows of type `Heading`. Group sheets by work package, phase or location. Reuse a suitable heading or use `edit_measurements` with `{"action":"create","description":"First-floor lighting","ref":"lighting"}` to create one. Set `category` on each sheet to the heading ID or the same-call reference (for example `$ground-floor` or `$lighting`). Verify each sheet's `category_id` with `get_measurements`.
- Use `get_measurements section=templates`, then `edit_measurements` to create and link sheets and fill the records. Combine quantities measured on the same rows in one multi-output sheet when the template fits.
- `recalculate what=quantities` with an explicit rounding choice.
- `edit_analysis` only when the user asks for a rate analysis change.
- Group related writes in `batch`. Pass `if_revision` from the last response. Use `preview: true` where a tool offers it.

Fix validation errors from the field and hint they return. Check `get_summary` after writing. The deliverable is the saved GEstimator project (`project action=save_copy` for a new project, then `save`). Make a workbook only when the user asks for one: export it with `project action=export_xlsx` and do not edit the exported file, because its total is GEstimator's total. The Schedule sheet ends with the imported analysis dependencies (the SUB ANALYSIS category) at zero quantity; they add nothing to the total. If a total looks different from `get_summary`, report it rather than correcting the file.
