<script setup lang="ts">
/** Use the application's installed-font inventory without changing interface typography. */
import { computed, onMounted, ref } from "vue";
import { request } from "../backend";
import type { ReportSpecification } from "../reportTypes";

const specification = defineModel<ReportSpecification>({ required: true });
const families = ref<string[]>([]);
const loading = ref(true);
const unavailable = ref(false);
const selected = computed(() => specification.value.font_family ?? "");
const options = computed(() =>
  selected.value && !families.value.includes(selected.value) ? [selected.value, ...families.value] : families.value,
);
const scale = computed({
  get: () => Math.round((specification.value.font_scale ?? 1) * 100),
  set: (value: number) => {
    specification.value.font_scale = value / 100;
  },
});
onMounted(async () => {
  try {
    families.value = await request<string[]>("program.fonts");
    unavailable.value = !families.value.length;
  } catch {
    unavailable.value = true;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="report-appearance">
    <p class="field-hint">A4 pages · 20 mm margins on all sides</p>
    <label
      >Report font
      <select aria-label="Report font" v-model="specification.font_family" :disabled="loading">
        <option value="">Default (bundled Iosevka)</option>
        <option v-for="family in options" :key="family" :value="family">
          {{ family
          }}{{ family === "Iosevka" ? " (bundled)" : !families.includes(family) ? " (saved font unavailable)" : "" }}
        </option>
      </select>
    </label>
    <label>Font scale (%)<input v-model.number="scale" type="number" min="60" max="200" step="5" /></label>
    <p v-if="loading" role="status" class="field-hint">Loading installed fonts…</p>
    <p v-else-if="unavailable" class="field-hint">
      The system font list is unavailable. Default and saved fonts remain available.
    </p>
    <p v-else class="field-hint">
      Fonts apply to preview and exports. Another computer may substitute an unavailable font.
    </p>
  </div>
</template>

<style scoped>
label {
  display: grid;
  gap: 4px;
  margin-block: 12px;
}
.field-hint {
  color: var(--muted);
  font-size: var(--text-size-small);
}
</style>
