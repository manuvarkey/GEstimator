"""Correction Slip No. 1 (CPWD, 27-11-2025) to the DSR (E&M) 2025, as data.

The slip prints each corrected item twice, "existing" and "modified", with long
specifications abridged by dots. Rates, units and codes are taken from the
"modified" columns; description changes are listed as exact text replacements on
the full descriptions of the book, so only what the slip changes is touched.

Used by tools/prepare_dsrem2025.py. The book was issued in parts and some
corrections are already in the workbook; a replacement whose new text is already
present counts as applied, and anything else that does not match is reported.
"""

# Annexure I, modified rates (Each unless the schedule says otherwise).
RATES = {
    "4.4.2": 1458, "4.5.4": 1836,
    "8.9.3": 705,
    "11.2.23": 2117, "11.2.24": 2643, "11.4.29": 2374,
    "12.5": 9096,
    "15.14.4": 1303,
    "19.10.1": 8962,
    "20.5.6": 7397,
    "27.12.2": 7691, "27.12.3": 9869, "27.12.4": 11386, "27.12.5": 15603, "27.12.6": 24088,
    "27.13": 1424,
    "27.17.2": 11086,
    "27.18.1": 2544, "27.18.2": 1756,
    "28.1.10": 75339,
    "28.5.3.3": 133, "28.5.3.4": 169,
    "30.2.13": 1266, "30.2.14": 1069,
    "30.27.11": 301047, "30.27.12": 316621,
    "39.14": 151,
    "39.18.1": 62, "39.18.2": 99, "39.18.3": 137, "39.18.4": 174,
}

# Items deleted by the slip.
DELETED = {"39.10"}

CERTIFICATIONS = ("Certifications: FCC, CE marked, UL/EN, RoHS and relevant MTCTE(TEC)/BIS "
                  "compliance/certification as applicable")
DOT_TRUSTED = "Certifications: UL, CE, FCC, RoHS, MTCTE, OEM/Product must be on Trusted Telecom Portal of Department of Telecommunication, Government of India etc. complete as required."

