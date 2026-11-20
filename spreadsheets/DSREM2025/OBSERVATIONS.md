# DSR (E&M) 2025: observations

Sources: `DSR EandM 2025 3 09 2025.xlsx` (workbook), `DSR_EM_2025.pdf` (book, authoritative for text and rates), `DAR(E&M) 2025 DAR.pdf` (analyses), `Correction slip 1.pdf` (27-11-2025, prevails over book and DAR). Edits live in `tools/dsrem2025_nomenclature.py` and `tools/dsrem2025_correction_slip1.py`; `tools/prepare_dsrem2025.py` applies them. The book and DAR were read as text with automatic parsing, so counts are approximate; the slip is a scan read by eye.

## 1. Precedence used

1. Correction Slip No. 1.
2. Printed book (text, units, rates).
3. DAR for analysis content and for numbering where the book repeats or skips a number.
4. Workbook only where none of the above speaks.

## 2. What was changed

### Correction slip
- 31 rates (4.4.2, 4.5.4, 8.9.3, 11.2.23/24, 11.4.29, 12.5, 15.14.4, 19.10.1, 20.5.6, 27.12.x, 27.13, 27.17.2, 27.18.x, 28.1.10, 28.5.3.3/4, 30.2.13/14, 30.27.11/12, 39.14, 39.18.x).
- Description edits for 4.4, 4.5, 8.3, 8.8, 8.9, 8.18, 26.1, 26.2, 30.2, 32.5, 39.1-39.9, 39.14, 39.22, 40.9-40.11 and the cosmetic changes (50/60 Hz, 12V DC /24V DC).
- Item 39.10 deleted.
- Appendix I: 1020 Electronic Technician replaced by 1021 Technician (also in the analyses that used it).
- Appendix II: 5246-5249 rates 26.25, 52.50, 78.75, 105.00 (also in the 39.18.x analyses).

### Book against workbook
- Stock phrase "Supplying, Installation, Testing and Commissioning of" in the workbook replaced by the book's opening words (10.9, 10.10, 13.15-13.23, 20.28, 23.1-23.9, 27.22).
- Spelling and typing slips fixed (1.56, 1.57, 1.59, 2.21, 2.22, 20.5.x, 20.10.x, 25.1, 39.3.1, 39.15, 40.x "spcifications", 42.x "Supply" for "Supplying").
- Text cut at the end of a cell restored (28.1.10, 28.1.11 battery charger line, 30.21, 39.12, 39.13, 39.15, 39.16).
- Workbook values replaced by the book's: 1.50, 20.27, 25.1, 32.4 (400/230V), 33.1-33.3, 36.1 (WC), 39.19.2, 40.4.2, 40.5, 42.9.1.
- Stray line "2 MP IP IR Dome Camera" removed from 39.26.
- Items marked DELETED in the book dropped: 6.1, 6.10, 6.11.
- Rates rounded to whole rupees, as printed (the workbook keeps formula results such as 1930.0383); civil sub-rates (chapter 15) and 21.1.1/21.1.2 keep their decimals.
- Units: schedule "Metre" to "Meter"; Appendix II "Nos/No/E" to "Each", "m/Mtr/Mtrs." to "Meter", "Per sq meter" to "sq. m", 2416 "1225" to "Set".
- Chapter 19 has no title row in the workbook, so its items sat under chapter 18's category; set to FACADE LIGHTING.
- Resource 5274 had `#REF!` for its description; text taken from the book. Typos in resource descriptions fixed.
- Resources 3099 (20400 CMH) and 3162 (23800 CMH) are printed swapped in the book; set back (205166.44 and 215780.34), as the slip does for items 30.27.11/12. 5174 stays as printed (2138).

### Numbering (book repeats or skips; DAR numbering used)
| Book | Database | Note |
|---|---|---|
| 24.8.6 (second, 630 kVA, 1568164) | 24.9.6 | |
| 11.1.34 (4x35) / 11.1.35 (4x50) | 11.1.35 / 11.1.36 | 11.1.34 printed twice |
| 23.3, 23.3.1-3 under 23.4 | 23.4.1-4 | |
| 31.12.1 (heading) | text of 31.12 | heading carried a number |
| 31.12.3 / 31.12.4 | 31.12.2 / 31.12.3 | 31.12.2 skipped |
| DAR 18.19.x | 8.19.x | |
| DAR 30.10.1.x (group 30.10.1) | 30.10.x (30.10) | |
| DAR 5.1.4 | 26.1.4 | |

