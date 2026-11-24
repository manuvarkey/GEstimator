---
description: Typical coefficients of utilisation for six fitting types at 70% ceiling, 50% wall and 20% effective floor-cavity reflectance.
---

# Typical coefficients of utilisation (CU)

Use these values for a preliminary estimate when fitting-specific photometric data is unavailable and the room has reflectances close to **70% ceiling, 50% walls and 20% effective floor cavity**. Select the column for a fitting with a similar light distribution. Use the selected luminaire's photometric data when available or when the room reflectances differ materially from these assumptions.

Calculate the room cavity ratio as `RCR = 5 × Hm × (L + W) / (L × W)`, using the room length and width and the luminaire mounting height above the working plane in the same units. RCR equals `5 / kr` when the room index uses the same dimensions. Interpolate linearly between adjacent RCR rows. If RCR is outside the tabulated range, use fitting-specific data or leave the CU unresolved. The entries are dimensionless factors ready to use as `μ` in the lumen formula.

| RCR | 2×2 panel | Batten | Flat downlighter | Inset downlighter | Wide-beam high-bay | Wide-beam suspended |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1.16 | 1.14 | 1.16 | 1.07 | 1.16 | 1.16 |
| 1 | 1.04 | 0.96 | 1.01 | 0.96 | 1.06 | 1.07 |
| 2 | 0.92 | 0.83 | 0.88 | 0.86 | 0.95 | 0.98 |
| 3 | 0.82 | 0.72 | 0.77 | 0.77 | 0.86 | 0.90 |
| 4 | 0.74 | 0.64 | 0.68 | 0.69 | 0.78 | 0.83 |
| 5 | 0.67 | 0.57 | 0.61 | 0.63 | 0.71 | 0.76 |
| 6 | 0.60 | 0.51 | 0.55 | 0.57 | 0.64 | 0.70 |
| 7 | 0.55 | 0.46 | 0.50 | 0.52 | 0.59 | 0.65 |
| 8 | 0.51 | 0.42 | 0.46 | 0.48 | 0.54 | 0.60 |
| 9 | 0.47 | 0.39 | 0.42 | 0.45 | 0.50 | 0.56 |
| 10 | 0.43 | 0.36 | 0.39 | 0.41 | 0.46 | 0.52 |

The values come from the zonal-cavity exports in `MEP-Design-Sheets/Lighting/CU Tables` for 2x2 Panel, Batten, Downlighter Flat, Downlighter Inset, Highbay WB and Suspended WB. Each column is the supplied RC 70 / RW 50 series at effective floor-cavity reflectance 0.20. The source percentages were divided by 100.
