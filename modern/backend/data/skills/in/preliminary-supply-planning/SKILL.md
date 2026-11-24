---
name: preliminary-supply-planning
description: Estimate utility, transformer, generator, UPS and battery requirements from operating scenarios and allocate equipment and connection works.
---

# Supply capacity and backup power

Use the adopted SP 7 building electrical-services provisions, SP 30:2023, utility conditions and equipment ratings. Record kW, true PF, kVA, phase, starting duty and allowed interruption for each load. Identify normal-only, essential and no-break groups. Show a one-line diagram for utility available, changeover, sustained outage and restoration/recharge. Check whether standby sources may parallel. Determine interlocking, neutral switching, earthing and protection for each permitted mode.

Example with project-supplied simultaneous input loads: normal-only 45 kW at PF .90, essential direct 18 kW at .90 and no-break 9 kW at .90. A double-conversion UPS operates at supplied efficiency .90 and input PF .95. With fully charged batteries the UPS draws 10 kW or 10.53 kVA. Conservative sums of input kVA give 80.53 kVA on utility and 30.53 kVA on generator after shedding normal-only loads. During transfer only the UPS output carries 10 kVA. A supplied 3 kW charger input at .95 adds up to 3.16 kVA on restoration; include it on generator only if enabled. Tag the UPS input in the source schedules and its output in the load schedule.

With an explicit 20% project reserve, the utility screen is (45/.90 + 18/.90 + 10/.95 + 3/.95) × 1.2 = 100.42 kVA if recharge coincides with peak. Compare actual available transformer sizes, sanctioned supply, ambient derating and fault impedance. For generator duty check kW and kVA, largest start/load step, voltage/frequency dip, altitude, ambient, harmonics and recharge controls against supplier data. For 15 minutes at 9 kW and inverter efficiency .90, battery-terminal energy delivered is 2.50 kWh. Use manufacturer constant-power discharge data at the specified cutoff voltage, temperature, autonomy and end-of-life capacity for strings and cabinets.

Return candidate capacities and open operating limits. Price utility charges separately. Allocate transformer, panels, metering, changeover, UPS/bypass, battery cabinets, generator auxiliaries, ventilation/exhaust, fuel, cabling, plinth and testing to actual package owners. Use [LV design](gestimator://skills/in/preliminary-lv-distribution-design) for each downstream feeder.
