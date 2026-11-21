# Other Electrical Installation Works (rev 21/11/2026): database notes

Read this before choosing items from this database. The general part says what the database is, when to use it instead of DSR (E&M) 2025 and how its items are built. Each `## Category:` section describes one head: what it covers, how its items are arranged, how to pick the right one and which DSR item to combine it with. Read the section of every category you take items from.

## About

- **Purpose:** market-rate items for electrical, ELV, HVAC, fire fighting, audio visual and medical gas works that **DSR (E&M) 2025 does not have**. Always look in DSR (E&M) 2025 first; take an item from here only when DSR has no item of that scope and specification. Items with an equivalent in DSR (E&M) 2025 were removed from this database.
- **Sources:** Other Electrical Installations rev 10/04/2019, its 01/2025 revisions (general, ELV, HVAC, medical gas) and market-rate items of project estimates prepared between 11/2021 and 11/2026 (residential quarters, campus buildings, networking, CCTV, audio visual, studio). Each item's remarks give the original remark ("MR" = market rate; "DSREM16 x.y" = taken from DSR (E&M) 2016) followed by the source file and its date, e.g. "MR (OE-GEN, 01/2025)".
- **Rates:** each item's rate is its rate analysis, built in the DSR (E&M) 2025 order: materials (market quotations, GST-exclusive; quotations that included GST are reduced through a negative VAT on the resource), cartage 1 %, labour or an installation, testing and commissioning percentage for equipment (6 % or 10 %, specific to the equipment), overheads and profit 15 %, labour cess 1 %, GST 18 % last. Civil items at complete schedule rates (excavation, concrete) are added after GST. The two lift items are quoted lump sums inclusive of taxes. Rates are **not escalated**: an item dated 2019 or 2021 carries that year's prices. Check the date in the remarks and update the resource rates of older items before using them in an estimate.
- **Specifications:** works follow the CPWD General Specifications for Electrical Works and for HVAC Works, the BIS and IEC standards named in each item, and the detailed technical specifications of the tender where an item says so ("as per detailed requirements listed out in the tender document").
- **Guardrail:** do not add GST, overheads or profit on top of item rates; they are in the analyses. Do not use a resource rate directly as a BOQ item.
- **Preferred over DSR (E&M) 2025:** for lightning protection, use the aluminium air terminal and aluminium round conductor system of LIGHTNING CONDUCTOR (6.1–6.8, IS/IEC 62305) instead of the DSR G.I. finials and G.I. tapes (DSR 6.2–6.15). For earthing, use the copper coated (copper bonded) steel rod electrode (5.2) and copper coated steel round conductor (5.1) instead of the DSR G.I. pipe/plate electrodes and G.I. strip/wire earth leads (DSR 5.1–5.13), unless the specification asks for those.

## How the items are built

- **Codes** are head.item[.subitem], e.g. 8.3.12. A head is a category. Heads 1 to 26 follow the DSR (E&M) 2025 chapter heads in DSR order; heads 27 to 34 have no DSR counterpart. Gaps in the numbering are items deleted after review (8.9, 24.51, 24.54, 32.2, 32.91: available in DSR or superseded).
- **Headings and items.** A row with rate 0 and subitems is a heading: its description is the common specification, and each subitem adds only the size, rating or variant ("3 X 16 sq. mm", "1200 mm sweep", "24U (800 mm deep)"). Always use a priced subitem, never the heading; the full meaning is heading text + subitem text. Where several sources had the same heading, their subitems are under one heading, so a heading can list a size more than once with different specifications in the subitem text (for example two 20 pair KRONE boxes); read the subitem text and the remarks date and prefer the newer one.
- **Bracketed titles.** Many ELV, AV and panel items start with a title in capitals in brackets, e.g. "(24 RJ45 + 4 SFP LAYER 2+ SWITCH WITH 10 Gbps UPLINK)" or "(4 SERVICE, 3PH METERING PANEL)"; search on these words.
- **Supply only vs supply and installation.** "Supplying and testing" cable items are the cable only: add the DSR (E&M) 2025 laying item. "Supply of ... pole" is the pole only: add the erection item. "Supply, installation, testing and commissioning" (SITC) and "Supplying and fixing" items include fixing. Items "in the existing ..." (DB, rack, panel, conduit, patch panel, pipeline) assume that part exists.
- **Job items** (unit Job) are complete systems or panels built for one project (metering panels, fire fighting panels, IP-PABX server, Wi-Fi controller, video management, storage server, boom barrier). Their description lists the configuration; use them only for an equivalent configuration, otherwise as a reference for pricing a new item.
- **Units:** No/Each/Nos, Metre/Meter/m, Set, Pair, Sqm/Sq.Mtr, kg, Job, Month (lift maintenance).
- **Resources** have codes R0001 onward (prefix OE26 when imported into a project). One sub-analysis (SA.1, excavation of cable trenches in soft soil) is used by an analysis and is not an estimate item.

