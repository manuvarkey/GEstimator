---
description: Size preliminary lightning interception and down paths by protection class and derive auditable conductor, earthing and SPD takeoff.
---

# From protection class to quantities

SP 7:2026 Part D Section 2, Tables 3 and 4, gives the following layout data. CPWD Internal 2023 Appendix H Tables H-3 and H-4 give the mesh and down-conductor spacing basis. Use the class selected for the whole protected zone.

| Class | Rolling sphere radius, m | Maximum square mesh side, m | Typical down-path spacing, m |
|---|---:|---:|---:|
| I | 20 | 5 | 10 |
| II | 30 | 10 | 10 |
| III | 45 | 15 | 15 |
| IV | 60 | 20 | 20 |

**Interception.** For a rectangular flat roof include the perimeter and divide each dimension into whole bays no wider than the class mesh limit. Put conductors on exposed edges and connect intersections to give alternative paths to earth. Check every higher roof level, parapet, PV array, tank and antenna in elevation. Use the rolling sphere for complex shapes; a projection touched by the sphere needs a revised interception layout. A protective angle depends on class and air-terminal height above the protected plane. Use the adopted chart. CPWD §9.1 excludes early-streamer and dissipation devices.

**Down paths and materials.** Place paths near exposed corners and distribute them around the perimeter. Route directly, allow for actual offsets and avoid shared shafts. Check separation at the closest approach to services using the applicable Part 3 method, class, current sharing, insulating medium and path to the bonding point. For the simplified CPWD Appendix H.6 case, s = ki × kc × l / km. Use the applicable class coefficient, current partition and insulation medium, and measure l along the lightning path to its nearest equipotential bonding point. For a supplied Class III assessment with ki = 0.04, kc = 1, km = 1 (air) and l = 12 m, s = 0.48 m. An actual clearance of 0.30 m fails that check. For branched paths or multiple media use the adopted detailed method. Where separation fails, revise the geometry or provide an engineered bonding and surge solution. Credit structural steel only with accepted continuity details and testing provisions. For exposed conductor costing, CPWD H-10 lists solid copper tape at 50 mm² minimum; verify dimensions, mechanical duty, fasteners and metal compatibility. Earth electrodes use the separate H-11 criteria. Keep aluminium out of concrete and soil under CPWD §9.4.

**Earth and internal protection.** Coordinate foundation or ring electrodes with the building earth network and main bonding bar. For CPWD Type B external rings check the required soil contact (at least 80% of ring length), soil resistivity, effective radius and any supplementary electrodes. One down path need not equal one independent pit. Allow accessible test points, equipotential connections, inspection and touch/step-voltage measures. At each lightning protection zone boundary identify conductive services. Coordinate lightning-current capable Type 1 protection at entries exposed to partial lightning current, Type 2 downstream and Type 3 at equipment where needed; include power, PV and signal interfaces as applicable. Select performance by earthing system, impulse current duty, continuous voltage, protective level, backup protection and equipment withstand. Count one device/assembly per actual protected interface and check panel inclusions.

**Worked layout.** LPS-01 rev A: unobstructed 30 × 20 m flat roof, 12 m straight external down routes, approved Class III, no natural conductor credits. Two bays along each dimension give 15 × 10 m cells. Three runs of 30 m plus three of 20 m give **150 m roof conductor including the perimeter**. Four corner downs plus one midpoint on each side give eight paths, spaced 15 m or 10 m. Book **96 m of down conductor** and eight accessible test joints for the specified external arrangement. A rectangular Type B ring drawn 1 m outside the walls measures 32 × 22 m on plan, **108 m of ring conductor**. Add the eight actual ring connections from the detail; offsets, clamps, cross joints, fasteners and test chambers need their own measured or enumerated basis. A later rooftop tank reopens interception and separation checks.

Record separate measurement lines by roof run, down ID and earth segment; keep conductor material and section against each. List existing site earth items reused, SPD locations and ratings pending, verification of continuity, earth tests and as-built inspection. A low measured resistance alone cannot establish satisfactory interception, bonding or surge protection.
