# DSR (E&M) 2025: database notes

Read this before choosing items from this database. The general part says what the database is and how its items are built. Each `## Category:` section describes one chapter: what it covers, how its items are arranged and how to pick the right one. Read the section of every category you take items from.

## About

- **Book:** CPWD Delhi Schedule of Rates (E&M) 2025 and Delhi Analysis of Rates (E&M) 2025. Published by the Directorate General, CPWD, Nirman Bhawan, New Delhi; foreword dated July 2025.
- **Corrections:** Correction Slip No. 1 dated 27-11-2025 is applied (31 rates, description changes, 39.10 deleted, Appendix I 1020 replaced by 1021, Appendix II cable rates 5246–5249). Items it changed say so in their remarks.
- **Supersedes:** DSR (E&M) 2022, DSR (E&M) for Solar PV Power Plant 2019, DSR (E&M) for Facade Lighting 2019, DSR (E&M) Energy Efficient Materials Vol. II 2025. New chapters: CCTV, EPABX/IP-PBX, LAN, access control, BMS, fountains, lifts.
- **Specifications:** works are to be executed to the CPWD General Specifications for Electrical Works Part I Internal 2023, Part II External 2023, Part III Lifts & Escalators 2003, Part IV Sub-station 2013, Part V Wet Riser & Sprinkler 2020, Part VI Fire Detection & Alarm 2018, Part VII DG Sets 2013, Part VIII Gas Based Fire Extinguishing 2013, the CPWD General Specifications for HVAC Works 2024, BIS codes, and ENS 2024 / ECSBC 2024.
- **Rates:** schedule rates are complete: material, labour, taxes and duties (Delhi), T&P, overheads and profit, and GST on works contracts. They apply to a working height up to 4.5 m from floor level unless the item says otherwise. Rates are indicative; actual rates are governed by the market.
- **Appendix I and II (resources):** basic rates of labour and materials. These **exclude** contractor's profit, overheads, carriage and taxes; the analyses add them.
- **Source data:** the CPWD workbook "DSR EandM 2025 3 09 2025", with the schedule's numbering, text and rates taken from the printed book. Where the printed rate disagrees with the printed analysis, the analysis rate is kept and the item's remarks say so. Full build notes: `spreadsheets/DSREM2025/README.md` in the GEstimator repository.

## How the items are built

- **Codes** follow the book: chapter.item[.sub-item[.sub-sub-item]], e.g. 1.7.3 or 30.7.1.4. A chapter is a category. Gaps in the numbering are items the book prints as DELETED.
- **Headings and items.** A row with rate 0 and children is a heading: its description is the common specification, and each child adds only the size, rating or variant ("Group A", "2 X 4 sq. mm + 1 X 4 sq. mm earth wire", "18 watt"). Always use a priced child, never the heading; the full meaning is heading text + child text. Some headings (30.7, 30.11) carry only a title over further headings.
- **Supply and installation vs installation only.** "Supplying, installation, testing and commissioning" (SITC) items include the equipment. "Installation, testing and commissioning", "Erection of", "Laying of", "Fixing of" items are labour and fixing materials only; the equipment, fitting or cable is supplied separately (from another item, or by the client). Items "in the existing ..." (box, conduit, panel, pipeline, trench) assume that part already exists.
- **Analysis structure.** Labour-and-material items: materials, cartage 1 % of materials, labour, overheads and profit 15 %, labour cess 1 %, GST 18 %. Equipment items (transformers, DG sets, UPS, chillers, LED fittings and most SITC equipment): material (A), cartage 1 %, "ITC @ 4 % of A" in place of labour, overheads and profit 15 %, labour cess 1 %, GST 18 %. Some analyses price a lot (10 sq m, 100 m) and divide.
- **Resource codes.** Four-digit ICD codes from the book: 1001–1021 labour and hire charges (Appendix I; 1001 wireman, 1007 khallasi, 1021 technician), 1101 onward materials (Appendix II). Resources in the category RESOURCES FROM ANALYSES are lump sums the book prices only inside an analysis (battery racks, pump controllers, tanks); their rate is the book amount ÷ quantity. "X – Unit item" (unit Rs, rate 1) carries a lump sum the book adds without a quantity.
- **Units:** Point, Metre/Meter, Each, Set, sq. m, cum, kg, kWp, Per HP, Per TR. A "Per TR" or "Per HP" item is priced per unit of capacity: quantity = capacity × number of units.
- **Book inconsistencies** kept as published: 17 analyses differ from their rate by ₹1 and about 190 by a fraction of a rupee (unrounded intermediate amounts). The printed schedule disagrees with the printed analysis in 197 items; the analysis rate is used. 6.12 (testing joint) has no printed analysis; the workbook's (₹140) is used against a printed rate of ₹3614.

