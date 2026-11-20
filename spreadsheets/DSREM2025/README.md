# DSR (E&M) 2025

Source: CPWD Delhi Schedule of Rates (E&M) 2025 workbook `DSR EandM 2025 3 09 2025.xlsx` and the published analysis of rates `DAR(E&M) 2025 DAR.pdf` (reference only).

| File | Contents |
|---|---|
| `schedule.xlsx` | Code, Description, Unit, Rate, Category, Remarks from sheet "DSR 2025"; chapters become categories; DELETED items dropped; codes stored as numbers restored (15.1 → 15.10 in sequence); repeated codes renumbered (see below); civil items "Rate to be taken from Civil DSR" carry the rate the analyses use, with a remark. |
| `resources.xlsx` | Code, Description, Unit, Rate, Category from "APPENDIX-II BASIC MATERIAL RATE" (labour and materials); section headings become categories; descriptive lines above short item rows are joined into the description. |
| `analysis.xlsx` | The six analysis columns of every chapter sheet ("CH…"), one after another (CH-16's extra unit column between Qty and Rate is dropped); analyses numbered differently from the schedule carry the schedule code (see below). |
| `corrections.csv` | Every analysis change the build makes to reproduce the book: item, book row, book code/description/quantity/rate/amount, the resource used, the quantity and the remark stored on the analysis line. |

Rebuild:

```sh
.venv/bin/python tools/prepare_dsrem2025.py   # writes the three workbooks above
.venv/bin/python tools/build_dsrem2025.py     # writes Other databases/DSREM2025.eproj and corrections.csv
```

The build imports the schedule (code hierarchy), then resources, then all analyses, reconciles the analyses with the book (`tools/dsrem2025_reconcile.py`), and finally restores the published schedule rates.

## Numbering fixes (prepare step)

The "DSR 2025" sheet repeats codes; the chapter sheets number the same items differently. The prepare step prints each change.

- Repeated schedule codes: 11.1.34 appears twice (4 × 25 and 4 × 35 sq. mm) → 11.1.34, 11.1.35, 11.1.36 as in the analyses; the items under 23.4 are numbered 23.3, 23.3.1–23.3.3 → 23.4.1–23.4.4; the 630 KVA item under 24.9 is numbered 24.8.6 → 24.9.6. Renumbered items say "Numbered … in the book" in their remarks. The coded sub-heading "31.12.1 High Static Ductable units" before item 31.12.1 keeps only its text.
- Analyses moved to the schedule item with the same description and rate: 31.12.2 → 31.12.3 and 31.12.3 → 31.12.4 (the schedule skips 31.12.2), 18.19.1–9 → 8.19.1–9, 30.10.1.1–6 → 30.10.1–6, 5.1.4 → 26.1.4, and "5190" (a resource code in the item code cell) → 20.15. A move needs the analysis result to equal the target's published rate.

## Analysis reconciliation (build step)

Every resource line keeps the book's amount; the line's remarks say what the book shows and how the line was adjusted.

- **Unit item X.** Lines without a matching Appendix II resource (no code, or a code that is another resource, e.g. 19.9.3 lists an XLR connector under 5164, a keypad in Appendix II) use the resource "X – Unit item" (unit Rs, rate 1, category UNIT ITEMS) with quantity = book amount; the remarks hold the book's description, quantity, rate and amount. Examples: battery racks (26.x), fire pump controllers (27.5.x), cold water tanks and tank connections (16.1.x), excavation (15.16.x), "Add for screws etc." lump sums (30.15, 30.17).
- **Relinked lines.** Codeless or mis-coded lines whose description and rate match an Appendix II resource are linked to it: "Wiremen"/"Khallasi" in 39.17–39.20 → 1001/1007; "Fitter, Grade 1" coded 1006 (Painter) in 27.11–27.12 → 1004.
- **Quantity back-calculation.** Where the book prices a resource differently from Appendix II, or its amount is not quantity × rate, the quantity becomes book amount ÷ Appendix II rate: 4.4.2/4.5.4 (painting 2936 at ₹36, Appendix II ₹7.20 → quantity 5), 8.9.3 (labour at ₹805/₹783), 11.4.29 (cable jointer and khallasi charged for a full day against 0.25), 12.5 (sundries at ₹0 → quantity 0), 15.14.4 (cement at the collar rate ₹63), 27.11.x/27.17.x (quantity 0 with an amount → 1), 30.2.13/30.2.14 (19 mm insulation at the 32 mm rate), 39.14 (₹147 against ₹105). Differences from the book multiplying unrounded rates (₹1850.3390 against ₹1850.34) are left alone.
- **Book arithmetic.** Where a book subtotal adds a row a second time (27.13 and 28.5.3.4 the cartage, 27.18.1/27.18.2 the materials total), a "Book adjustment" group with a unit item line keeps that amount before the subtotal. 30.21 rounds the cost of 10 sqm and then divides by 10; a multiplier 0.1 and a rounding row follow the analysis. These structural changes are kept only when they bring the analysis to the published rate.

Result: of 2,134 priced items, 2,114 have an analysis, and every analysis reproduces its published rate within ₹1. 84 differ by up to ₹0.10 and 19 by up to ₹1, because the book keeps unrounded intermediate amounts while GEstimator rounds each step; the published rates are kept.

## Remaining gaps

- No analysis in the book for 1.14, 4.2.9, 4.2.14, 6.10, 19.3.1, 20.20.1, 31.1.1–31.1.3 and 42.11.6, nor for the civil items 15.1–15.13 ("Rate to be taken from Civil DSR"; 15.7 and 15.9 carry the rate the analyses use).
- 25.1.8–25.1.23 and 25.2.17–25.2.23 are empty analysis tables without schedule items.
- The two-level headings 30.7 and 30.11 (each followed directly by another heading) are not imported; their sub-headings and items are.
- Some Appendix II descriptions carry the previous section's heading (e.g. 4015/4016 nitrile insulation start with "Hot Dipped Galvanized CABLE TRAYS"); the prepare step's context joining needs a section-boundary check.
- Database notes and the latest amendments/correction slips are not applied yet (roadmap).
