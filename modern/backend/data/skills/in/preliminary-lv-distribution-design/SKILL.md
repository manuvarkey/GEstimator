---
name: preliminary-lv-distribution-design
description: Plan Indian LV circuit topology, room isolation, rising mains, indoor and outdoor routes, and size copper or aluminium feeders using IS 732.
---

# Preliminary LV distribution design

Use IS 732:2019 as the LV design basis. Record the applicable CEA provisions, authority, project specification and adopted amendments. For an issued design, use [electrical takeoff](gestimator://skills/in/electrical-measurement-estimation).

- For a new distribution scheme, read [circuits, isolation and routes](gestimator://skills/in/preliminary-lv-distribution-design/references/distribution-layout.md). Return the source panel, destination, isolation point, route segments and core functions.
- For a known copper conduit run, use [copper sizing](gestimator://skills/in/preliminary-lv-distribution-design/references/feeder-selection.md). For an eligible aluminium feeder, use [aluminium sizing and terminations](gestimator://skills/in/preliminary-lv-distribution-design/references/aluminium-feeders.md). Read the applicable card once across similar circuits.
- Use [mixed-load checks](gestimator://skills/in/preliminary-lv-distribution-design/references/method.md), the [supplier-data example](gestimator://skills/in/preliminary-lv-distribution-design/references/worked-example.md) or the [standards register](gestimator://skills/in/preliminary-lv-distribution-design/references/standards.md) as needed. Identify the governing sizing check, unresolved protection checks and payable route quantities.

- Starting from room loads, build the [DB and phase schedule](gestimator://skills/in/preliminary-lv-distribution-design/references/board-schedule.md). Select the [wall installation method and containment](gestimator://skills/in/preliminary-lv-distribution-design/references/containment.md) for each distinct route.
- Check [fault protection and protective earthing](gestimator://skills/in/preliminary-lv-distribution-design/references/fault-and-earth.md) for the proposed devices. For multiple supplies use [source and backup planning](gestimator://skills/in/preliminary-supply-planning).

For offline sizing, work one circuit or repeated circuit type at a time. Keep its ID, installation method, mm², corrected amps, protection setting, drop and unresolved checks on the same row. Reject any candidate below its protection setting. Reconcile the number of unique board and circuit IDs across floors before totalling. Read another card only when the next decision needs it.

For board totals, conduit limits or a feeder shortlist, use the [local calculation checks](gestimator://skills/in/preliminary-lv-distribution-design/references/local-checks.md) before reporting results.
