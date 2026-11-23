/** Rounding choices accepted by the backend for schedule quantities. */
export const quantityRoundingOptions = [
  "Round within 1%",
  "Round within 5%",
  "Round within 10%",
  "Round to 10000",
  "Round to 1000",
  "Round to 100",
  "Round to 10",
  "Round to 0",
  "Round to .0",
  "Round to .00",
  "Round to .000",
  "No rounding",
] as const;
