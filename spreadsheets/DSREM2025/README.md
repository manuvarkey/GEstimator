# DSR (E&M) 2025

Source: CPWD Delhi Schedule of Rates (E&M) 2025 workbook `DSR EandM 2025 3 09 2025.xlsx` and the published analysis of rates `DAR(E&M) 2025 DAR.pdf` (reference only).

| File | Contents |
|---|---|
| `schedule.xlsx` | Code, Description, Unit, Rate, Category, Remarks from sheet "DSR 2025"; chapters become categories; DELETED items dropped; codes stored as numbers restored (15.1 → 15.10 in sequence); civil items "Rate to be taken from Civil DSR" carry the rate the analyses use, with a remark. |
| `resources.xlsx` | Code, Description, Unit, Rate, Category from "APPENDIX-II BASIC MATERIAL RATE" (labour and materials); section headings become categories; descriptive lines above short item rows are joined into the description. |
| `analysis.xlsx` | The six analysis columns of every chapter sheet ("CH…"), one after another. |

Rebuild:

```sh
.venv/bin/python tools/prepare_dsrem2025.py   # writes the three workbooks above
.venv/bin/python tools/build_dsrem2025.py     # writes Other databases/DSREM2025.eproj
```

The build imports the schedule (code hierarchy), then resources, then all analyses, and finally restores the published schedule rates (the book keeps unrounded intermediate amounts, so a recalculated analysis can differ by ₹1).

Known inconsistencies in the book (reported by the import, left as published): duplicate codes (11.1.34, 23.3.x, 24.8.6, 31.12.1); analyses without a schedule item or numbered differently from the schedule (25.1.8–25.1.23, 25.2.17–25.2.23, 18.19.x, 23.4.x, 30.10.1.x and a few others); analyses using resource rates or codes that differ from Appendix II (e.g. 4.4.2 uses ₹36 for 2936, 27.12.1 uses code 1006 for a fitter); chapter 16 analyses that do not add up to the published rates.