## Category: WIRING

Wiring accessories not in DSR chapter 1 (CPWD General Specifications Part I). Point, circuit and socket wiring, conduits, standard modular switches/sockets, plates and GI boxes are in DSR WIRING: use them first.

- **Modular devices on existing plates** (1.3): RJ45 Cat 6 socket, USB charger sockets (single/double), 15/16 A and 25 A switches with indicator, 32 A DP switch, 3 pin 25 A socket, bell indicator with reset, buzzer, key fob switch, cable outlet, skirting LED light, bulkhead LED indicator. The modular plate and box are separate (1.6 plates on cable management system; DSR 1.27/1.28 on metal boxes; 1.11 IP55 boxes with membrane for wet areas).
- **Circuit wiring 4 X 1.5 sq. mm + 2 X 1.5 sq. mm earth in steel conduit** (1.4), a size DSR 1.7 does not have.
- **Cable management and trunking:** uPVC cable management system 105 × 50 mm (1.5) with partition (1.8) and plates (1.6); uPVC trunking 32 × 12 to 100 × 50 mm (1.9); GI trunking raceway 300 mm with height-adjustable junction box (1.13, 1.14) for floor/desk distribution.
- **Flexible conduits:** steel wire reinforced flexible PVC conduit 20–32 mm (1.2, 1.7), for the final run to motors, equipment and fittings; brass glands for corrugated galvanised steel conduit 20–32 mm (1.15).
- **Junction boxes:** IP66 glass reinforced SMC boxes in three sizes (1.1 with terminals, by terminal capacity; 1.10 without terminals), for outdoor and wet locations.
- **Video door phone** (1.12): 7" indoor monitor with outdoor camera panel, per set.

## Category: MCCB, MCB & DB'S

Switchgear not covered by DSR chapter 2. DSR has the standard horizontal and vertical TPN DBs (4/6/8 and 4/8/12 way), MCBs 5–32 A, RCCBs 30 mA and TP MCCBs 100–800 A: use them first.

- **MCCBs in existing DBs, FP, 16 kA** (2.3): 40–160 A, and 100–160 A with integrated earth leakage (30 mA–3 A) trip. DSR 2.2 has FP MCCBs only at 30–50 kA from 100 A.
- **MCBs above 32 A** (2.2): 40 A and 63 A TP, "C" curve.
- **RCCBs Type S (selective)** (2.10): 63 A and 80 A four pole, for upstream discrimination.
- **Distribution boards not in DSR:** per phase isolation (PPI) TPN DBs 6/8/12 way (2.5, 2.14); 12 way 7-segment horizontal/vertical TPN DB (2.6); vertical TPN DB with MCCB incomer 6 way (2.7); MCCB DBs 8 way 160/250 A and 12 way 160 A as complete jobs (2.15–2.17). A DB item is the empty board: add MCBs, MCCBs and RCCBs separately.
- **Surge protection devices** in existing DBs (2.1): SP+N Type II, TP+N Type II and TP+N Type I+II. Use Type I+II at the main board of a building with lightning protection, Type II at sub-DBs.
- **DB mountable auxiliaries** (2.8): 25 A power contactor, astronomical and daily time switches, 32 A two-way changeover switch, for lighting control from the DB.
- **Others:** DP enclosure with 6 A SP MCB (2.4); 63 A TPN industrial socket with MCB (2.9); disconnector fuse units 32/63 A (2.11) and changeover switch 63 A (2.12) in enclosures; 4 strip 200 A copper busbar chamber (2.13).

