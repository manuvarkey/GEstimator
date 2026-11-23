<script setup lang="ts">
// Presents and edits one selected analysis row using the workspace's shared commands.
import type { AnalysisRow, RowKind } from "../backend";
import { formatMoney } from "../numberFormatting";
import AppIcon from "./AppIcon.vue";

type InspectorField = "code" | "description" | "value" | "unit" | "rate" | "vat" | "discount";

const props = defineProps<{
  visible: boolean;
  selection?: AnalysisRow;
  multipleSelected: boolean;
  busy: boolean;
}>();
const emit = defineEmits<{
  edit: [row: AnalysisRow, field: InspectorField, value: string];
  move: [delta: -1 | 1];
  delete: [];
  hide: [];
  shortcuts: [];
}>();

const selectionHints: Record<RowKind, string> = {
  Group: "Organize resources into a calculation group.",
  GroupTotal: "Total of the group's resources.",
  Resource: "Definition changes apply to every use of this resource when saved.",
  Subtotal: "Sets the base for subsequent weighted additions.",
  Weight: "Adds a fraction of the latest group or subtotal base.",
  Multiply: "Replaces the total with the last base multiplied by a factor.",
  Round: "Rounds the cumulative total using the existing currency rules.",
};

function editField(event: Event, field: InspectorField) {
  if (props.selection) {
    const control = event.currentTarget as HTMLInputElement | HTMLTextAreaElement;
    emit("edit", props.selection, field, control.value);
  }
}
</script>

<template>
  <aside v-show="visible" class="inspector">
    <div class="panel-heading">
      <span>INSPECTOR</span
      ><button class="icon-button" aria-label="Hide inspector" @click="emit('hide')">
        <AppIcon name="close" :size="15" />
      </button>
    </div>
    <div v-if="selection" class="inspector-body" :key="selection.id">
      <span class="row-badge" :class="'kind-' + selection.kind.toLowerCase()">{{ selection.kind }}</span>
      <h2>
        {{ selection.code || selection.description || selection.kind }}
      </h2>
      <p class="inspector-hint">{{ selectionHints[selection.kind] }}</p>
      <label v-if="selection.kind === 'Group' || selection.kind === 'Resource'" class="field"
        >{{ selection.kind === "Group" ? "Group code" : "Resource code (replace entry)"
        }}<input :value="selection.code" :disabled="busy" @change="editField($event, 'code')"
      /></label>
      <label class="field"
        >Description<textarea
          :value="selection.description"
          :disabled="busy"
          rows="4"
          @change="editField($event, 'description')"
        /></label
      ><template v-if="!['Group', 'Subtotal'].includes(selection.kind)"
        ><label class="field"
          >{{ selection.kind === "Resource" ? "Quantity" : selection.kind === "Round" ? "Rounding places" : "Factor"
          }}<input
            :value="selection.value"
            :disabled="busy"
            inputmode="decimal"
            @change="editField($event, 'value')" /></label></template
      ><template v-if="selection.kind === 'Resource'"
        ><div class="field-pair">
          <label class="field"
            >Unit<input :value="selection.unit" :disabled="busy" @change="editField($event, 'unit')" /></label
          ><label class="field"
            >Base rate<input
              :value="selection.rate"
              :disabled="busy"
              inputmode="decimal"
              @change="editField($event, 'rate')"
          /></label>
        </div>
        <div class="field-pair">
          <label class="field"
            >Tax %<input
              :value="selection.vat"
              :disabled="busy"
              inputmode="decimal"
              @change="editField($event, 'vat')" /></label
          ><label class="field"
            >Discount %<input
              :value="selection.discount"
              :disabled="busy"
              inputmode="decimal"
              @change="editField($event, 'discount')"
          /></label>
        </div>
        <div class="inspector-result">
          <span>Effective rate</span><strong>{{ formatMoney(selection.effective_rate) }}</strong>
        </div></template
      >
      <div class="inspector-result">
        <span>Calculated amount</span><strong>{{ formatMoney(selection.amount) }}</strong>
      </div>
      <div class="inspector-actions">
        <button class="button secondary" :disabled="busy" @click="emit('move', -1)">
          <AppIcon name="up" :size="15" />Move up</button
        ><button class="button secondary" :disabled="busy" @click="emit('move', 1)">
          <AppIcon name="down" :size="15" />Move down
        </button>
      </div>
      <button class="button danger full-width" :disabled="busy" @click="emit('delete')">
        <AppIcon name="trash" :size="15" />Delete row
      </button>
    </div>
    <div v-else class="inspector-empty">
      <span class="inspector-empty-icon"><AppIcon name="panel" :size="28" /></span>
      <h3>
        {{ multipleSelected ? "Multiple rows selected" : "A closer look" }}
      </h3>
      <p>
        {{
          multipleSelected
            ? "Use the ribbon to copy, duplicate or delete your selection."
            : "Select a row to edit its properties and inspect calculated values."
        }}
      </p>
      <div class="inspector-tip">
        <AppIcon name="help" :size="17" /><span>Use Ctrl / ⌘ + click to select multiple rows.</span>
      </div>
    </div>
    <div class="inspector-bottom">
      <span class="eyebrow">CALCULATION NOTES</span>
      <p>Weighted additions use the latest group or subtotal as their base. Totals follow the row sequence.</p>
      <button class="text-button" @click="emit('shortcuts')">
        Keyboard shortcuts<AppIcon name="chevron" :size="12" />
      </button>
    </div>
  </aside>
</template>