## Category: WIRING

Internal wiring in buildings (CPWD General Specifications Part I, clauses 3.3–3.4).

- **Point wiring** (unit Point) is the wiring from the controlling switch or MCB to the outlet (ceiling rose, connector, holder) of a light, fan, exhaust fan or call bell point, including conduit, switch box, switch, cover and loop earthing. It is counted per point, not measured.
- **Groups A, B, C** are classified by **building type**, not by length (clause 3.4.4): Group A for Type I, II and III residential quarters and hostels; Group B for Type IV and above residential quarters and barracks; Group C for all non-residential buildings (offices, hospitals, laboratories, educational institutions, libraries). For other buildings the Chief Engineer (Elect.) decides. Choose the group from the building, then the item from the conduit and switch type.
- **Point wiring items:** steel conduit with piano switch 1.1 (single control), 1.2 (twin control); steel conduit with modular switch 1.3, 1.4; PVC conduit with piano switch 1.8, 1.9; PVC conduit with modular switch 1.10, 1.11. Group-controlled (looped) points without an independent switch: 1.54 (steel), 1.55 (PVC). Rewiring in existing conduit: 1.15, 1.16.
- **Measuring points:** a twin control light point (two 2-way switches) is two points (clause 3.4.7), so the twin control items 1.2, 1.4, 1.9, 1.11 are priced per such light. Several points on one switch: the first is a point, each further point (outlet to outlet) a looped point (clause 3.4.6).
- **Circuit and submain wiring** (per metre, along the run): circuit wiring runs from the distribution board to the first switch box; submain wiring from one switchboard to another. Items 1.7 (steel conduit) and 1.14 (PVC conduit), by number and size of wires; the earth wire is included in the item.
- **Socket outlet (light plug 6 A / power 16 A) wiring** is measured per metre from the tapping point (switch box, previous socket or DB) to the socket: 1.5, 1.6 (steel), 1.12, 1.13 (PVC). The socket box, switch and socket are a separate item: 1.29–1.32, 1.56, 1.57.
- **Accessories and parts:** cables drawn in existing conduit 1.17, telephone cable 1.18, TV coaxial 1.19, conduit only 1.20 (steel), 1.21 (PVC), metal boxes 1.22, switches/sockets on existing boxes 1.23 (piano), 1.24 (modular), modular boxes and plates 1.27, 1.28, ceiling rose and holders 1.33, 1.34, 1.58.
- **Installing fittings and fans** (supply excluded; fittings are in LED LIGHT, fans in BLDC FAN): fittings 1.35, 1.41, 1.42; ceiling fans 1.44, 1.45 with extra down rods 1.43, 1.47, 1.48; exhaust fans 1.50, 1.51; numbering 1.49; fan painting 1.52, 1.59.

## Category: MCCB, MCB & DB'S

Switchgear for distribution: TP&N disconnector fuse units in existing panels (2.1), MCCBs in existing panels by rating, breaking capacity and poles (2.2), SPN MCB distribution boards (2.3), horizontal TPN DBs (2.4), vertical TPN DBs (2.5), MCBs in existing DBs (2.10), blanking plates (2.11), isolators (2.12 DP, 2.13 FP), RCCBs 30 mA (2.14 DP, 2.15 FP), enclosures with MCB (2.16, 2.17), industrial sockets (2.18–2.20), danger plates (2.21 MV, 2.22 HT), cable end boxes (2.23–2.25). A DB item is the empty board; add each MCB, RCCB or isolator separately. "Way" counts MCB positions; TPN DBs are "4 + 12" etc. (incomer + outgoing).