## Category: RISING MAINS & BUS TRUNKING

25 A **lighting busbar** systems (not in DSR, whose rising mains and bus trunking start at higher ratings): busbar per metre with 2 or 4 conductors + earth (3.1, 3.4), end feed unit (3.2) and tap-off boxes, single phase or phase selectable (3.3). Use for long runs of light fittings in halls, workshops and car parks; add one end feed unit per run and one tap-off per fitting or group.

## Category: CABLE TRAYS

Covers for perforated hot dipped galvanised cable trays (4.1 by number of standard lengths; 4.3 per sq. m of plan area) and hot dipped galvanised **wire mesh** cable trays 150/400/600 mm wide (4.2), used for data and ELV cabling. Perforated trays are in DSR CABLE TRAYS (4.1–4.10).

## Category: EARTHING

**Prefer these for earth connections.** Copper coated (copper bonded) steel rod electrode 3 m × 20 mm with augering and backfill compound (5.2, per set) and copper coated steel round conductor 10 mm laid in ground from the electrode (5.1): maintenance-free, corrosion resistant earthing to IS 3043 / IEC 62561, used in place of the DSR G.I. pipe and plate electrodes with charcoal/coke and salt treatment (DSR 5.1–5.4) and G.I. strip or wire earth leads in ground (DSR 5.9, 5.11, 5.12). Use DSR copper plate electrodes (5.5, 5.6) or copper strip (5.8, 5.10) only where the specification asks for them. Other items here: 32 × 6 mm G.I. strip in G.I. pipe from the electrode (5.3) and on surface (5.4) where DSR has only 25 × 5 mm; 25 × 5 mm copper strip in heavy PVC conduit from the electrode (5.5).

## Category: LIGHTNING CONDUCTOR

**Prefer these for lightning protection.** Lightning protection to IS/IEC 62305 with **aluminium** air terminals and 8 mm aluminium round conductors on stainless steel/polyamide holders; use it in place of the DSR G.I. finials and G.I. tapes (DSR 6.2–6.15), which follow the older practice. A complete system takes the air terminals, conductors along the roof and down conductors, connectors at joints, expansion pieces on long runs, a testing joint per down conductor, and an earth electrode per down conductor (copper coated rod, EARTHING 5.2, with 5.1 to interconnect). Items: 1 m vertical air terminal (6.1), conductor jointing with stainless steel connectors (6.2), 8 mm aluminium round conductor on parapet or wall (6.3 horizontal, 6.4 vertical) and on metallic surfaces (6.7, 6.8), expansion piece (6.5), testing joint between down conductor and earth conductor (6.6). Earth electrodes are in EARTHING (DSR, or 5.1–5.5 here).

## Category: LED LIGHT

LED fittings DSR does not have. DSR LED LIGHT has recessed downlighters, 2×2 panels, battens, street and flood lights by wattage and efficacy: use them first.

- **Indoor IP20 fittings by lumen output** (7.1): industrial battens 2000/4000 lm (one with PIR sensor), surface downlights 1100/1600 lm, 600 × 600 surface fitting, trunking fitting, decorative suspended/surface 1200 mm fittings, mirror battens.
- **IP65 fittings** (7.3): bulkhead, wellglass 2700/3500 lm, bulkhead batten, highbay 10000/14500 lm for high bay areas.
- **Decorative and special:** wall brackets and indirect wall lights (7.2, 7.4, 7.5), mirror lights 350/570 mm (7.7, 7.9), study lamp (7.8), aluminium channel suspension rail for fittings (7.6), post top lanterns 30/45 W for gates (7.10, 7.11).
- Prices include the fitting and fixing. Wiring is from DSR WIRING; installation only of client-supplied fittings is DSR 1.35, 1.41, 1.42.

## Category: MV CABLE LAYING

**Supply** of LV cables (1.1 kV) and laying of small cables; DSR has cable laying (labour and accessories) but not cable supply.

