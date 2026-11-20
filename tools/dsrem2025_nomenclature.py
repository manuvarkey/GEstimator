"""Nomenclature of DSR (E&M) 2025 as printed in DSR_EM_2025.pdf, as data.

The workbook the schedule is prepared from differs from the printed book in some
descriptions (a stock phrase put in front of erection items, spelling slips, text
cut at the end of a cell). Edits here bring those to the printed wording; edits
of Correction Slip No. 1 (dsrem2025_correction_slip1.py) are applied afterwards
and prevail. Differences that look like deliberate later changes (for example
voltages of 32.4, "WG" of 36.1) are left as the workbook has them.

Edit format: (item code, old, new); "re:" before old makes it a regular expression.

The printed book is authoritative; the only departures are the slip's own changes.
"""

STOCK = "Supplying, Installation, Testing and Commissioning of "

TEXT = [
    ("1.56", "providng", "providing"),
    ("1.57", "wih", "with"),
    ("1.59", "with with", "with"),
    ("2.21", "enameled", "enamelled"),
    ("2.22", "enameled", "enamelled"),
    ("10.9", STOCK + "making", "Supplying and making"),
    ("10.10", STOCK + "cable route marker", "Supplying and fixing cable route marker"),
    ("13.15", STOCK + "Erection of", "Erection of"),
    ("13.20", STOCK + "Erection of", "Erection of"),
    ("13.21", STOCK + "Erection of", "Erection of"),
    ("13.22", STOCK + "Erection of", "Erection of"),
    ("13.23", STOCK + "Erection of", "Erection of"),
    ("13.16", STOCK + "erection of", "Supplying and erection of"),
    ("13.17", STOCK + "erection of", "Supplying and erection of"),
    ("13.18", STOCK + "erection of", "Supplying and erection of"),
    ("13.19", STOCK + "erection of", "Supplying and erection of"),
    ("20.28", STOCK + "PVC", "Supplying & fixing PVC"),
    ("23.1", STOCK + "making", "Supplying and making"),
    ("23.2", STOCK + "making", "Supplying and making"),
    ("23.3", STOCK + "making", "Supplying and making"),
    ("23.4", STOCK + "making", "Supplying and making"),
    ("23.5", STOCK + "making", "Supplying and making"),
    ("23.7", STOCK + "making", "Supplying and making"),
    ("23.8", STOCK + "making", "Supplying and making"),
    ("23.9", STOCK + "making", "Supplying and making"),
    ("27.22", STOCK + "pressure switch", "Providing & fixing of pressure switch"),
    ("31.13", "Supply, Installation", "Supplying, Installation"),
    ("25.1", "handel", "handle"),
    ("25.1", "arrangment", "arrangement"),
    ("39.3.1", "cooper", "copper"),
    ("39.12", "ANSI/TIA-568.2-D", "ANSI/TIA-568.2-D etc. complete as required."),
    ("39.13", "ANSI/TIA-568.2-D", "ANSI/TIA-568.2-D etc. complete as required."),
    ("39.15", "mainitain compatibility and interopertability.", "maintain compatibility and interoperability etc. complete as required."),
    ("39.16", "transparent color. Use for 24- 26 AWG stranded wires.", "transparent color, Use for 24- 26 AWG stranded wires etc. complete as required."),
    ("30.21", "cadmium plated nuts,", "cadmium plated nuts, bolts, stick pins, CPRX compound in confirmation to SMACNA/IS and as per specifications complete etc. as required."),
    ("42.9.1", "500X500X200 mm", "500mmX500mmX200 mm"),
    ("42.8", "expension", "expansion"),
    ("28.1.10", "terminal blocks etc. complete as required -1 set.",
     "terminal blocks etc. complete as required -1 set. Battery charger trickle cum boost to take complete load of fire alarm & PA system "
     "complete with all accessories including providing & fixing of 2 nos.12 volt, 60 AH each sealed maintenance free batteries -1 set."),
    ("28.1.11", "terminal blocks etc. complete as required -1 set.",
     "terminal blocks etc. complete as required -1 set. Battery charger trickle cum boost to take complete load of fire alarm & PA system "
     "complete with all accessories including providing & fixing of 2 nos. 12 volt, 30 AH each sealed maintenance free batteries -1 set."),
    ("5.5", r"re:\bmetre", "meter"),
]
for _code in ("12.1.1", "12.1.2", "12.1.3", "12.3.1", "12.3.2", "12.3.3", "12.3.4"):
    TEXT.append((_code, r"re:\b([Mm])etre", r"\1eter"))
# Specification (and its slip-corrected items) are spelled wrong in many 40.x lines.
for _code in ("40.7", "40.8", "40.9", "40.10", "40.11"):
    TEXT.append((_code, "spcifications", "specifications"))
for _code in ("42.1", "42.2", "42.3", "42.5", "42.6", "42.7", "42.8", "42.9", "42.10", "42.11"):
    TEXT.append((_code, "Supply Installation", "Supplying Installation"))
