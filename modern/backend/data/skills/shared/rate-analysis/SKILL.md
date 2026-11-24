---
name: rate-analysis
description: Prepare or adapt a rate analysis by finding suitable project items, schedule analyses and library resources before creating custom rates.
---

# Rate analysis

1. Read `get_state` and use the project, attached `sources` and relevant `available_sources`. Use an attached ID or the returned library `path` as `source`. Read the source overview and relevant category notes with `describe_source`.
2. Search for the work and its significant components with `search_items kind=schedule`. Use `browse` to compare variants and `get_items kind=schedule include=["analysis","resources"]` to inspect promising analyses. Check the unit, specification, inclusions, source date and rate basis. For a composite item such as building demolition, look for separate compatible component items for concrete, masonry, handling and disposal.
3. Adapt a suitable project analysis with `upsert_items` and `duplicate_from` if the original item must remain available. For a library item use `import_items` and read its `code_map`. Update the imported or duplicated analysis with `edit_analysis`. When copying criteria or prices, record what changed and why. Retain distinct compatible components as measured items when the estimate calls for separate items.
4. Search `kind=resource` for labour, plant and materials in the project and relevant rate libraries. Add accepted resources to an analysis with their code, source and quantity, omitting `rate` so GEstimator resolves the existing definition. Create custom resources for remaining gaps. Record each assumed price with its currency, unit and basis. Match quantity units to each resource's rate unit.
5. State the quantity basis of the analysis and how it converts to the schedule unit. Use one `edit_analysis` with ordered `ops` per item. Address existing rows and resource lines with `r0` and `r0:0`. For new groups, add a `ref` and use it as the resource insertion ID. Add allowances, overheads, taxes or credits only where the adopted basis calls for them and avoid counting included costs twice.
6. Present the proposed analysis and assumptions for review. Use `preview: true` to check the rate before applying if needed. Group related edits in one `batch` where appropriate. Verify totals with `get_summary` and save the project separately.

The MCP text result includes the response data for clients that only display text. Read tool errors and their hints before retrying. Use typed reads for discovery and inspection.
