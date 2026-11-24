---
name: electrical-takeoff
description: Take off electrical points, equipment and runs by room, storey and circuit using the project's specification and available rate libraries.
---

# Electrical takeoff

Read the layouts, fixture and distribution schedules, and project specification. Use the adopted measurement rules and full item descriptions to determine whether equipment supply, point wiring, controls and circuit wiring are payable separately. Read `get_state` for available libraries, read their source and category notes, and compare candidate definitions with `get_items`.

## Plan the takeoff

- Count fixtures, controls, fans and sockets by room and floor. Record equipment type, rating and mounting where they affect item selection. Keep separate records for distinct circuits or rooms, even when the same schedule item applies.
- Measure cable, conduit and tray by route, recording endpoints, lengths and drawing or model references. Reconcile circuits with the distribution schedule and check for omissions and overlapping scope.
- Use headings such as lighting, small power and distribution by floor or phase. If the model contains no electrical layout, distinguish assumed fixtures, point counts and route lengths from measured geometry. Mark provisional records with their location, source and basis, and use the finest breakdown the evidence supports.
- For preliminary lighting design requested without a layout, use the project's specified lighting targets and luminaire data. Record room dimensions, target illuminance, fixture output and the basis of each assumed utilisation and maintenance factor. Label resulting counts provisional.

## Write and verify

Review the draft quantities, assumptions and item matches with the user. Apply when requested. Import matched schedule definitions and use the returned `code_map`. Read `get_measurements section=templates` for editable columns. Group related counts or run lengths on a multi-output sheet with links in output order.

Create headings with `edit_measurements` using `description` and `ref` without a template. Use `after` to place each new heading after the previous group. Give every sheet the heading ID or same-call `$name` as `category`. Put the room, circuit or route and source in each record's description. Verify sheet `category_id`, recalculate linked quantities, review `get_summary` and save.