### Analyses (workbook defects corrected on import)
- 4.2.9 and 4.2.14: the book and DAR have no headings; headers inserted between the two analyses that are run together.
- 19.3.1 (100 W) and 20.20.1 (80 mm dia): their lines sat under the group heading; 20.15: its analysis carried the resource code 5190 as item code.
- 31.1.1-31.1.3: numbered 31.2.1-31.2.3 under heading 31.1.
- 42.11.6 (immersion temperature sensor): its lines sat under a second, wrongly numbered 42.11.7 header.
- Chapter 39 labour lines without a code ("Wiremen", "Khallasi") at the Appendix I rates mapped to 1001 and 1007.
- Resource codes the DAR gives to the wrong item, now mapped to the item meant (the importer had silently used the Appendix II item of that code):
  - "Fitter, Grade 1" coded 1006 (Painter) in 27.11.5, 27.11.8, 27.11.9 and 27.12.1-27.12.6: now 1004. With the Fitter rate the analyses of 27.12.2-27.12.6 reach the slip rates (7691, 9869, 11386, 15603, 24088).
  - 19.10.1: keypad is 5164 (6225), the DAR uses 5165 (a fountain nozzle, 7275); with 5164 the analysis gives the slip rate 8962.
  - 27.17.2: gate valve 4213 and lump sum 4355 as in 27.17.1 (the DAR uses 4256, a G.I. pipe, and 4255, a 300 mm pipe at Rs 5026.50); the analysis then gives the slip rate 11086.
  - 19.9.3: XLR connector is 5163 (1360), the DAR uses 5164.
  - 27.5.1-27.5.6: the priced line has no code; the code stands on the line above (4321-4326, the control panels); the lines had been merged into one resource of Rs 175000.
- Lines without an ICD number mapped to the item meant: "Add Valve Cladding" to 3023, "Khallasi" (24.25.6) to 1007, "Cement sand and grit etc." (28.4.1) to 2935, "Excavation i/c refilling" (15.16.x) to the civil item 15.4. Where the DAR rate differs from Appendix I/II (Khallasi 663, cement 1.73) the Appendix rate applies.
- 28.1.10: the workbook's totals leave out the panel (Total A 47648.77); with the correct totals the analysis gives the slip rate 75339.
- Chapter 16: the workbook keeps formulas without saved values, so its analyses had no amounts. The DAR chain (cartage 1 %, ITC 4 %, overheads 15 %, cess 1 %, GST 18 %) is written out.
- Resources 2322 and 2323 (3½ X 150 and 185 sq mm kits) set to 946 and 1326: the DAR and the slip rates of 11.2.23/11.2.24 price them that way round; the book prints 1326 and 946. Resource 5174 set to 5138: the book prints 2138 (a copy of 5172), the slip rate of 20.5.6 (7397) needs 5138.
- Four sub-heading rows of Appendix II that carry schedule item numbers (35.1, 19.2, 19.3, 40.2) dropped from the resources.

### Back-calculated material rates (no resource added)
The DAR adds lump-sum lines that have no Appendix II item: battery racks of the UPS (26.1.x, 26.2.x, Rs 500 each), tank (Rs 11 per litre) and connections (Rs 400) of the evacuated tube solar heaters (16.1.x), screws of ducts (30.15-30.18, Rs 260). No resource is added for them. The rate of the main material of the item is back-calculated so that the analysis gives the published rate; 30 resources are changed and listed in `backcalculated_materials.csv` with the book rate, the adjusted rate and the result. The collector and UPS rates therefore differ from Appendix II of the book by the lump sums (up to about 5 %); each of those resources is used by one item only.

## 3. Observations in the sources (not all changed)

### Book
- Rate series that run the wrong way, fixed by the slip: 30.27.11/12; 20.5.5 (3726) against 20.5.6 (3078).
- Same rate for consecutive sizes that look unintended: Appendix II 1534 (1400 A) and 1535 (1600 A bus trunking) both 19438; 5172 and 5174 both 2138 (5174 kept as printed, the workbook has 5138, which fits the series 2588, 5138, 5438).
- Resources 2322 (3½ X 150) at 1326 and 2323 (3½ X 185) at 946: the larger kit is cheaper. The DAR prices them the other way round and the slip's 11.2.23/24 rates follow the DAR, so the two analyses use 946 and 1326. Appendix II is left as printed.
- 42.11.18 prints 357752 in the schedule; an automatic read gave 1770644.20 from another line (parse noise, not an error).
- Chapter title lines are missing for 19 and 38 in the workbook; the book contents page names chapter 19 "Façade Lighting".
- Description lines lose degree signs and line breaks when read from the PDF ("0C"); the workbook keeps them and was left alone.
- Remaining typos kept as printed: "orfice" (20.5.6, per the slip), "nesssary" corrected to "necessary" in 42.5 only.