- **Supply and testing only** (add the DSR laying item 10.x for the route: direct in ground, in pipe, on tray or clamped): XLPE armoured aluminium power cable 2 to 3½ core, 10–400 sq. mm (8.3); XLPE armoured copper 3 and 4 core, 4–25 sq. mm (8.7); PVC armoured copper control cable 3–12 core, 1.5–4 sq. mm (8.4). Pick by conductor (aluminium for feeders, copper for small power and control), cores and size.
- **Supply and laying:** PVC flexible copper cables 2–5 core, 1–4 sq. mm in conduit or on tray (8.2); screened instrumentation cables 1 and 2 pair (8.5, 8.6, 8.10). Flat submersible cable is in WATER SUPPLY PUMPS, armoured Cat 6 cable in LAN, and fire survival cable for fire alarm and emergency circuits is DSR 28.5.1.
- **Pipes for cables:** HDPE pipes 32/40 mm PE80 SDR11 (8.1) and 63 mm PE100 (8.8). DWC pipes are in DSR.

## Category: MV CABLE JOINTING & END TERMINATION

Terminations not in DSR chapter 11 (which has brass glands with **aluminium** lugs and cast resin outdoor terminations): brass compression glands with **copper** lugs for copper cables, by cable size and gland size (9.1, 9.3, 9.5 double compression); outdoor heat shrink terminations by size range for XLPE cables (9.4); IP66 nylon glands for unarmoured and flexible cables (9.2, 9.6). One termination per cable end. Glands for armoured Cat 6 and optical fibre cables are in LAN.

## Category: POLE ERECTION

Street light and camera poles not in DSR: factory made octagonal GI poles 6 m (10.1) and 9 m (10.10), supply only, with erection on RCC foundation (10.2 for 6 m, 10.11 for 9 m); fabricated GI pipe poles 3 m and 6 m (10.3, 10.4, supply) with erection on CC foundation (10.5, 10.6); ornamental 3 m pole (10.9); GI pipe in the foundation for cable entry (10.7) and SMC junction box on the pole (10.8). A pole needs a supply item and an erection item; add the fitting (DSR LED LIGHT 8.12) or camera and the bracket if any. Use the 9 m poles for outdoor CCTV cameras and high mast-like street lighting.

## Category: HV OVER HEAD LINE WORK

**22 kV** overhead line and substation yard items (DSR chapter 14 has 11 kV and 33 kV): ISMB 200 DP/FP structure (11.1) with angle/channel framework per kg (11.2), jumpers (11.3), ACSR Raccoon and Dog conductors per metre (11.4, 11.5), earthing strip for lightning arrestors (11.6), stay set (11.7), air break switches (11.8, 11.9), horn gap and drop out fuse sets (11.10, 11.11), pin and disc insulators (11.12, 11.13), lightning arrestors (11.14). Fencing and yard surfacing are in MISC.CIVIL ITEMS.

## Category: MISC.CIVIL ITEMS

Substation and transformer yard civil works: chain link fencing 2.1 m high per metre (12.1) with double and single leaf gates (12.2, 12.3), quarry dust 100 mm (12.4) and 40 mm stone aggregate 150 mm (12.5) spread over the yard per sq. m. DSR MISC.CIVIL ITEMS has the cable trench, masonry and foundation items.

## Category: LIFT

MRL gearless lifts as complete units, 8 floors, by capacity and speed: 16 passenger (1020 kg) passenger lift at 1.5 m/s (13.1), 15 passenger bed/goods lift at 1.0 m/s (13.2). Annual comprehensive maintenance per month for years 1–5 (13.3 passenger, 13.4 bed/passenger): take each year's subitem × 12 months. DSR LIFT is priced by stops and capacity: compare both and use the one matching the specification.

## Category: HT CABLE LAYING

**Supply and testing** of XLPE screened armoured aluminium HT cables 3 core: 11 kV 120/240 sq. mm (14.1) and 22 kV 120/185/240 sq. mm (14.2). DSR HT CABLE LAYING has laying only: add DSR 22.x for the laying.

