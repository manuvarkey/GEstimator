<script setup lang="ts">
import { ref, watch } from "vue";
import { request } from "../backend";
import { formatMoney } from "../numberFormatting";
import { highlightScheduleRates } from "../projectGridRows";
import type { GridRow, GridState, RateDiscrepancies } from "../projectViewTypes";

const props = defineProps<{
  revision?: number;
  source: string;
  run: (work: () => Promise<void>) => Promise<boolean>;
}>();
const discrepancy = ref<RateDiscrepancies>();

watch([() => props.revision, () => props.source], () => {
  discrepancy.value = undefined;
});

async function show() {
  await props.run(async () => {
    const result = await request<RateDiscrepancies>("schedule.editor.discrepancies", {});
    if (props.revision === result.revision && !props.source) discrepancy.value = result;
  });
}

function highlight(rows: GridState["rows"]): GridRow[] {
  return discrepancy.value
    ? highlightScheduleRates(
        rows.filter((row) => !!row.rowtype),
        discrepancy.value,
      )
    : rows;
}

defineExpose({ show, highlight });
</script>

<template>
  <div v-if="discrepancy" role="status">
    {{ discrepancy.counts.items }} items · {{ discrepancy.counts.mismatch }} mismatches · ≤0.10:
    {{ discrepancy.counts.small }} · ≤1.00: {{ discrepancy.counts.medium }} · >1.00: {{ discrepancy.counts.large }} ·
    Missing analysis: {{ discrepancy.counts.missing }}
    <button class="button secondary" @click="discrepancy = undefined">Clear highlighting</button>
    <details>
      <summary>Stored / calculated rates</summary>
      <div v-for="row in discrepancy.rows" :key="row.id">
        {{ row.code }}: {{ formatMoney(row.stored) }} /
        {{ row.calculated == null ? "Missing analysis" : formatMoney(row.calculated) }}
      </div>
    </details>
  </div>
</template>
