---
description: Run local read-only arithmetic checks for board counts, conduit capacity, feeder overload and missing fault data before carrying sizes to the estimate.
---

# Check sizes with the local calculation tool

With a project open, run the applicable SELECT via the MCP query tool. The result is a preliminary check for the inputs entered. Substitute the project ID for the example label. Carry returned columns directly to that circuit’s worksheet. Show the governing row and residual checks beside the BOQ item; a model-generated summary can transpose values between rows. Replace example values with actual schedule counts, ratings and corrections. If any input or reference method is unknown, mark that check pending. Without a project use the same inequalities with a local calculator. Avoid opening or changing a project solely to check arithmetic.

For two identical floors, three room boards per floor and two final circuits per room board (light and power), bind params [2, 3, 2] in that order. Include floor feeders separately.

```sql
WITH layout(floors, rooms, circuits) AS (VALUES (?, ?, ?))
SELECT 'office' AS building_id, floors * rooms AS room_boards, floors * rooms * circuits AS final_circuits FROM layout
```

For a bent conduit with equal 4 mm² PVC wires under CPWD Table 4.1, bind the physical count, e.g. [3] for L/N/PE. The rows below apply only to that construction and size. An empty result means the shortlist is exhausted.

```sql
WITH conduit(mm, wires) AS (VALUES (20, 2), (25, 5), (32, 8))
SELECT 'A-P' AS circuit_id, mm AS conduit_mm, wires AS max_wire_count FROM conduit WHERE wires >= CAST(? AS INTEGER) ORDER BY mm LIMIT 1
```

For the example aluminium D1 feeder, bind design amps, breaker setting, device I2 and applicable combined correction factor in that order, e.g. [90, 100, 130, 0.93]. Return all passing rows so the subsequent drop check can increase the size.

```sql
WITH cable(mm2, amps) AS (VALUES (35,90), (50,106), (70,130), (95,154), (120,174)),
duty(ib, setting, i2, factor) AS (VALUES (?, ?, ?, ?))
SELECT 'annex' AS feeder_id, mm2 AS candidate_mm2, round(amps * factor, 2) AS corrected_A FROM cable, duty
WHERE ib * 1.0 <= setting * 1.0 AND amps * factor >= setting * 1.0 AND 1.45 * amps * factor >= i2 * 1.0
ORDER BY mm2
```

Expected first passing row is 70 mm² at 120.90 A. Check voltage drop, applicable cable and equipment limits separately. No row in this query assesses breaking capacity. When source fault level is unknown, record **breaking capacity pending — utility fault level required** even when overload and voltage drop pass. Never infer a fault-duty pass from the selected mm².