### DAR
- No heading for 4.2.9 and 4.2.14; the import reads their analyses as part of 4.2.8 and 4.2.13. Both items have no analysis.
- Several chapter 5 and other blocks are merged in the text so only 1,188 items give both a DAR and a workbook "Say" value; of these 1,181 agree. The other seven are parse artefacts except 11.2.23/24 (above).
- Analyses of slip items still show the old amounts. A slip item's published rate is kept; the analysis is not rebuilt.
- Rows of `#REF!` in the workbook analyses (25.1.8-25.1.23, 25.2.16-25.2.23) have no counterpart in the DAR.
- Rate differences of Re 1 between recalculation and published rate (1.15.3, 1.16, 1.21.3, 1.50.2, 24.1.5): the book keeps unrounded intermediate amounts. Published rates are kept.

### Slip
- Existing text is abridged with dots; only the visible differences were applied.
- Some corrections are already in the workbook (30.27.11, 32.3, 39.4, 20.5.6 rate); the slip's value is applied in every case.
- Appendix I note about labour and hire charges added by the slip is not imported.
- Items 28.1.10 and 28.5.3.3/4: the slip changes the schedule rate but the DAR analysis still gives the old one.

## 4. Database statistics (against the book)

| | Book | Database |
|---|---|---|
| Schedule rows | 2,439 coded rows, 2,118 priced, 13 DELETED | 2,428 rows, 2,128 priced, 300 headings |
| Resources | 2,193 | 2,195 (no auto-created `R…` codes; civil codes 15.4/15.7/15.9) |
| Items with an analysis | | 2,126 of 2,128 priced (15.7 and 15.9 are civil rates) |

- Schedule rates: 2,069 equal; 31 differ through the slip; 3 other (11.1.35, 31.12.3 after renumbering; 42.11.18 parse noise).
- Schedule units: 2,101 compared, all equal.
- Schedule descriptions: 2,348 equal; 25 differ through the slip; 37 differ for reasons of structure or reading noise (headings, chapter 15 civil items, merged sub-rows).
- Only in the database: 11.1.36, 23.4.1-4, 31.12.2, 30.11.4.1-10 (missed by the reading), 1.1, 1.1.1.
- Only in the book: the 13 DELETED items and 39.10.
- Appendix rates: 2,156 equal; 6 differ (5246-5249 slip; 1528 and 3059 reading noise).
- Analyses matched on import: 2,126; 26 blocks stay unmatched (`#REF!` blocks of chapter 25, deleted 6.1, 6.11 and 39.10).
- Analysis against published rate after the fixes: of 2,126 analyses, 2,092 agree to less than Re 1 and about 20 differ by about Re 1 (through rounding of the book's unrounded intermediate amounts; the 39.18.2 and 39.18.4 slip rates 99 and 174 give 100 and 175 with the corrected Appendix II rates); the others are listed in section 5.
- Chapters with different priced counts: 1 (175/176), 6 (10/7, deleted items), 15 (20/22), 19 (32/30), 30 (168/177, 30.11.4.x), 35 (27/26), 39 (41/45).

## 5. Gaps

- 15.7 and 15.9 are rates with those codes (civil items, no analysis); other chapter 15 items take their rates from the Civil DSR, which this database does not hold.
- Analyses still different from the published rate by more than Re 1:
  - 30.3.10 (analysis 2948, published 2716): the labour groups of the insulation work are counted although the sheet does not add them.
  - 30.7.4.6 (8598, published 8644): the 25 mm insulation line (Rs 152.54 per metre) has no Appendix II item and was dropped.
  - 30.21 (8903, published 890): the DAR gives the cost for 10 sq m and divides by 10; the import does not carry the division.
  - 26.2.7-26.2.13 and 16.1.4: up to Rs 5 (the back-calculation rounds the rate to two decimals).
- Slip item analyses now agree with the slip rates except 39.18.2 and 39.18.4 (Re 1).
- Back-calculated materials (30) differ from Appendix II of the book; see `backcalculated_materials.csv`.
- 26 analysis blocks stay unmatched: `#REF!` blocks of chapter 25, deleted 6.1, 6.11 and 39.10.
- 95 Appendix II resources are not used by any analysis; they are kept as published.
- Analyses are verified against the DAR for part of the items only (1,188 with a readable rate); the rest rely on the workbook.
- The slip was read by eye; item texts of 39.x and 40.x were re-checked against the database after the build.