## Category: RISING MAINS & BUS TRUNKING

Rising mains and bus trunking per metre (3.1, 3.5, 3.6, 3.8, 3.9, 3.13), with tap-off boxes, distribution tap-off boxes and end feed units each (3.2–3.4, 3.7, 3.11, 3.12). Three families: sheet steel with insulated aluminium bars (3.1–3.7), air insulated compact type (3.8–3.12), sandwich type (3.13). Pick by current rating and short-circuit rating; add end feed units and tap-offs separately.

## Category: CABLE TRAYS

Perforated cable trays by width × depth × thickness: powder coated M.S. (4.1 trays per metre; 4.2 bends, 4.3 tees, 4.4 cross members, 4.5 reducers each) and hot dipped galvanised (4.6 trays per metre; 4.7–4.10 fittings each). Trays include suspenders and supports. Cable laying on trays is in MV CABLE LAYING (10.8).

## Category: EARTHING

Earth electrodes each/set: G.I. pipe 4.5 m (5.1 without, 5.2 with charcoal and salt), G.I. plate (5.3, 5.4), copper plate (5.5, 5.6). Strip and wire electrodes per metre (5.7–5.9). Earth leads from the electrode in G.I. pipe (5.10–5.13), on surface (5.14, 5.15), loop earthing (5.16–5.19; 5.18, 5.19 along existing wiring), copper earth bus (5.20). Choose "with charcoal/coke and salt" only where the soil needs treatment.

## Category: LIGHTNING CONDUCTOR

Finials (6.2 supply and fix, 6.3 fix only), tape jointing (6.4), G.I. tape on parapet or wall (6.7 horizontal, 6.8 vertical; 6.9, 6.10 fixing only), testing joint (6.12), tape from electrode in ground (6.14 supply, 6.15 laying only). Earth electrodes are in EARTHING.

## Category: LIGHTING CONTROLS

Occupancy sensors: PIR (7.1), PIR with daylight dimming (7.2), microwave (7.3); astronomical time switches for street lighting (7.4, by outputs per phase).

## Category: LED LIGHT

LED fittings, supply and installation. Each fitting type is offered in efficacy bands as separate headings: system lumen efficacy ≥105 <120, ≥120 <135 and ≥135 lm/W. Use the band the design or energy code (ECSBC/ENS) requires; children are wattages. Down lighters SMD (8.1–8.3), COB (8.4, 8.5); 2×2 ft panels (8.6–8.8); battens (8.9–8.11); street lights (8.12–8.14); flood lights (8.15–8.17); smart street lights (8.18–8.20); solar outdoor lights (8.21). Poles are in POLE ERECTION; wiring to the point is in WIRING.

## Category: BLDC FAN

Ceiling fans with BLDC motor, supply, installation, testing and commissioning, by sweep (900, 1050, 1200, 1400 mm). 9.1 is controlled by remote (preferably mobile app based); 9.2 is for operation with a regulator. Otherwise the specification is the same. Installation-only fan items are in WIRING.

## Category: MV CABLE LAYING

Laying of 1.1 kV PVC/XLPE power cable per metre, by cable size band; **cable supply is not included** (price the cable separately). Direct in ground with sand cushioning and brick protection (10.1, additional cable in the same trench 10.2), direct in ground without protection (10.3, 10.4), in existing pipe (10.5), in existing open duct (10.6), on wall (10.7), on cable tray (10.8). Route markers 10.9, 10.10. Excavation is included in the direct-in-ground items.

## Category: MV CABLE JOINTING & END TERMINATION

