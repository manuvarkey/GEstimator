<script setup lang="ts">
defineProps<{ name: string; size?: number }>();
// Semantic silhouettes with a neutral body and a restrained accent detail.
// OpenAEC-style two-tone treatment; paths remain local to GEstimator.
const clipboardIcons = ["copy", "paste"];
const paths: Record<string, string> = {
  blank: "",
  forward: "M4 12h16 M14 6l6 6-6 6",
  back: "M20 12H4 M10 6l-6 6 6 6",
  database: "M4 6a8 3 0 0 0 16 0 8 3 0 0 0-16 0 M4 6v12a8 3 0 0 0 16 0V6 M4 12a8 3 0 0 0 16 0",
  folder:
    "M3 7V5a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z M3 9h18",
  save: "M5 3h12l4 4v14H3V3h2Z M7 3v6h10V3 M7 21v-8h10v8",
  grid: "M3 3h18v18H3Z M3 9h18 M3 15h18 M9 3v18",
  library: "M4 4h4v17H4Z M10 4h4v17h-4Z M16 5l4-1 3 16-4 1Z",
  plus: "M12 5v14 M5 12h14",
  child: "M5 3v9h14 M15 8l4 4-4 4 M5 18v3",
  search: "M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z",
  undo: "M9 4 3 10l6 6 M3 10h10a7 7 0 0 1 7 9",
  redo: "m15 4 6 6-6 6 M21 10H11a7 7 0 0 0-7 9",
  copy: "M8 8H22V22H8ZM10 10V20H20V10ZM2 2H16V6H14V4H4V14H6V16H2Z",
  trash: "M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7",
  up: "m6 14 6-6 6 6",
  down: "m6 10 6 6 6-6",
  chevron: "m9 5 7 7-7 7",
  close: "m6 6 12 12 M6 18 18 6",
  panel: "M3 4h18v16H3Z M15 4v16",
  "panel-left": "M3 4h18v16H3Z M9 4v16",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1 1 M18 18l1 1 M5 19l1-1 M18 6l1-1",
  moon: "M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z",
  help: "M12 17h.01 M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z",
  check: "m5 12 4 4L19 6",
  group: "M4 6h16 M4 12h10 M4 18h16",
  sum: "M18 4H6l7 8-7 8h12",
  percent:
    "M5 19 19 5 M8 6a2 2 0 1 0-4 0 2 2 0 0 0 4 0 M20 18a2 2 0 1 0-4 0 2 2 0 0 0 4 0",
  multiply: "m6 6 12 12 M6 18 18 6",
  round: "M6 5H3v14h3 M18 5h3v14h-3 M8 12h8",
  resource: "m12 3 9 5v9l-9 5-9-5V8Z M3 8l9 5 9-5 M12 13v9",
  paste: "M7 2H17V5H21V22H3V5H7ZM9 4V6H15V4ZM5 7V20H19V7H17V8H7V7Z",
  dots: "M5 12h.01 M12 12h.01 M19 12h.01",
  collapse: "m8 9 4-4 4 4 M8 15l4 4 4-4",
  expand: "m8 5 4 4 4-4 M8 19l4-4 4 4",
  settings: "M4 7h16 M4 17h16 M8 4v6 M16 14v6",
  file: "M5 2h9l5 5v15H5Z M14 2v6h5 M8 13h8 M8 17h6",
  edit: "M4 20h4L19 9l-4-4L4 16v4Z M13 7l4 4",
  category: "M3 5h7l2 2h9v12H3Z M3 10h18",
  duplicate: "M8 8h13v13H8Z M3 16V3h13v3",
  colour: "M12 3a9 9 0 1 0 0 18h2a2 2 0 0 0 0-4h-1a2 2 0 0 1-2-2c0-1.1.9-2 2-2h2a6 6 0 0 0-6-10Z M7 11h.01 M9 7h.01 M14 7h.01 M17 11h.01",
  refresh: "M20 7v5h-5 M4 17v-5h5 M18 12a6 6 0 0 0-10-4L4 12 M6 12a6 6 0 0 0 10 4l4-4",
  chart: "M4 20V10 M10 20V4 M16 20v-7 M22 20H2",
  link: "M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1 M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1",
  import: "M12 3v12 M7 10l5 5 5-5 M4 21h16",
  export: "M12 16V4 M7 9l5-5 5 5 M4 21h16",
  calculate: "M5 3h14v18H5Z M8 7h8 M8 11h2 M14 11h2 M8 15h2 M14 15h2",
  rows: "M4 5h16 M4 9h16 M4 15h16 M4 19h16",
  ruler: "M4 16 16 4l4 4L8 20Z M13 7l4 4 M10 10l2 2 M7 13l2 2",
  attach: "M8 12l5-5a3 3 0 0 1 4 4l-7 7a5 5 0 0 1-7-7l8-8",
  play: "m8 4 12 8-12 8Z",
  stop: "M5 5h14v14H5Z",
  filter: "M3 5h18l-7 8v6l-4 2v-8Z",
  minimize: "M5 17h14",
  maximize: "M5 5h14v14H5Z",
};
const accents: Record<string, string> = {
  database: "M4 12a8 3 0 0 0 16 0", folder: "M3 9h18", save: "M7 3v6h10V3",
  grid: "M3 9h18", library: "M16 5l4-1 3 16-4 1Z", plus: "M12 5v14",
  child: "M15 8l4 4-4 4", search: "M21 21l-5-5", undo: "M9 4 3 10l6 6", redo: "m15 4 6 6-6 6",
  copy: "M10 10H20", paste: "M9 4h6", trash: "M3 6h18", panel: "M15 4v16", "panel-left": "M9 4v16",
  group: "M4 12h10", sum: "M6 4h12", percent: "M5 19 19 5", round: "M8 12h8",
  resource: "M3 8l9 5 9-5", settings: "M8 4v6 M16 14v6", file: "M14 2v6h5", edit: "M13 7l4 4",
  category: "M3 10h18", duplicate: "M8 8h13", colour: "M7 11h.01 M9 7h.01 M14 7h.01 M17 11h.01",
  refresh: "M20 7v5h-5 M4 17v-5h5", chart: "M10 20V4", link: "M10 13a5 5 0 0 0 7 0l2-2",
  import: "M12 3v12 M7 10l5 5 5-5", export: "M12 16V4 M7 9l5-5 5 5", calculate: "M8 7h8",
  rows: "M4 9h16", ruler: "M13 7l4 4 M10 10l2 2 M7 13l2 2", attach: "M8 12l5-5a3 3 0 0 1 4 4",
  filter: "M3 5h18", help: "M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5",
};
</script>
<template>
  <svg
    class="app-icon"
    :data-icon="name"
    :width="size || 18"
    :height="size || 18"
    viewBox="0 0 24 24"
    :fill="clipboardIcons.includes(name) ? 'currentColor' : 'none'"
    :stroke="clipboardIcons.includes(name) ? 'none' : 'currentColor'"
    fill-rule="evenodd"
    :shape-rendering="clipboardIcons.includes(name) ? 'crispEdges' : undefined"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="icon-body" :d="paths[name] ?? paths.grid" />
    <path v-if="accents[name]" class="icon-accent" :d="accents[name]" fill="none" stroke="var(--icon-accent, currentColor)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>