for _code in ("20.5.1", "20.5.2", "20.5.3", "20.5.4", "20.5.5", "20.5.7", "20.10.1", "20.10.2", "20.10.3"):
    TEXT.append((_code, "orfice", "orifice"))  # 20.5.6 stays as in the slip

TEXT += [
    ("1.50", "Installation, testing and commissioning following sizes of exhaust fan in the existing opening including making good the damages, connections, etc. as required.",
     "Installation, Testing and Commissioning of exhaust fan in the existing opening, including making good the damage, connection, testing, commissioning etc. as required."),
    ("12.1.4", "upto 13.00 metre", "upto 13.00 Meter"),
    ("20.27", "Supplying, Installation Testing and Commissioning of fixing", "Supplying, Installation, Testing and Commissioning of fixing"),
    ("20.27", "Output Power-12 V DC, complete as per the Direction & Entire Satisfaction of engineer in charge", "Output Power-12 V DC etc. complete as required."),
    ("25.1", "Supplying, Installation, testing and commissioning of Automatic", "Supply, Installation, testing and commissioning of Automatic"),
    ("25.1", "Siemens gray", "Siemens Gray"),
    ("25.1", "supports,bottom", "supports, bottom"),
    ("25.1", "below details (A)", "below details. (A)"),
    ("25.1", "alongwith", "along with"),
    ("32.4", "suitable for 230/415V +10%,", "suitable for 400/230V,"),
    ("33.1", "415V±10% 50 cycles", "415±10% 50 cycles"),
    ("33.2", "415V±10% 50 cycles", "415±10% 50 cycles"),
    ("33.3", "415V±10% 50 cycles", "415±10% 50 cycles"),
    ("36.1", "50 mm WG static", "50 mm WC static"),
    ("36.1", "specifications:- A. Air washer", "specifications A. Air washer"),
    ("36.1", "in all respect. G. All", "in all respect G. All"),
    ("39.19.2", "Single Mode Optical 12 Core fiber cable", "Single Mode 12 Core Optical fiber cable"),
    ("40.4.2", "5MP/6MP IP IR Dome Camera", "5/6MP IP IR Dome Camera"),
    ("40.5", "5MP/6MP IP IR Dome Camera having", "5/6MP IP IR Dome Camera having"),
]
# Lines that belong to the next section in the workbook.
DROP_ROWS = {("39.26", "2 MP IP IR Dome Camera")}

# Items the printed book marks DELETED.
DELETED = {"6.1", "6.10", "6.11"}
# The workbook numbers the transformer 630 kVA of 24.9 as 24.8.6 a second time.
RENUMBER = {
    ("24.8.6", "1568164"): "24.9.6",
    # numbering of the analyses (DAR) is followed where the schedule repeats or skips a number
    ("11.1.35", "489"): "11.1.36", ("11.1.34", "438"): "11.1.35",
    ("23.3", "12946"): "23.4.1", ("23.3.1", "15989"): "23.4.2", ("23.3.2", "17414"): "23.4.3", ("23.3.3", "17414"): "23.4.4",
    ("31.12.3", "78065"): "31.12.2", ("31.12.4", "85191"): "31.12.3",
    ("31.12.1", ""): "",
}

# Appendix II units as printed (the workbook has Nos, m, Mtr ... for what the book calls Each, Meter, sq. m).
RESOURCE_UNITS = {"nos": "Each", "no": "Each", "e": "Each", "each": "Each", "m": "Meter", "mtr": "Meter",
                  "mtrs.": "Meter", "meter": "Meter", "per sq meter": "sq. m", "sqmtr": "sq. m", "sq meter": "sq. m"}
RESOURCE_RATES = {"3099": 205166.44, "3162": 215780.34, "5174": 5138,
                  "2322": 946, "2323": 1326}
# 3099/3162: swapped back, as the slip does for 30.27.11/12. 5174: the book prints 2138 (a copy of 5172); the slip rate of 20.5.6
# (7397) needs 5138. 2322/2323: the DAR and the slip rates of 11.2.23/24 price the 150 and 185 sq mm kits the other way round.
RESOURCE_UNIT_BY_CODE = {"2416": "Set"}
# Resource descriptions: (old, new) on every resource.
RESOURCE_TEXT = [
    ("spcifications", "specifications"),
    ("mainitain compatibility and interopertability", "maintain compatibility and interoperability"),
    ("operning", "opening"),
    ("#REF!", "5MP/6MP IP IR 2.8/ 3.6/6/8/12 mm fixed lens (as per site requirement) outdoor bullet Camera"),
]

# Published schedule rates are whole rupees (the workbook keeps unrounded formula results);
# these keep decimals as printed: civil sub-analysis rates and two lift items.
KEEP_DECIMALS = {"21.1.1": 2, "21.1.2": 2}
KEEP_DECIMALS_PREFIX = ("15.",)