For 1.1 kV aluminium conductor cables, by number of cores and size: end termination with brass compression gland and lugs (11.1), outdoor cast resin end termination (11.2), straight-through joint with cast resin (11.3) or heat shrinkable kit (11.4). One cable needs two terminations.

## Category: POLE ERECTION

Erection of poles (supply excluded): RCC/PCC poles in brick ballast (12.1, struts 12.2), metallic poles in concrete (12.3, struts 12.4); steel pole collars per cum (12.5); G.I. pipe for cable entry (12.6).

## Category: MV OVER HEAD LINE WORK

LT overhead lines: stay sets (13.1–13.9), cross arms (13.10–13.12), D-iron clamps and insulators (13.13–13.20), erection of conductors per kg (13.21–13.25), guards (13.26–13.28), aerial fuses (13.29–13.31), lightning arrestors (13.32, 13.33), street light brackets (13.34), service poles (13.35, 13.36), cable protection pipes on poles (13.37–13.39), dismantling (13.40–13.42). "Erection of" items exclude the material.

## Category: HV OVER HEAD LINE WORK

11 kV and 33 kV overhead lines: stay sets (14.1, 14.14), pole top brackets and cross arms (14.2–14.9, 14.15–14.21), cross bracing (14.8, 14.22), pin and disc insulators (14.10–14.12, 14.23, 14.24), lightning arrestors (14.13, 14.25).

## Category: MISC.CIVIL ITEMS

Civil work for electrical installations: excavation (15.1, 15.2), refilling (15.3), cable trench with sand refilling (15.4, deduction 15.5), trench in hard rock (15.6), concrete in equipment foundations (15.7–15.10), brick work (15.11), plaster (15.12), G.I. pipe (15.13), RCC pipe (15.14) and DWC HDPE pipe (15.15, 15.16) for cables. Items marked "Rate to be taken from Civil DSR" have no rate here (15.1, 15.2, 15.8, 15.10–15.13): take the rate from the Civil DSR. 15.7 and 15.9 carry the rate the analyses use. The book's note lists further civil items (fan clamps, fan boxes, holes for exhaust fans) to be taken from the Civil DSR.

## Category: SOLAR WATER HEATING SYSTEM

Solar water heaters, supply and installation, by capacity in litres per day: evacuated tube collector systems (16.1) and flat plate collector systems (16.2).

## Category: SOLAR PV POWER GENERATION

On-grid solar PV power plant per kWp (17.1), complete as per BIS/IEC/MNRE/CEA requirements.

## Category: ELECTRICAL VEHICLE CHARGER

EV charging stations, supply and installation (18.1): light EV AC charger 7 kW, light EV DC charger up to 7 kW, park-bay AC charger 11/22 kW, park-bay DC charger 24 kW and above.

## Category: FAÇADE LIGHTING

Architectural RGB lighting: LED flood lights (19.1, by wattage), linear profiles / wall washers AC (19.2) and DC (19.3, by wattage per metre), RGB LED strip (19.4), DMX controller (19.5), splitters (19.6), signal amplifier (19.7), DMX decoder (19.8), connectors (19.9), processor (19.10). A system needs fittings plus controller, decoders, splitters and connectors as designed.

## Category: FOUNTAIN

Fountain nozzles of many effects (20.1–20.10), floater rope (20.11), strainers, skimmer and drain (20.12–20.15), submersible pumps (20.16–20.19), gate and non-return valves (20.20, 20.21), underwater RGB lights with power supply, controller and amplifier (20.22–20.27), submersible flat cable (20.28).

## Category: LIFT

Machine room less lifts with regenerative drive, supply and installation, each: passenger (21.1, 13 or 16 passengers), goods 2000 kg (21.2), hospital bed lift 20 passenger (21.3). The description states the stops, speed and features the rate covers; check them against the requirement.

## Category: HT CABLE LAYING

Laying of 11 kV (22.1–22.4) and 33 kV (22.5–22.8) cables per metre: direct in ground, additional cable in the same trench, in existing pipe, in existing open duct. Cable supply is not included.

## Category: HV CABLE JOINTING & END TERMINATION