## Category: HV CABLE JOINTING & END TERMINATION

Heat shrink terminations and joints for **22 kV** XLPE cables 120/240 sq. mm: indoor (15.1) and outdoor (15.2) end terminations, straight through joints (15.3). 11 kV and 33 kV terminations and joints are in DSR chapter 23.

## Category: UNINTERRUPTED POWER SUPPLY (UPS)

Small online UPS for single loads (DSR UPS starts at larger ratings): 5 kVA single phase with 30 min backup (16.1), 1 kVA and 2 kVA with 30 min backup (16.2, 16.3).

## Category: WET RISER & SPRINKLER SYSTEM

Items DSR chapter 27 does not have: fire fighting electrical panel for terrace pumps (17.1) and its remote operation panel (17.2), wall mounted switch board (17.5) and remote push button station for booster pump (17.6), hydrant boxes (17.4, 17.7), double headed hydrant valve (17.8), monoblock booster pumpset 450 lpm at 30 m (17.3). Pipes, valves, sprinklers, hose reels and main pumps are in DSR.

## Category: FIRE DETECTION AND ALARM SYSTEM

Only an add-on loop card for an existing addressable fire alarm panel (18.1). All detectors, call points, sounders and panels are in DSR chapter 28.

## Category: DIESEL GENERATOR SET

DG exhaust piping of black MS C class pipe with insulation, 65–200 mm (19.2, per metre) and MS supporting structure per kg (19.1). The DG set itself is DSR 29.1.

## Category: HVAC(ONLY PLUMBING,DUCTING & AHU)

HVAC items not in DSR chapter 30: SS304 ducting per sq. m by sheet thickness (20.3; DSR has GSS ducting), fresh air/exhaust cowls (20.1), rubber expansion joint (20.2), motorised 3 way mixing/diverting valves 50–80 mm (20.4), closed expansion tank 500 l (20.5), BMS field sensors for temperature, humidity, air velocity and differential pressure (20.6), VAV boxes 600–3900 CMH (20.7), inline axial fans (20.8). Chilled water piping, GSS ducting, grilles, insulation and AHUs are in DSR.

## Category: UNITARY SYSTEM

Accessories and units DSR chapter 32 does not have: extra length of refrigerant piping per metre beyond the standard length of a split AC (21.1), outdoor unit wall bracket (21.2), air curtains 600–2000 mm (21.3), scroll condensing unit 8.5 TR for DX AHUs (21.4). Split, cassette, ductable and package units are in DSR.

## Category: AHU & FCU

Chilled water fan coil units: ceiling cassette 1.5/2 TR (22.1) and hi-wall 1 TR (22.2). DSR AHU & FCU has the ducted FCUs and AHUs.

## Category: IPABX/EPABX SYSTEM

Telephone and voice items not in DSR chapter 38: KRONE termination boxes 10–100 pair (23.1), telephone cables 10/50/100 pair in conduit (23.4; DSR has 1, 2, 4 and 20 pair), SIP VoIP phones basic/intermediate/video/cordless (23.3) and executive (23.5), analogue EPABX systems (23.6 small, 23.7 expandable), VM based IP-PABX server for 2000 phones (23.2, Job). DSR has the IP-PBX systems and Type 1 IP phone.

## Category: LAN

Network items beyond DSR chapter 39 (which has 8/24 port L2 and 24 port L3 switches, SFPs 1G–100G, indoor/outdoor access points, Cat 6/6A cabling, patch cords, LIUs and racks).

