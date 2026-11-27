<script setup lang="ts">
/** Estimate metadata shared by program defaults and project properties. */
import ReportLogoEditor from "./ReportLogoEditor.vue";
import SignoffEditor from "./SignoffEditor.vue";
import ReportNotesEditor from "./ReportNotesEditor.vue";
import type { EstimateFields } from "../reportTypes";
const values = defineModel<EstimateFields>({ required: true });
const props = defineProps<{ defaults?: EstimateFields; label: string }>();
const fields = [
  { key: "title", label: "Report title" },
  { key: "organization", label: "Organization" },
  { key: "reference", label: "Estimate reference" },
] as const;
function restore(key: keyof EstimateFields) {
  if (props.defaults) values.value = { ...values.value, [key]: JSON.parse(JSON.stringify(props.defaults[key])) };
}
</script>
<template>
  <div class="estimate-fields">
    <div v-for="field in fields" :key="field.key" class="estimate-field">
      <label
        >{{ field.label }}<input v-model="values[field.key]" :aria-label="`${label} ${field.label}`" maxlength="10000"
      /></label>
      <p v-if="defaults" class="field-hint">
        Program default: {{ defaults[field.key] || "(empty)" }}
        <button type="button" :aria-label="`Use program default for ${field.key}`" @click="restore(field.key)">
          Use default
        </button>
      </p>
    </div>
    <div v-if="label === 'Project'" class="estimate-field">
      <label
        >Issue date<input v-model="values.issue_date" :aria-label="label + ' Issue date'" maxlength="10000"
      /></label>
    </div>
    <div class="estimate-field">
      <label
        >Office<textarea
          v-model="values.office"
          :aria-label="label + ' Office'"
          rows="3"
          maxlength="10000"
          data-multiline
        />
      </label>
      <button v-if="defaults" type="button" @click="restore('office')">Use program default office</button>
    </div>
    <ReportLogoEditor v-model="values.logo" :label="label + ' logo'" />
    <button v-if="defaults" type="button" @click="restore('logo')">Use program default logo</button>
    <details>
      <summary>Default block headings</summary>
      <label v-for="(_, kind) in values.headings" :key="kind" class="estimate-field">
        {{ kind.replaceAll("_", " ") }}
        <input
          v-model="values.headings[kind]"
          :aria-label="kind.replaceAll('_', ' ') + ' default heading'"
          maxlength="10000"
        />
      </label>
      <button v-if="defaults" type="button" @click="restore('headings')">Use program default headings</button>
    </details>
    <details>
      <summary>Default notes pages</summary>
      <ReportNotesEditor v-model="values.notes" />
      <button v-if="defaults" type="button" @click="restore('notes')">Use program default notes</button>
    </details>
    <details>
      <summary>Signoff blocks</summary>
      <label
        >Text before signature blocks (Jinja2)
        <textarea v-model="values.signoff_intro" rows="3" maxlength="10000" data-multiline />
      </label>
      <button v-if="defaults" type="button" @click="restore('signoff_intro')">Use program default signoff text</button>
      <SignoffEditor v-model="values.signoff_blocks" :label="`${label} signoff`" />
      <button v-if="defaults" type="button" @click="restore('signoff_blocks')">
        Use program default signoff blocks
      </button>
    </details>
  </div>
</template>
<style scoped>
label {
  display: grid;
  gap: 4px;
}
.estimate-field {
  margin-block: 12px;
}
.field-hint {
  color: var(--muted);
  font-size: var(--text-size-small);
}
summary {
  cursor: pointer;
  padding-block: 8px;
}
</style>