# Analysis codes (DAR) that differ from the schedule: item code in the analysis -> code in the schedule.
ANALYSIS_RENUMBER = {"5.1.4": "26.1.4", "30.10.1": "30.10"}
ANALYSIS_RENUMBER_PREFIX = (("18.19", "8.19"), ("30.10.1.", "30.10."))
# Analysis lines whose code names the wrong resource: (item, code in the analysis) -> (right code, qty or None).
# 19.10.1: keypad is 5164 (5165 is a fountain nozzle). 27.17.2: gate valve 4213 and lump sum 4355 as in 27.17.1
# (4256 is a G.I. pipe, 4255 a 300 mm pipe). 19.9.3: the XLR connector is 5163.
ANALYSIS_LINE_CODES = {("19.10.1", "5165"): ("5164", None), ("27.17.2", "4256"): ("4213", None),
                       ("27.17.2", "4255"): ("4355", 1), ("19.9.3", "5164"): ("5163", None)}
# "Fitter, Grade 1" is 1004; the DAR codes it 1006 (Painter).
ANALYSIS_FITTER = ("1006", "1004")

# The workbook has no title row for chapter 19, so its items fall under chapter 18.
CHAPTER_CATEGORY = {"19": "FACADE LIGHTING"}

# Analyses the workbook labels wrongly or runs together (the DAR has the same defects for 4.2.9 and 4.2.14).
# A header missing between two analyses: after the analysis of the key, the next one is this item.
ANALYSIS_INSERT_HEADERS = {
    "4.2.8": ("4.2.9", "375 mm width X 62.5 mm depth X 2.0 mm thickness"),
    "4.2.13": ("4.2.14", "600 mm width X 75 mm depth X 2.0 mm thickness"),
}
# First header (code, description start) that gets another code: its lines belong to that item.
ANALYSIS_HEADER_CODES = {
    ("19.3", "LED Linear Profile"): "19.3.1",   # the 100 W line sits under the group heading
    ("20.20", "Supplying, Installation"): "20.20.1",  # the 80 mm dia line likewise
    ("5190", "Supplying, Installation"): "20.15",  # analysis of 20.15 carries the resource code
}
# Children numbered 31.2.n under the heading 31.1 are 31.1.n.
ANALYSIS_CHILD_PREFIX = {"31.1": ("31.2.", "31.1.")}
# A header that repeats the code of the next one right after another header is a mislabel of the item before.
ANALYSIS_BLANK_AFTER = {("42.11.6", "42.11.7")}

# Labour lines of chapter 39 without a resource code, at the Appendix I rate: description -> (code, name, rate).
ANALYSIS_LABOUR = {"wiremen": (1001, "Wireman", 981), "khallasi": (1007, "Khallasi", 805)}

# Analyses whose priced line has no code, the resource code standing on the description line above it.
ANALYSIS_CODE_ROW_ITEMS = {"27.5.1", "27.5.2", "27.5.3", "27.5.4", "27.5.5", "27.5.6"}
# 28.1.10: the workbook's running totals leave out the panel (Total A 47648.77); the corrected totals reproduce
# the slip rate 75339. Values in the order of the rows after the labour lines.
ANALYSIS_AMOUNTS = {"28.1.10": [54968.77, 8245.32, 63214.09, 632.14, 63846.23, 11492.32, 75338.55, 75339]}
ANALYSIS_AMOUNT_LABELS = ("Total", "Overhead & Profit @15%", "Labours cess@1%", "Add 18% GST", "Rate of Each", "Say")

# Analysis lines without an ICD number, by description: mapped to the Appendix I/II (or civil) item that is meant,
# or dropped where Appendix II has no such item (no resource is added for them; see OBSERVATIONS.md).
ANALYSIS_LINE_BY_DESCRIPTION = {
    "add valve cladding": ("3023", 360),
    "khallasi": ("1007", 805),
    "cement sand and grit etc.": ("2935", 7.2),
    "excavation i/c refilling etc. as required": ("15.4", 830),
}
ANALYSIS_DROP_BY_DESCRIPTION = ("cold water tank", "tank connections and water inlet valve", "battery rack i/c connections",
                                "basic price of insulation - 25 mm")

# Analyses that cannot be reproduced from Appendix II items alone: the DAR adds lump-sum lines that have no Appendix II
# item (battery racks of the UPS, tank and connections of solar water heaters, screws of ducts). No resource is added for
# them; the rate of the main material of the item is back-calculated so that the analysis gives the published rate.
BACKCALC_ITEMS = (["16.1.%d" % n for n in range(1, 5)] + ["16.2.%d" % n for n in range(1, 6)]
                  + ["26.1.%d" % n for n in range(1, 5)] + ["26.2.%d" % n for n in range(1, 14)]
                  + ["30.15", "30.16", "30.17", "30.18"])