- **Switches and modules** (24.1–24.16): enterprise core, distribution, data centre and 2.5G PoE access switches (24.1, by model); managed L2+ switches 24/48 port with 1/10 Gbps uplink and PoE budget (24.8–24.10, 24.12); smart managed L2 switches 8/24 port (24.13, 24.16) for AV and small networks; DIN rail unmanaged industrial switches 4/8 port (24.14, 24.15) for outdoor CCTV panels; SFP28, QSFP+ 40G/100G, 10GBASE-T and GPON SFP modules (24.2–24.4, 24.6, 24.7, 24.11); GPON OLT (24.5).
- **Wireless** (24.17–24.19): Wi-Fi 6 access points indoor/outdoor/low density, software managed access point, on-premise Wi-Fi controller (Job).
- **GPON/FTTH** (24.20–24.26): ONT, PLC splitters 1×4, 1×16, 2×16, fibre termination box, ONT enclosure, indoor drop cable.
- **Storage** (24.27): 900 TB on-premise storage server (Job).
- **Copper passive** (24.28–24.36): Cat 6 patch panels 24 port unloaded with 6 port modules, 48 port loaded, Cat 6A STP patch panel and modules (24.33, 24.34), blanking modules, armoured Cat 6 cable in conduit or pipe (24.31) and outdoor armoured Cat 6 cable with UV stabilised jacket (24.35) with its double compression gland (24.36).
- **Fibre passive** (24.37–24.58, 24.64): OS2 indoor/outdoor and OM4 armoured cables by fibre count, loaded and modular fibre patch panels, LC/SC modules (OM4 LC module 24.53), pigtails, single-mode LC/SC and MPO patch cords, OM4 LC connectors (24.55), IP66 gland for fibre cable (24.58). Multimode LC/LC patch cords are DSR 39.22.
- **Racks and containment** (24.59–24.63): cable manager; 19" free standing racks 24/36/42U and wall racks 12–17U by size and depth (DSR has 6/9/15U wall and 24/42U floor racks). Wire mesh trays are in CABLE TRAYS.

## Category: CCTV CAMERA

CCTV items beyond DSR chapter 40 (which has dome, bullet and PTZ cameras, NVRs and hard disks): video analytics for 100 cameras (25.1) and video management system (25.2) as Jobs, outdoor CCTV panel (25.3), CCTV/VMS workstation (25.4), 55" professional display for the control room (25.5). Network switches for CCTV are in LAN (industrial switches 24.14, 24.15) and camera poles in POLE ERECTION (10.10, 10.11).

## Category: ACCESS CONTROL SYSTEM

Card based access control (DSR chapter 41 has face/fingerprint reader systems, software, locks, exit buttons and door sensors): 8 reader 4 door controller (26.1), RFID card reader with PIN (26.2), RFID cards (26.3), emergency break glass unit (26.4), boom barrier entrance system (26.5, Job).

## Category: FANS

**Supply and installation** of fans (DSR BLDC FAN has BLDC ceiling fans; DSR WIRING has installation only): non-metallic exhaust fans 150–250 mm (27.1), heavy duty metallic exhaust fans 230–450 mm (27.3), AC ceiling fans 1200 mm BEE 5 star and 1400 mm (27.2), cabin fan (27.4) and wall fan (27.5) 400 mm. Use DSR 9.1/9.2 for BLDC ceiling fans. Regulators and point wiring are separate (DSR WIRING).

## Category: LT PANELS AND FEEDER PILLARS

Project-built panels as Jobs, each description listing the incomer, outgoings and metering: service metering panels for 1, 4 and 3 + 3 services (28.1–28.3), street light control feeder pillar (28.5), SPD enclosure panel (28.6), and a 125 A 4 pole automatic transfer switch (28.4). Use only for a matching configuration; otherwise price a panel from its components.

## Category: FIRE EXTINGUISHERS AND SAFETY EQUIPMENT

Portable fire extinguishers to IS 15683 (not in DSR): ABC powder 2–9 kg (29.1), CO2 2 and 4.5 kg (29.2), automatic discharge ABC 5/10 kg (29.3), AFFF foam 9 l (29.7), water 9 l (29.8, 29.17), fire buckets (29.9). Substation safety: insulating rubber mats Type A/B/C for 3.3/11/33 kV per sq. m (29.4, 29.12, 29.13), insulating gloves and earth discharge rod (29.15), shock treatment chart (29.11), first aid box (29.10), key cabinet and key board (29.5, 29.14). LED exit signage single/double sided (29.6, 29.16). Choose extinguisher type by fire class: ABC for general and electrical, CO2 for electrical panels and server rooms, foam for oil.

## Category: WATER SUPPLY PUMPS

