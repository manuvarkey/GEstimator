---
name: civil-takeoff
description: Measure civil and building works from drawings, schedules or IFC quantities using the project's specification and available rate libraries.
---

# Civil takeoff

Use the contract specification, adopted measurement rules and full schedule description to decide what is payable. Read `get_state` for the available libraries, then use `describe_source` for source and category notes. Search the project and suitable libraries for each work type, and check the full definitions and units with `get_items`.

## Plan the takeoff

- Inventory the source by building and storey, then by room, grid, zone or element where identifiable. Create measurement headings for distinct work packages and phases, such as foundations, ground-floor structure, finishes and roof. Combine phases only where the breakdown remains clear from the records.
- For an IFC model, read the units, placement and spatial containment of installed instances. Use trustworthy quantity sets where available. Reconcile computed geometry with known dimensions and check for openings, element junctions and duplicate instances. Record model element identifiers or an identifiable range.
- Break down concrete by elements, masonry by wall type and location, and finishes by room or surface. Record counts and dimensions separately, show deductions explicitly, and avoid counting shared junctions or included work twice.
- When room or element data are missing, use the most detailed location you can substantiate. Mark each inferred dimension, count or allowance provisional and record its basis. Keep measured values and allowances in distinct records.

## Write and verify

Review the draft breakdown, uncertain quantities and item matches with the user. Apply when requested. Import matched definitions and use the returned `code_map` to link them. Read `get_measurements section=templates` for editable fields and outputs. Use dimension and count columns for the arithmetic and put the location, source and assumption in each record's description.

In `edit_measurements`, create each heading with a description and a `ref`, omitting `template`. Use `after` to place each new heading after the previous group. Pass `category: "$ref-name"` on every sheet in that heading's group, or pass an existing heading ID. Use one multi-output sheet for work measured together where a matching template exists. Check each sheet's `category_id` in `get_measurements`, recalculate quantities, review `get_summary` and save the project.
