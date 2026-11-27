<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ name: string; size?: number }>();

// Locally drawn icons following the OpenAEC B2 visual grammar (see docs/ui-guidelines.md):
// 24-unit grid, round caps/joins, 1.6-unit corner radii, open line work, a neutral body
// and at most one small amber accent detail. Navigation, window and state glyphs stay
// monochrome. Each entry is [body, accent?].
const rr = (x: number, y: number, w: number, h: number, r = 1.6) =>
  `M${x + r} ${y}H${x + w - r}a${r} ${r} 0 0 1 ${r} ${r}V${y + h - r}a${r} ${r} 0 0 1-${r} ${r}H${x + r}a${r} ${r} 0 0 1-${r}-${r}V${y + r}a${r} ${r} 0 0 1 ${r}-${r}Z`;
const circle = (cx: number, cy: number, r: number) =>
  `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0-${2 * r} 0Z`;
const backSheet = "M16 5V4.6A1.6 1.6 0 0 0 14.4 3H4.6A1.6 1.6 0 0 0 3 4.6v9.8A1.6 1.6 0 0 0 4.6 16H5";
const tray = "M4 15v3.4A1.6 1.6 0 0 0 5.6 20h12.8a1.6 1.6 0 0 0 1.6-1.6V15";

const icons: Record<string, [string, string?]> = {
  blank: [""],
  // Navigation, window and state glyphs: monochrome.
  forward: ["M4 12h15 M13 6l6 6-6 6"],
  back: ["M20 12H5 M11 6l-6 6 6 6"],
  up: ["m6 14.5 6-6 6 6"],
  down: ["m6 9.5 6 6 6-6"],
  chevron: ["m9 5.5 6.5 6.5L9 18.5"],
  collapse: ["m8 9 4-4 4 4 M8 15l4 4 4-4"],
  expand: ["m8 5 4 4 4-4 M8 19l4-4 4 4"],
  close: ["m6 6 12 12 M6 18 18 6"],
  multiply: ["m7 7 10 10 M7 17 17 7"],
  check: ["m5 12.5 4.5 4.5L19 7"],
  grip: ["M8 5h.01 M16 5h.01 M8 12h.01 M16 12h.01 M8 19h.01 M16 19h.01"],
  dots: ["M5 12h.01 M12 12h.01 M19 12h.01"],
  minimize: ["M5 17h14"],
  maximize: [rr(5, 5, 14, 14)],
  plus: ["M12 5v14 M5 12h14"],
  play: ["M8 5.3v13.4a.8.8 0 0 0 1.2.7l10.6-6.7a.8.8 0 0 0 0-1.4L9.2 4.6A.8.8 0 0 0 8 5.3Z"],
  stop: [rr(5, 5, 14, 14)],
  undo: ["M4 9h11.5a4.5 4.5 0 0 1 0 9H10 M8 5 4 9l4 4"],
  redo: ["M20 9H8.5a4.5 4.5 0 0 0 0 9H14 M16 5l4 4-4 4"],
  sun: [
    circle(12, 12, 4) +
      " M12 2.5v2 M12 19.5v2 M2.5 12h2 M19.5 12h2 M5.3 5.3l1.4 1.4 M17.3 17.3l1.4 1.4 M5.3 18.7l1.4-1.4 M17.3 6.7l1.4-1.4",
  ],
  moon: ["M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"],
  filter: ["M4.6 4h14.8a.6.6 0 0 1 .5 1L14 12.5v6l-4 2v-8L4.1 5a.6.6 0 0 1 .5-1Z"],
  attach: ["M16 7.5 9.2 14.3a1.8 1.8 0 0 0 2.5 2.5l6.8-6.8a3.8 3.8 0 0 0-5.4-5.4L6.3 11.4a5.8 5.8 0 0 0 8.2 8.2L19 15"],
  // Two-tone action icons: neutral body, small amber detail.
  file: [
    "M14 3H6.6A1.6 1.6 0 0 0 5 4.6v14.8A1.6 1.6 0 0 0 6.6 21h10.8a1.6 1.6 0 0 0 1.6-1.6V8Z M14 3v3.4A1.6 1.6 0 0 0 15.6 8H19",
    "M9 13h6 M9 17h4",
  ],
  folder: [
    "M3 18.4V5.6A1.6 1.6 0 0 1 4.6 4h3.8a1.6 1.6 0 0 1 1.3.7l1.1 1.6a1.6 1.6 0 0 0 1.3.7h5.3A1.6 1.6 0 0 1 19 8.6V11 M3 18.4A1.6 1.6 0 0 0 4.6 20H16.9a1.6 1.6 0 0 0 1.5-1.1l2.4-6.6a1 1 0 0 0-.9-1.3H7.4a1.6 1.6 0 0 0-1.5 1.1L3 18.4",
  ],
  save: [
    "M4.6 3h10.7a1.6 1.6 0 0 1 1.1.5l4.1 4.1a1.6 1.6 0 0 1 .5 1.1v10.7a1.6 1.6 0 0 1-1.6 1.6H4.6A1.6 1.6 0 0 1 3 19.4V4.6A1.6 1.6 0 0 1 4.6 3Z M7.5 3v3.9a.6.6 0 0 0 .6.6h6.4",
    "M7.5 21v-5.4a.6.6 0 0 1 .6-.6h7.8a.6.6 0 0 1 .6.6V21",
  ],
  database: ["M4 6a8 3 0 1 0 16 0a8 3 0 1 0-16 0 M4 6v12a8 3 0 0 0 16 0V6", "M4 12a8 3 0 0 0 16 0"],
  grid: [rr(3, 3, 18, 18) + " M3 15h18 M9 9v12", "M3 9h18"],
  library: [
    rr(3.5, 4, 4.5, 16, 1) +
      rr(10, 4, 4.5, 16, 1) +
      " M16.7 5.6l2.3-.6a.8.8 0 0 1 1 .6l2.9 13.2a.8.8 0 0 1-.6 1l-2.3.5a.8.8 0 0 1-1-.6L16.1 6.6a.8.8 0 0 1 .6-1Z",
    "M3.5 8h4.5 M10 8h4.5",
  ],
  child: ["M4 4h8 M7 4v9.4A1.6 1.6 0 0 0 8.6 15H12", "M17 12v6 M14 15h6"],
  search: [circle(10.5, 10.5, 6.5), "m15.5 15.5 4.5 4.5"],
  copy: [rr(8, 8, 13, 13), backSheet],
  cut: [circle(6.5, 17.5, 2.5) + circle(17.5, 17.5, 2.5) + "M8.3 15.7 16 4 M15.7 15.7 8 4", "M12 11.2v.01"],
  duplicate: [rr(8, 8, 13, 13) + " " + backSheet, "M14.5 11.5v6 M11.5 14.5h6"],
  paste: [
    "M8 5H6.6A1.6 1.6 0 0 0 5 6.6v12.8A1.6 1.6 0 0 0 6.6 21h10.8a1.6 1.6 0 0 0 1.6-1.6V6.6A1.6 1.6 0 0 0 17.4 5H16 M9 12h6 M9 16h4",
    rr(8, 3, 8, 4, 1),
  ],
  trash: [
    "M4 6h16 M9 6V4.6A1.6 1.6 0 0 1 10.6 3h2.8A1.6 1.6 0 0 1 15 4.6V6 M6 6l.9 13.5A1.6 1.6 0 0 0 8.5 21h7a1.6 1.6 0 0 0 1.6-1.5L18 6",
    "M10 10.5v6 M14 10.5v6",
  ],
  panel: [rr(3, 4, 18, 16), "M15 4v16"],
  "panel-left": [rr(3, 4, 18, 16), "M9 4v16"],
  help: [circle(12, 12, 9) + " M9.5 9.5a2.5 2.5 0 0 1 5 0c0 1.7-2.5 2-2.5 4", circle(12, 17, 0.5)],
  group: ["M4 6h16 M4 18h16", "M8.5 12H20"],
  sum: ["M17 5H7.5a.6.6 0 0 0-.4 1l5.4 6-5.4 6a.6.6 0 0 0 .4 1H17", "M17 5v1.5 M17 19v-1.5"],
  percent: ["M18 6 6 18", circle(7.5, 7.5, 2) + circle(16.5, 16.5, 2)],
  round: [
    "M7 5H5.6a.6.6 0 0 0-.6.6v12.8a.6.6 0 0 0 .6.6H7 M17 5h1.4a.6.6 0 0 1 .6.6v12.8a.6.6 0 0 1-.6.6H17",
    "M9 12h6",
  ],
  resource: [
    "M11.2 3.4a1.6 1.6 0 0 1 1.6 0l6.4 3.7a1.6 1.6 0 0 1 .8 1.4v7a1.6 1.6 0 0 1-.8 1.4l-6.4 3.7a1.6 1.6 0 0 1-1.6 0l-6.4-3.7a1.6 1.6 0 0 1-.8-1.4v-7a1.6 1.6 0 0 1 .8-1.4Z M12 12v8.8",
    "M4.3 7.6 12 12l7.7-4.4",
  ],
  settings: ["M4 7h16 M4 17h16", "M9 4.5v5 M15 14.5v5"],
  edit: ["M4 20h4l11.3-11.3a1.6 1.6 0 0 0 0-2.3l-1.7-1.7a1.6 1.6 0 0 0-2.3 0L4 16v4Z", "m13.5 6.5 4 4"],
  category: [
    "M3 4.6V11l9.4 9.4a1.6 1.6 0 0 0 2.3 0l5.7-5.7a1.6 1.6 0 0 0 0-2.3L11 3H4.6A1.6 1.6 0 0 0 3 4.6Z",
    circle(8, 8, 1.3),
  ],
  colour: [
    "M12 3a9 9 0 1 0 0 18h1.5a2 2 0 0 0 0-4H13a2 2 0 0 1 0-4h2.4A5.6 5.6 0 0 0 21 7.4C19.4 4.8 15.9 3 12 3Z",
    "M7.5 11.5h.01 M9.5 7.5h.01 M14 7h.01",
  ],
  refresh: ["M19 12a7 7 0 0 0-12.2-4.7L5 9 M5 12a7 7 0 0 0 12.2 4.7L19 15", "M5 4.5V9h4.5 M19 19.5V15h-4.5"],
  chart: ["M3 3v16.4A1.6 1.6 0 0 0 4.6 21H21", "M8 17v-5 M13 17V6 M18 17v-3"],
  link: ["M10.5 7.5l1.8-1.8a4 4 0 0 1 5.7 5.7l-1.8 1.8 M13.5 16.5l-1.8 1.8a4 4 0 0 1-5.7-5.7l1.8-1.8", "m9.5 14.5 5-5"],
  import: [tray + " M12 4v10.5", "m7.5 10.5 4.5 4.5 4.5-4.5"],
  export: [tray + " M12 4.5V15", "M7.5 8.5 12 4l4.5 4.5"],
  calculate: [
    rr(5, 3, 14, 18) + " M8.5 12h.01 M12 12h.01 M15.5 12h.01 M8.5 15.5h.01 M12 15.5h.01 M15.5 15.5h.01",
    "M8.5 7h7",
  ],
  rows: ["M4 5h16 M4 19h16", "M4 10h16 M4 14h16"],
  ruler: [
    "M3.7 15.6 15.6 3.7a1 1 0 0 1 1.4 0l3.3 3.3a1 1 0 0 1 0 1.4L8.4 20.3a1 1 0 0 1-1.4 0L3.7 17a1 1 0 0 1 0-1.4Z",
    "m13 6.5 2 2 M10 9.5l2 2 M7 12.5l2 2",
  ],
};

const icon = computed(() => icons[props.name] ?? icons.grid);
const px = computed(() => props.size || 18);
// Match B2's masters: ~1.25 px lines at small sizes, 1.75 units on the 24 grid above.
const strokeWidth = computed(() => (px.value <= 18 ? Math.round((1.25 * 24 * 100) / px.value) / 100 : 1.75));
</script>
<template>
  <svg
    class="app-icon"
    :data-icon="name"
    :width="px"
    :height="px"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="icon-body" :d="icon[0]" />
    <path v-if="icon[1]" class="icon-accent" :d="icon[1]" stroke="var(--icon-accent, currentColor)" />
  </svg>
</template>
