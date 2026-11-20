# DSR (E&M) 2025

Source: CPWD Delhi Schedule of Rates (E&M) 2025 workbook `DSR EandM 2025 3 09 2025.xlsx` (combined and updated up to 08/2025), with the published books in `reference/` (kept locally, not committed): `DSR E&M 2025.pdf`, the analysis of rates `DarEm2025PART1–3.pdf`, and Correction Slip No. 1 dated 27-11-2025 (`1.pdf` for the schedule, `1-ana.pdf` = `DarEm2025Part4.pdf` for the analyses; scanned).

| File | Contents |
|---|---|
| `schedule.xlsx` | Code, Description, Unit, Rate, Category, Remarks from sheet "DSR 2025"; chapters become categories; DELETED items dropped; codes stored as numbers restored (15.1 → 15.10 in sequence); repeated codes renumbered (see below); civil items "Rate to be taken from Civil DSR" carry the rate the analyses use; correction slip changes applied, each noted in the item remarks. |
| `resources.xlsx` | Code, Description, Unit, Rate, Category from "APPENDIX-II BASIC MATERIAL RATE" (labour and materials); section headings become categories; descriptive lines above short item rows are joined into the description; correction slip changes applied. |
| `analysis.xlsx` | The six analysis columns of every chapter sheet ("CH…"), one after another (CH-16's extra unit column between Qty and Rate is dropped); notes under resource lines kept as text; analyses numbered differently from the schedule carry the schedule code; analyses corrected by the slip replace the book's. |
| `correction_slip_1.csv` | Transcription of Correction Slip No. 1 (schedule and Appendix changes). Rates are applied; complete new descriptions (39.14, 40.9.3) replace the old ones; the changed phrases the slip quotes are replaced in the descriptions (each must be found, or reported); chapter 40 specifications that are not in the schedule workbook are noted in the item remarks. |
| `correction_slip_1_analysis.csv` | Corrected analyses from the slip that differ from the book's in their resources or arithmetic: 19.1.6 (new), 19.10.1 (keypad 5164), 27.17.2 (globe valve 4213, fittings 4355), 28.1.10 (materials included in the total). |
| `corrections.csv` | Every change the build makes to an analysis line (link, back-calculated resource, unit item, multiplier) and every line note, with the book's figures. |
| `discrepancies.csv` | The book's differences, documented and not reproduced: line amounts that are not coefficient × Appendix II rate, subtotals that add a row twice, and analyses whose rate differs from the published rate. |

Rebuild:

```sh
.venv/bin/python tools/prepare_dsrem2025.py   # writes the three workbooks above
.venv/bin/python tools/build_dsrem2025.py     # writes Other databases/DSREM2025.eproj, corrections.csv and discrepancies.csv
```

The build imports the schedule (code hierarchy), then resources, then all analyses, reconciles the analyses with the book (`tools/dsrem2025_reconcile.py`), and finally restores the published schedule rates (after the correction slip).

## Numbering fixes (prepare step)

The "DSR 2025" sheet repeats codes; the chapter sheets number the same items differently. The prepare step prints each change.

- Repeated schedule codes: 11.1.34 appears twice (4 × 25 and 4 × 35 sq. mm) → 11.1.34, 11.1.35, 11.1.36 as in the analyses; the items under 23.4 are numbered 23.3, 23.3.1–23.3.3 → 23.4.1–23.4.4; the 630 KVA item under 24.9 is numbered 24.8.6 → 24.9.6. Renumbered items say "Numbered … in the book" in their remarks. The coded sub-heading "31.12.1 High Static Ductable units" before item 31.12.1 keeps only its text.
- Analyses moved to the schedule item with the same description and rate: 31.12.2 → 31.12.3 and 31.12.3 → 31.12.4 (the schedule skips 31.12.2), 18.19.1–9 → 8.19.1–9, 30.10.1.1–6 → 30.10.1–6, 5.1.4 → 26.1.4, and "5190" (a resource code in the item code cell) → 20.15. A move needs the analysis result to equal the target's published rate.
- Appendix II repeats "1020 Electronic Technician" where Appendix I has 1021 Technician; 1021 is added (the analyses already use it).

## Correction Slip No. 1 (27-11-2025)

31 schedule rates (4.4.2, 4.5.4, 8.9.3, 11.2.23/24, 11.4.29, 12.5, 15.14.4, 19.10.1, 20.5.6, 27.12.2–6, 27.13, 27.17.2, 27.18.1/2, 28.1.10, 28.5.3.3/4, 30.2.13/14, 30.27.11/12, 39.14, 39.18.1–4), 39.10 deleted, Appendix II 5246–5249 (Cat6A cable ₹26.25/52.50/78.75/105). The workbook already carries 20.5.6, 30.27.11/12, 39.18.1 and 5246; the prepare step reports these as already applied. Most corrected rates are what the book's analyses give with Appendix II rates (e.g. 4.4.2 ₹1458, 27.13 ₹1424, 12.5 ₹9096), so those analyses are unchanged.

Specification changes are merged into the descriptions of 4.4, 4.5, 8.3, 8.8, 8.9, 8.18, 26.1, 26.2, 30.2, 32.3, 32.5, 39.1–39.5, 39.7–39.9 and 39.22 (46 phrases, all found); the items say "description amended" in their remarks. The detailed camera and NVR specifications of 40.1, 40.2, 40.8, 40.9, 40.10 and 40.11 are only in the printed book, so those changes stay as remarks.

Derived from the slip: it swaps the schedule rates of 11.2.23 (3½ × 150 sq. mm → ₹2117) and 11.2.24 (185 sq. mm → ₹2643) but leaves Appendix II, where the 150 sq. mm kit 2322 (₹1326) is dearer than the 185 sq. mm kit 2323 (₹946). The two kit rates are swapped to match (₹946 and ₹1326), so both analyses give the corrected rates; the book's kit prices are noted on the analysis lines.

## Analysis reconciliation (build step)

Coefficients (quantities) are the book's and are not changed. Remarks the book writes under a resource line ("= 0.2 @ 1.11kg/m = 0.22kg") stay on the line; the build's notes follow them.

- **Book amount differs.** Where the book prices a resource differently from Appendix II or its amount is not coefficient × rate, the line keeps the Appendix II resource and the difference is noted on the line and in `discrepancies.csv` (e.g. 4.4.2 painting 2936 at ₹36 against ₹7.20; 11.4.29 labour charged for a full day against 0.25; 12.5 sundries at ₹0; 39.18.2–4 cable at the old rates). The correction slip confirms the Appendix II based rates for these items.
- **Relinked lines.** Codeless or mis-coded lines whose description matches an Appendix II resource are linked to it: "Wiremen"/"Khallasi" in 39.17–39.20 → 1001/1007; "Fitter, Grade 1" coded 1006 (Painter) in 27.11–27.12 → 1004.
- **Back-calculated rates.** Lines with a coefficient but no Appendix II resource get a resource of their own (category RESOURCES FROM ANALYSES) whose rate is the book amount ÷ coefficient: battery racks (26.x), fire pump controllers and battery charger (27.5.x), cold water tanks and tank connections (16.1.x), excavation (15.16.x), valve cladding and insulation (30.7.x), cement/sand (28.4.1), and the XLR connector that 19.9.3 lists under the keypad's code 5164.
- **Unit item X.** Rows the book prices without a coefficient ("Add for screws etc. LS ₹260" in 30.15–30.18) use "X – Unit item" (unit Rs, rate 1, quantity = amount) before the following subtotal.
- **Book arithmetic.** Subtotals that add a row a second time (27.13, 27.18.x, 27.29, 28.5.3.x, 28.5.4) are noted in the analysis remarks and `discrepancies.csv`. 30.21 rounds the cost of 10 sqm and then divides by 10; a multiplier 0.1 and a rounding row follow the analysis.

Result: of 2,133 priced items, 2,113 have an analysis, and every analysis reproduces its published rate within ₹1 (83 within ₹0.10 and 17 within ₹1, from the book's unrounded intermediate amounts).

## Remaining gaps

- No analysis in the book for 1.14, 4.2.9, 4.2.14, 6.10, 19.3.1, 20.20.1, 31.1.1–31.1.3 and 42.11.6, nor for the civil items 15.1–15.13 ("Rate to be taken from Civil DSR"; 15.7 and 15.9 carry the rate the analyses use).
- 25.1.8–25.1.23 and 25.2.17–25.2.23 are empty analysis tables without schedule items; the 39.10 analysis remains in the book but the item is deleted.
- Chapter 40 specification changes of the slip are remarks only (the specifications are not in the schedule workbook).
- The two-level headings 30.7 and 30.11 (each followed directly by another heading) are not imported; their sub-headings and items are.
- Some Appendix II descriptions carry the previous section's heading (e.g. 4015/4016 nitrile insulation start with "Hot Dipped Galvanized CABLE TRAYS").
- Database notes are not written yet (roadmap).