Water supply pumping (not in DSR): openwell submersible pump sets (30.1, 30.5), motor control feeder pillar for 4 × 5 HP pumps (30.4, Job), motor starters in enclosures, single phase DOL, three phase DOL and star-delta by rating (30.8), water level controller probe (30.6), GI pipeline headers 100–150 mm (30.7), flat submersible cable 3 core 4–16 sq. mm from starter to pump (30.2) with single core earth wire (30.3), water flow meter (30.9).

## Category: PUBLIC ADDRESS SYSTEM

General public address equipment (DSR 28.3 has the voice evacuation controller and ceiling speakers for fire alarm): cabinet loudspeaker (31.1), power amplifiers 120/240/480 W (31.2, 31.10, 31.11), 6 channel mixer (31.3), wireless handheld and lavalier, gooseneck and wired microphones (31.4, 31.6–31.8), speaker cable 1.5 sq. mm and shielded microphone cable 2.5 sq. mm per metre (31.5, 31.9). Size amplifiers for the total speaker wattage plus margin.

## Category: AUDIO VISUAL SYSTEM

Classroom, auditorium, conference room and studio AV equipment (not in DSR). Items are grouped:

- **Projection** (32.1–32.18): laser projectors by brightness 4000–15000 ANSI lumen (LCD/DLP and 3LCD), ultra short throw projector, manual, motorised, fixed frame auditorium and green screens; HDMI cable 15 m from face plate to projector (32.1). Choose brightness by screen size and room light.
- **Displays** (32.19–32.30): large format displays 40"/65", professional signage displays by size, collaboration display, IPS monitors, digitiser monitors for podiums, room control touch display, digital podium; wireless microphones and a mouse also fall in this range (32.21–32.23).
- **Studio** (32.31–32.34): studio monitor speaker and headphone, PTZ cameras and camera control unit.
- **Video switching and processing** (32.35–32.47): presentation switcher/scaler, HDMI matrix 4×4/8×8, automatic switchers, distributors, HDBaseT transmitter, USB extender, HDMI-SDI converter, capture box, live production switcher, recorder and streamer, audio delay box.
- **Conferencing** (32.48–32.61): video conferencing MCUs (2, 8, 10 site), analogue audio conferencing control unit with chairman and delegate units, digital wireless conferencing system with conference units, credenza for VC setup.
- **Audio** (32.62–32.83): loudspeakers (cabinet, ceiling, column, point source), power amplifiers, mixers, DSPs, wired/gooseneck/boundary microphones and stands, antenna distribution.
- **Control and computers** (32.84–32.90): control processor, keypad, presentation controller, USB sharing switch and hub, desktop and podium PCs.
- **Cabling and boards** (32.92–32.98): audio/control cables, HDMI and USB cables by length, HDMI/USB face plates (32.95, 32.96), ceramic green/white boards, coaxial splitters.

Most items include installation and configuration; cables between equipment are separate items. Network switches, racks and patch panels for AV are in LAN.

## Category: STAGE LIGHTING

Studio and stage lighting: dimmable LED fresnel, soft panel and profile lights (33.1) with DMX lighting console (33.2), MS pipe grid and suspenders (33.3, 33.4), power distribution and DMX junction boxes (33.5–33.8, 33.10), DMX splitter (33.12), black finish lighting DB and cable trays for the stage (33.9, 33.11), DMX cable (33.13), XLR connectors (33.14, 33.15). Flexible power cables are in MV CABLE LAYING (8.2).

## Category: MEDICAL GAS

Medical gas pipeline system for hospitals (not in DSR): medical grade copper pipes 10–76 mm per metre (34.1) with brass isolation valves (34.2), zonal valve boxes for 3/4 gases (34.3, 34.4), zonal alarm boxes (34.5, 34.6), gas outlets DISS and DIN (34.7, 34.9), bed head panel per metre (34.8) with vacuum unit, oxygen flow meter and monitor stand (34.10–34.12), medical air compressor, vacuum pump, air dryer, receiver and filters (34.13–34.18), semi-automatic cylinder manifolds 4+4 and 5+5 (34.19). Size pipes for the design flow of each gas; one outlet per gas per bed.
