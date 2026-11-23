<script setup lang="ts">
// Stage item and category forms. The project view runs commands and refreshes the grid.
import { computed, ref } from "vue";
import Dialog from "primevue/dialog";
import ThemedAutocomplete from "./ThemedAutocomplete.vue";
import { request } from "../backend";
import type {
  GridRow,
  MeasurementGridCategory,
  MeasurementTemplate,
  ProjectItemField,
  ProjectItemMode,
  View,
  ViewCommand,
} from "../projectViewTypes";

const props = defineProps<{
  view: View;
  categories?: string[];
  measurementCategories: MeasurementGridCategory[];
  templates: MeasurementTemplate[];
  editableFields: readonly ProjectItemField[];
  selectedItem?: GridRow;
  busy: boolean;
  error: string;
  run: (work: () => Promise<void>) => Promise<boolean>;
  command: ViewCommand;
}>();

const isMeasurement = computed(() => props.view === "measurement");
const formOpen = ref(false);
const formMode = ref<ProjectItemMode>("add");
const form = ref<Record<string, string>>({});
const measurementDestination = ref("");
const templateInfo = computed(() => props.templates.find((template) => template.code === form.value.template));
const categoryOpen = ref(false);
const categoryName = ref("");

/** Stage the selection that opened the form and ask Python for insertion defaults. */
async function showItem(mode: ProjectItemMode, item: GridRow | undefined, ids: string[], child: boolean) {
  formMode.value = mode;
  form.value = {
    code: "",
    description: "",
    unit: "",
    rate: "0",
    qty: "0",
    vat: "0",
    discount: "0",
    category: item?.category || (item?.rowtype === "Category" ? item.description : ""),
    parent: "",
    reference: "",
    template: isMeasurement.value ? "_1_NLBH" : "",
    ...(mode === "duplicate" ? { code: item?.code + "-copy" } : {}),
    ...(mode === "edit"
      ? Object.fromEntries(props.editableFields.map((field) => [field, String(item?.[field] ?? "")]))
      : {}),
  };

  if (isMeasurement.value) {
    measurementDestination.value = "";
  } else if (mode === "add") {
    const ok = await props.run(async () => {
      const defaults = await request<{ code: string; category: string; parent: string }>(
        props.view + ".editor.defaults",
        { ids, child },
      );
      Object.assign(form.value, defaults);
    });
    if (!ok) return;
  }
  formOpen.value = true;
}

async function submit() {
  if (formMode.value === "edit") {
    const item = props.selectedItem;
    if (!item) return;
    const edits = Object.entries(form.value)
      .filter(([field, value]) => isEditableField(field) && value !== String(item[field] ?? ""))
      .map(([field, value]) => ({ id: item.id, field, value }));
    if (!edits.length || (await props.command("edit_many", { edits }))) formOpen.value = false;
    return;
  }

  const operation = isMeasurement.value && formMode.value !== "duplicate" ? "add" : formMode.value;
  const params = isMeasurement.value
    ? {
        template: form.value.template,
        description: form.value.description,
        ...(measurementDestination.value ? { ids: [measurementDestination.value] } : {}),
      }
    : { data: form.value };
  if (await props.command(operation, params)) formOpen.value = false;
}

function isEditableField(field: string): field is ProjectItemField {
  return props.editableFields.some((editableField) => editableField === field);
}

function showCategory() {
  categoryOpen.value = true;
}

async function submitCategory() {
  const description = categoryName.value;
  if (
    await props.command(isMeasurement.value ? "add" : "category_add", {
      description,
    })
  )
    categoryOpen.value = false;
}

defineExpose({ showItem, showCategory });
</script>

<template>
  <Dialog
    v-model:visible="formOpen"
    modal
    :header="formMode === 'duplicate' ? 'Duplicate item' : formMode === 'edit' ? 'Edit item' : 'Add item'"
    class="workspace-dialog resource-dialog"
    ><form @submit.prevent="submit">
      <template v-if="isMeasurement"
        ><label v-if="formMode === 'add'" class="field"
          >Measurement template<select v-model="form.template">
            <optgroup v-for="group in ['General', 'Civil', 'E&M']" :key="group" :label="group">
              <option
                v-for="template in templates.filter((item) => item.group === group)"
                :key="template.code"
                :value="template.code"
              >
                {{ template.label }}
              </option>
            </optgroup></select
          ><small v-if="templateInfo"
            >{{ templateInfo.summary }} {{ templateInfo.note }}<br />Inputs: {{ templateInfo.inputs.join(", ") }} ·
            {{ templateInfo.outputs }} linked {{ templateInfo.outputs === 1 ? "quantity" : "quantities" }}</small
          ></label
        ><label class="field"
          >Category<select v-model="measurementDestination">
            <option value="">At selection</option>
            <option value="measurement:uncategorised">Uncategorised</option>
            <option
              v-for="category in measurementCategories.filter((row) => row.id !== 'measurement:uncategorised')"
              :key="category.id"
              :value="category.id"
            >
              {{ category.description }}
            </option>
          </select></label
        ><label class="field"
          >Description / remarks<textarea data-primary-input autofocus v-model="form.description" rows="3" /></label
      ></template>
      <template v-else
        ><label class="field"
          >New code<input v-model="form.code" aria-label="New code" :required="formMode !== 'add'" /><small
            v-if="formMode === 'add'"
            >Suggested from the current numbering pattern. Edit it, or leave blank to generate a code when
            inserting.</small
          ></label
        ><template v-if="formMode !== 'duplicate'"
          ><label class="field"
            >Description<textarea data-primary-input autofocus v-model="form.description" rows="3" />
          </label>
          <div class="field-pair">
            <label class="field">Unit<input v-model="form.unit" /></label
            ><label class="field">Rate<input v-model="form.rate" required /></label>
          </div>
          <label class="field"
            >Category<ThemedAutocomplete
              v-model="form.category"
              label="Category"
              :suggestions="categories || []"
              :disabled="busy" /></label
          ><template v-if="view === 'schedule'"
            ><label class="field">Quantity<input v-model="form.qty" /></label
            ><label class="field">Parent code (optional)<input v-model="form.parent" /></label
          ></template>
          <div v-else class="field-pair">
            <label class="field">Tax %<input v-model="form.vat" /></label
            ><label class="field">Discount %<input v-model="form.discount" /></label></div></template
      ></template>
      <div v-if="error" class="dialog-error">{{ error }}</div>
      <div class="dialog-footer">
        <button type="button" class="button secondary" @click="formOpen = false">Cancel</button
        ><button class="button primary" :disabled="busy">
          {{ formMode === "duplicate" ? "Duplicate" : formMode === "edit" ? "Save item" : "Add item" }}
        </button>
      </div>
    </form></Dialog
  >
  <Dialog v-model:visible="categoryOpen" modal header="Add category" class="workspace-dialog file-dialog"
    ><label class="field">Category name<input v-model="categoryName" data-primary-input autofocus /></label>
    <div class="dialog-footer">
      <button class="button primary" :disabled="busy || !categoryName" @click="submitCategory">Add category</button>
    </div></Dialog
  >
</template>
