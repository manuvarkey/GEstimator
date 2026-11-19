<script setup lang="ts">
import { computed } from "vue";

// Spreadsheet-like preview of saved cell values. Click a cell to choose where
// the import starts; Shift+click chooses the last row. The selected range and
// the meaning of each imported column are shown in place.
const props = defineProps<{
  cells: string[][];
  maxRow: number;
  maxColumn: number;
  firstRow: number;
  lastRow?: number;
  firstColumn: number;
  /** Labels for consecutive columns from firstColumn (range imports). */
  labels?: string[];
  /** Labels by 1-based column number (mapped imports). */
  tags?: Record<number, string>;
  /** Header row mode: the first row is a header and data follows to the end. */
  header?: boolean;
}>();
const emit = defineEmits<{ pick: [row: number, column: number, extend: boolean] }>();
const width = computed(() => Math.max(1, ...props.cells.map(row => row.length)));
const columns = computed(() => Array.from({ length: width.value }, (_, index) => index + 1));
function letter(column: number) {
  let text = "";
  for (let value = column; value > 0; value = Math.floor((value - 1) / 26)) text = String.fromCharCode(65 + ((value - 1) % 26)) + text;
  return text;
}
function label(column: number) {
  if (props.tags) return props.tags[column];
  const offset = column - props.firstColumn;
  return props.labels && offset >= 0 && offset < props.labels.length ? props.labels[offset] : undefined;
}
function inRows(row: number) {
  if (props.header) return row > props.firstRow;
  return row >= props.firstRow && (!props.lastRow || row <= props.lastRow);
}
function cellClass(row: number, column: number) {
  const tagged = label(column) !== undefined;
  return {
    "sheet-header-row": props.header && row === props.firstRow,
    "sheet-in-range": tagged && inRows(row),
    "sheet-start": !props.header && row === props.firstRow && column === props.firstColumn,
  };
}
</script>
<template>
  <div class="sheet-grid" role="grid" aria-label="Worksheet preview" :aria-rowcount="maxRow" :aria-colcount="maxColumn">
    <table>
      <thead>
        <tr>
          <th class="sheet-corner" scope="col"></th>
          <th v-for="column in columns" :key="column" scope="col" :class="{ 'sheet-tagged': label(column) !== undefined }">
            <span class="sheet-letter">{{ letter(column) }}</span>
            <span v-if="label(column) !== undefined" class="sheet-tag">{{ label(column) }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(values, index) in cells" :key="index">
          <th scope="row" class="sheet-row-number" :class="{ 'sheet-in-range': inRows(index + 1), 'sheet-header-row': header && index + 1 === firstRow }">{{ index + 1 }}</th>
          <td v-for="column in columns" :key="column" :class="cellClass(index + 1, column)"
            :title="`${letter(column)}${index + 1}${values[column - 1] ? ': ' + values[column - 1] : ''}`"
            @click="emit('pick', index + 1, column, $event.shiftKey)">{{ values[column - 1] }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="maxRow > cells.length" class="sheet-more">Showing the first {{ cells.length }} of {{ maxRow }} rows. Type a later row number to import beyond the preview.</p>
  </div>
</template>