# (item code, old text, new text); text sits anywhere in the item's description lines.
TEXT = [
    ("4.4", "fastner", "fastener"),
    ("4.5", "fastner", "fastener"),
    ("8.3", "(System lumen efficacy >135lm/Watt)", "(System lumen efficacy ≥135lm/Watt)"),
    ("8.3", "System lumen efficacy >135 lm/Watt output", "System lumen efficacy ≥135 lm/Watt output"),
    ("8.8", "(System lumen efficacy >135 lm/Watt)", "(System lumen efficacy ≥135 lm/Watt)"),
    ("8.8", "System lumen efficacy >135 lm/Watt output", "System lumen efficacy ≥135 lm/Watt output"),
    ("8.8", "CRI >80", "CRI ≥80"),
    ("8.9", "junction temperature shall not rise above 90°C).",
     "junction temperature shall not rise above 90°C). Powder coated die cast /Extruded aluminium Body (Thickness ≥1.20 mm)"),
    ("8.18", "Operating temp range -15 °C to 50 °C", "Operating temp range -5 °C to 50 °C"),
    ("26.1", "Static Bypass switch along with provision for manual bypass", "Static Bypass switch along with manual bypass"),
    ("26.2", "Static Bypass switch along with provision for manual bypass", "Static Bypass switch along with manual bypass"),
    ("30.2", "minimum 45 Kg / cu m density, thermal conductivity 0.037 W/MK or better at 20 deg mean temperature",
     "minimum 55 Kg / cu m density, thermal conductivity 0.034 W/m.K or better at 10°C mean temperature"),
    ("32.5", "suitable for working between 380V-415V 50 hz ,3 phase AC supply with low & high voltage cutoff",
     "suitable for working between 415 ± 10% Volt with low & high voltage cutoff and 50 Hz, 3 phase AC supply"),
    ("39.1", "Jumbo frame: 10KB or higher", "Jumbo frame: 9KB or higher"),
    ("39.1", DOT_TRUSTED, CERTIFICATIONS + ", etc. complete as required."),
    ("39.2", "additional 4 X 1G SFP Ports", "additional 2 X 1G SFP/RJ45 Combo Ports"),
    ("39.2", "17Mpps", "14Mpps"),
    ("39.2", "-5° to 70° C operating temperature. Certificate: UL, CE, FCC, NEMA-TS2, IEC/MIL-STD for Shock , Vibration & Drop Certificate. "
     "OEM Should have Certificate for Industrial Cyber Security Capability IEC-62443-4-1:2018, ISO 45001, ISO 27001 and ISO 14001 "
     "Certified or Equivelent Indian Certificate. OEM/Product must be on Trusted Telecom Portal of Department of Telecommunication, "
     "Government of India etc. complete as required.",
     "-5° to 70° C operating temperature 6 KV Lighting protection. " + CERTIFICATIONS + ", NEMA-TS2, IEC/MIL-STD for Shock, "
     "Vibration & Drop Certificate, Industrial Cyber Security Capability IEC-62443-4-1:2018/CERT-IN, ISO 45001, ISO 27001, "
     "and ISO 14001 Certified or Equivalent Indian Certificate, etc. complete as required."),
    ("39.3", "Switching capacity of min. 168Gbps", "Switching capacity of min. 128Gbps"),
    ("39.3", "125Mpps", "95Mpps"),
    ("39.3", "Stacking support of min. 8 units per stack", "Stacking support of min. 4 units per stack"),
    ("39.3", DOT_TRUSTED, CERTIFICATIONS + ", etc. complete as required."),
    ("39.4", "Internal AC Power supply with operating temperature", "Dual AC Power supply with operating temperature"),
    ("39.4", "48K Mac address", "32K Mac address"),
    ("39.4", "IPv6 Neighbor Discovery (ND), BGP, ISIS, MPLS, VRRP v2, OSPFv2/v3", "IPv6 Neighbour Discovery (ND), BGP/ISIS/ MPLS/VRRP v2/OSPFv2/v3"),
    ("39.4", DOT_TRUSTED, CERTIFICATIONS + ", etc. complete as required."),
    ("39.5", "6x 100GbE QSFP28", "4x 100GbE QSFP28"),
    ("39.5", "2.16 Tbps", "1.76 Tbps"),
    ("39.5", "Certifications: CE, FCC, MTCTE, OEM/Product must be on Trusted Telecom Portal of Department of Telecommunication, Government of India etc. complete as required.",
     CERTIFICATIONS + " etc. complete as required."),
    ("39.7", "1 x RJ45 console port, 1G LAN POE Port, factory reset", "1G LAN POE Port with console management function factory reset"),
    ("39.7", "Works as Access Point, WDS, WDS with AP, Wireless Client, Web", "Works as Access Point, WDS with AP/ Wireless Client/MESH Web"),
    ("39.7", "Certifications: MTCTE, CE, FCC. Should also work", CERTIFICATIONS + ", Should also work"),
    ("39.7", "Captive Portal Authentication.OEM/Product must be on Trusted Telecom Portal of Department of Telecommunication, Government of India etc. complete as required.",
     "Captive Portal Authentication ,etc. complete as required."),
    ("39.8", "WIFI 6 Certified, 1 x RJ45 console port, MG 2.5G LAN POE Port, factory reset",
     "WIFI 6 Certified/ Wi-Fi Alliance, MG 2.5G LAN POE Port, having console management function, factory reset"),
    ("39.8", "Works as Access Point, WDS, WDS with AP, Wireless Client ., Web", "Works as Access Point, WDS with AP/ Wireless Client/MESH, Web"),
    ("39.8", "Certifications: MTCTE, CE, FCC.", CERTIFICATIONS + "."),
    ("39.8", "Captive Portal Authentication.OEM/Product must be on Trusted Telecom Portal of Department of Telecommunication, Government of India etc. complete as required.",
     "Captive Portal Authentication, etc. complete as required."),
    ("39.9", "WIFI 6 Certified, 1 x RJ45 console port, MG 2.5G LAN POE Port, factory reset",
     "WIFI 6 Certified/Wi-Fi Alliance, MG 1G LAN POE Port, having console management function. factory reset"),
    ("39.9", "Works as Access Point, WDS, WDS with AP, Wireless Client, Web", "Works as Access Point, WDS with AP/ Wireless Client/MESH/ Web"),
    ("39.9", "IP68 water/dustproof", "IP67 water/dustproof"),
    ("39.9", "Certifications: MTCTE, CE, FCC. Works as Standalone", CERTIFICATIONS + ". Works as Standalone"),
    ("39.9", "Captive Portal Authentication.OEM/Product must be on Trusted Telecom Portal of Department of Telecommunication, Government of India etc. completed as required.",
     "Captive Portal Authentication, etc. complete with required hardware/software controller etc. to make AP functional as required."),
    ("39.14", "color as per", "colour as per"),
    ("39.14", " All copper Cable and Components should be from same OEM to mainitain compatibility and interopertability.", ""),
    ("39.22", "Apex Offset < 50 µm", "Apex Offset ≤50 µm"),
    ("39.22", "Fiber Height + 100 nm", "Fiber Height ± 100 nm"),
    ("39.22", "Repeatability < 0.2 db", "Repeatability ≤ 0.2 dB"),
    ("40.9", "cover distance up to 300 meter or above", "cover distance 150 meter or above"),
    ("40.9.3", "45x Optical zoom and 16x Digital zoom", "32x Optical zoom and 12x Digital zoom"),
    ("40.10", "20TB capacity/ Slot", "16TB capacity/ Slot"),
    ("40.11", "20TB capacity/ Slot and RAID support of RAID 0/1/5/6/10.",
     "16 TB capacity/ Slot and RAID support of RAID 0/1/5/6/10. (4 SATA (32 Channel) & 8 SATA Slot for 64 Channel)"),
    # Cosmetic changes of the slip.
    ("8.3", "frequency 50/60 hz", "frequency 50/60 Hz"),
    ("8.8", "frequency 50/60 hz", "frequency 50/60 Hz"),
    ("8.9", "frequency 50/60 hz", "frequency 50/60 Hz"),
    ("8.18", "frequency 50/60 hz", "frequency 50/60 Hz"),
    ("40.1", "12VDC/24 VDC/PoE", "12V DC /24V DC/PoE"),
    ("40.2", "12VDC/24 VDC/PoE", "12V DC /24V DC/PoE"),
    ("40.8", "12VDC/24VDC/PoE", "12V DC /24V DC/PoE"),
]

# Appendix II (5246-5249 are per metre of Cat6A cable, 1 to 4 runs).
RESOURCE_RATES = {"5246": 26.25, "5247": 52.5, "5248": 78.75, "5249": 105}
# Appendix I: code 1020 Electronic Technician is replaced by 1021 Technician.
RESOURCE_RENAMED = {"1020": ("1021", "Technician")}
