<script setup lang="ts">
import Dialog from "primevue/dialog";
import { version } from "../../package.json";
import license from "../../../LICENSE?raw";
const manual = defineModel<boolean>("manual", { default: false });
const about = defineModel<boolean>("about", { default: false });
</script>
<template>
  <Dialog v-model:visible="manual" modal header="Application manual" class="workspace-dialog file-dialog application-help">
    <p>GEstimator prepares civil and electrical estimates, rate analyses and detailed measurements. Projects are saved as .eproj files.</p>
    <section><h3>Projects and saving</h3><p>Use the application menu to create or open a project. Editing takes place in an isolated working copy. Save updates the source project with backups; Save project copy writes a separate file. Recent projects and recovery checkpoints are available in Open project. Unsaved changes prompt you before switching projects or closing.</p></section>
    <section><h3>Schedule and resources</h3><p>The Schedule holds item codes, descriptions, units, stored rates and quantities. Resources hold prices, tax, discount and references shared by analyses. Double-click an editable cell; Enter accepts, Tab moves to the next cell, and Escape cancels the cell edit. Use the ribbons to add, duplicate, arrange or remove items and categories. Search and category filters narrow the visible rows. The estimate total covers the whole project.</p></section>
    <section><h3>Rate analysis</h3><p>Open a schedule item's analysis, then add resource groups and calculation rows. Subtotal establishes a base, Weight adds a fraction of that base, Multiply replaces the running total from the base, and Round applies rounding. Row order affects calculation. Apply analysis accepts the draft into the working project and updates dependent rates. Apply or Discard returns to Schedule. Discard analysis abandons pending edits. Save retains applied changes on disk.</p></section>
    <section><h3>Measurements</h3><p>Add a measurement using a General, Civil or E&amp;M template, then open its records. Enter dimensions or arithmetic expressions; derived cells and serial numbers are read-only. Properties controls template constants, captions and schedule links. The total covers all records across pages. Apply records accepts records, links and properties together as one project undo step. Apply or Discard returns to Measurements. Discard records abandons the draft. Refresh schedule quantities from measurements when ready.</p></section>
    <section><h3>Databases and spreadsheets</h3><p>Attach read-only .eproj databases from the Databases tab, then choose items or resources to insert. Source databases stay unchanged. Excel import previews selected worksheets and ranges before applying changes. Export workbook creates the original Schedule, Resources, DOM, Res Usage and Analysis sheets. Export analysis includes the loaded analysis draft.</p></section>
    <section><h3>Settings and assistance</h3><p>Program Settings controls appearance, table typography, number formatting and reusable analysis templates. Currency code selects the optional display symbol without converting prices. Project Settings applies to the current estimate. Keyboard shortcuts remain available separately in the application menu.</p><p>Illustrated user manual with a worked example: <a href="https://manuvarkey.github.io/GEstimator/manual.html" target="_blank" rel="noopener noreferrer">GEstimator user manual</a>.</p></section>
  </Dialog>
  <Dialog v-model:visible="about" modal header="About GEstimator" class="workspace-dialog file-dialog application-help">
    <h2>GEstimator</h2><p>Version {{ version }}</p>
    <p>Civil and electrical estimation with detailed rate analysis.</p>
    <p>Copyright © 2017 Manu Varkey. Original application by Manu Varkey, Central Public Works Department. Documentation by Anupama Varghese T and A. Ahila Subash.</p>
    <p>Licensed under the GNU General Public License, version 3. See the full licence below for terms.</p>
    <p><a href="https://manuvarkey.github.io/GEstimator/" target="_blank" rel="noopener noreferrer">Documentation</a> · <a href="https://github.com/manuvarkey/GEstimator" target="_blank" rel="noopener noreferrer">Source code</a></p>
    <details><summary>GNU General Public License</summary><pre>{{ license }}</pre></details>
  </Dialog>
</template>