3 core XLPE aluminium cables: 11 kV cast resin indoor end (23.1), outdoor end (23.2), straight-through (23.3); 11 kV heat shrinkable indoor end (23.4), outdoor end (23.5), straight-through (23.6); 33 kV heat shrinkable (23.7–23.9). By cable size.

## Category: TRANSFORMER

Distribution transformers, supply and installation, by kVA. Headings combine voltage ratio (11/0.433 kV or 33/0.433 kV), insulation (mineral oil, synthetic organic ester oil, dry type), mounting (indoor/outdoor) and efficiency (BEE 3, 4, 5 star; or energy efficiency Level 3, 4, 5 for dry type and higher ratings, with the permissible losses at 50 % and 100 % loading in each child). Choose the heading on all four, then the kVA child. Losses may not exceed the stated values by more than 15 % (book note).

## Category: AUTOMATIC POWER FACTOR CORRECTION (APFC) PANEL

APFC panels by kVAr (25.1) and hybrid APFC panels (25.2). The book: the NIT approving authority selects the rating for an average power factor close to unity; use the hybrid type where the load includes electronic ballasts, VFDs and similar non-linear loads.

## Category: UNINTERRUPTED POWER SUPPLY (UPS)

Online UPS by kVA at unity power factor: single phase in / single phase out (26.1), three phase in / three phase out (26.2). The item includes rectifier, inverter and a battery bank for 30 minutes backup at full load (not less than 1600 VAH per kVA per hour of backup); a different backup time needs another analysis.

## Category: WET RISER & SPRINKLER SYSTEM

Fire fighting: electric main fire pumps (27.1), diesel pumps (27.2), jockey pumps (27.3), terrace pumps (27.4) by flow and head (choose the head that gives at least 3.5 kgf/cm² at the highest/farthest point); control panels (27.5); M.S. 'C' class pipes (27.6, 27.7) and G.I. 'B' class pipes (27.8) per metre including fittings; hydrant valves (27.9, 27.10), butterfly, sluice and non-return valves (27.11, 27.12, 27.14), orifice plates (27.13), strainers (27.15), hoses and hose reels (27.16, 27.17), branch pipes (27.18), fire brigade inlets (27.19), air vessel (27.20), sprinklers (27.21), pressure and flow switches (27.22, 27.23), installation control valves (27.24), flexible sprinkler drops (27.25), deluge valves and water curtain nozzles (27.26, 27.27), rosettes (27.29). Cabling, earthing and cable trays are in their own chapters; digging in the Civil DSR.

## Category: FIRE DETECTION AND ALARM SYSTEM

Conventional system (28.1: detectors, panels, sounders; 28.1.9 sector panels by zones), intelligent addressable system (28.2: main panel by loops 28.2.1, addressable detectors and modules), public address system (28.3), aspiration detector accessories (28.4), cables (28.5: fire survival and fire alarm armoured cables; 28.5.3 FR PVC cables drawn in existing conduit). Choose conventional or addressable first and keep all devices from the same section.

## Category: DIESEL GENERATOR SET

Silent type DG sets to CPCB IV+ norms, supply and installation, by prime power kVA at 415 V, 1500 RPM, 0.8 pf (29.1). Check the description for what is included before adding panels, fuel tank or exhaust separately.

## Category: HVAC(ONLY PLUMBING,DUCTING & AHU)

Chilled water piping per metre (30.1 bare, 30.2 with nitrile rubber insulation, 30.3 with expanded polystyrene insulation); insulation on existing pipe per sq m (30.4–30.6); insulated valves for chilled water (30.7: butterfly 30.7.1, balancing 30.7.2, non-return 30.7.3, Y-strainer 30.7.4); gauges and thermometers (30.8, 30.9); condenser water pipes (30.10) and valves without insulation (30.11); ducting per sq m of duct surface (30.12.1 factory fabricated, 30.12.2 site fabricated); dampers (30.13, 30.14, fire dampers 30.20); grilles and diffusers per sq m (30.15–30.18); flexible duct (30.19); acoustic lining and duct insulation (30.21–30.25); floor mounted AHUs by CMH (30.26, 30.27 to IS 18794). Pipes 150 mm and below are M.S. 'C' class (book note).

## Category: VRV/VRF

Outdoor units per HP by efficiency: 31.1 meets ECSBC, 31.2 ECSBC+, 31.3 Super ECSBC (minimum IEER/COP values in the heading), indoor units each by capacity: 4-way cassette (31.4), compact cassette (31.5), one-way (31.6), two-way (31.7), high wall (31.8), ducted low, mid and high static (31.9–31.12); refnet joints (31.13); copper refrigerant piping per metre (31.14). An outdoor unit's quantity is its HP; add indoor units, joints and piping.

## Category: UNITARY SYSTEM

Window ACs (32.1), high wall splits (32.2), ductable splits (32.3), cassette splits (32.4), tower splits (32.5), air cooled package units (32.6), by TR and star rating / inverter type.

## Category: CHILLERS

Chillers per TR: air cooled screw (33.1, with VFD 33.2), air cooled scroll (33.3, with VFD 33.4), water cooled screw (33.5, 33.6), water cooled scroll with VFD (33.7), centrifugal (33.8), magnetic bearing centrifugal (33.9, 33.10). Quantity = TR. Water cooled chillers need cooling towers (COOLING TOWERS).

## Category: COOLING TOWERS

Induced draft counterflow cooling towers, CTI approved, by flow (GPM) (34.1).

## Category: AHU & FCU

Ceiling suspended AHUs by CFM (35.1), ductable fan coil units (35.2), cassette FCUs (35.3), high wall FCUs (35.4). Floor mounted AHUs are in HVAC(ONLY PLUMBING,DUCTING & AHU).

## Category: EVAPORATIVE COOLING

Central evaporative cooling plants by air flow (36.1).

## Category: AIR COOLED HEAT PUMP FOR HOT WATER

Heat pumps for hot water by capacity (37.1).

## Category: IPABX/EPABX SYSTEM

IP-PBX systems (38.1, 38.2), IP phones (38.3), analog phones (38.4), 20 pair telephone cable per metre (38.5). Chapter 38 is printed 36.1–36.5 in the book; the database keeps 38.x.

## Category: LAN

Network switches (39.1–39.5 by ports and layer; 39.2 outdoor PoE), SFP modules (39.6), wireless access points (39.7–39.9), patch panels, patch cords, information outlets and RJ45 (39.11–39.16), Cat6/Cat6A cable per metre (39.17, 39.18), fibre cables (39.19 single mode, 39.20 multi mode), LIUs and fibre patch cords (39.21, 39.22), racks (39.23–39.26). 39.10 is deleted by the correction slip.

## Category: CCTV CAMERA

IP IR cameras by resolution and type: 2 MP dome/bullet (40.1, 40.2), 4 MP (40.3, 40.4), 5/6 MP (40.5, 40.6), 8 MP (40.7, 40.8), PTZ (40.9); each has a fixed-lens and a motorised vari-focal child. NVRs by channels (40.10, 40.11), surveillance hard disks by TB (40.12). The full camera and NVR specifications are in the item descriptions.

## Category: ACCESS CONTROL SYSTEM

Access control systems (41.1 face recognition, 41.2 without finger print, 41.3, 41.4 compact readers), web software (41.5), electromagnetic locks (41.6), exit push button (41.7), door position sensor (41.8). A door needs a controller/reader system, lock, exit button and door sensor.

## Category: BUILDING MANAGEMENT SYSTEM (BMS)

Central server (42.1), client PC (42.2), printer (42.3), displays (42.4), BMS software by points (42.5), operator terminals (42.6), DDC controllers (42.7), I/O expansion modules (42.8), DDC enclosures (42.9), third-party integration units (42.10), field devices (42.11: switches, sensors, meters). The printed schedule rates of 42.11.1–42.11.12 are out of step with the printed analyses; the analysis rates are used.
