import { ref, type ComputedRef, type Ref } from "vue";
import { request } from "./backend";
import type { GridRow, GridState, MeasurementDetail, ViewCommand } from "./projectViewTypes";

interface PropertiesContext {
  state: Ref<GridState | undefined>;
  one: ComputedRef<GridRow | undefined>;
  error: Ref<string>;
  activeMeasurement: Ref<string | undefined>;
  command: ViewCommand;
  loadDetail: () => Promise<void>;
}

/** Staged measurement/category properties and their schedule-link picker.
 * Saving delegates validation and draft/transaction ownership to the shared command.
 */
export function useMeasurementProperties(context: PropertiesContext) {
  const { state, one, error, activeMeasurement, command, loadDetail } = context;
  const propertiesOpen = ref(false);
  const propertiesCategory = ref(false);
  const propertiesDetail = ref<MeasurementDetail | null>();
  const properties = ref<{
    description: string;
    links: { code: string; remark: string; label: string }[];
    user_data: string[];
  }>({ description: "", links: [], user_data: [] });
  const propertiesRevision = ref(0);
  const pickerOpen = ref(false);
  const pickerSlot = ref(0);
  const pickerQuery = ref("");
  const pickerPage = ref(0);
  const pickerItems = ref<{ code: string; description: string; unit: string | null }[]>([]);
  const pickerBusy = ref(false);
  const pickerError = ref("");

  async function showProperties() {
    // Step 1: load the selected item's detail; selection may change while it is in flight.
    if (!one.value || !state.value || one.value.id === "measurement:uncategorised") return;
    const identity = one.value.id;
    if (one.value.type !== "Heading" && one.value.rowtype !== "Category" && state.value.detail?.id !== identity)
      await loadDetail();
    if (one.value?.id !== identity) return;
    // Step 2: stage a separate form snapshot and retain the revision for stale-write checks.
    const detail = one.value.rowtype === "Category" ? undefined : state.value.detail;
    propertiesCategory.value = one.value.rowtype === "Category";
    propertiesDetail.value = detail;
    properties.value = {
      description: one.value.description,
      links: detail?.links.map((link) => ({ code: link.code, remark: link.remark, label: link.label })) || [],
      user_data: detail?.user_data.map((field) => field.value) || [],
    };
    propertiesRevision.value = state.value.revision;
    error.value = "";
    propertiesOpen.value = true;
  }

  async function saveProperties() {
    if (await command("properties", { id: one.value?.id, revision: propertiesRevision.value, ...properties.value }))
      propertiesOpen.value = false;
  }

  async function searchLinks() {
    pickerBusy.value = true;
    pickerError.value = "";
    try {
      pickerItems.value = await request("schedule.list", { query: pickerQuery.value, offset: pickerPage.value * 100 });
    } catch (reason) {
      pickerError.value = String(reason);
    } finally {
      pickerBusy.value = false;
    }
  }

  async function showLinkPicker(slot: number) {
    pickerSlot.value = slot;
    pickerQuery.value = "";
    pickerPage.value = 0;
    pickerOpen.value = true;
    await searchLinks();
  }

  async function chooseLink(code: string) {
    if (propertiesOpen.value) properties.value.links[pickerSlot.value]!.code = code;
    else if (
      !(await command("link", {
        id: activeMeasurement.value,
        slot: pickerSlot.value,
        code,
        remark: state.value?.detail!.links[pickerSlot.value].remark || "",
      }))
    )
      return;
    pickerOpen.value = false;
  }

  return {
    propertiesOpen,
    propertiesCategory,
    propertiesDetail,
    properties,
    pickerOpen,
    pickerQuery,
    pickerPage,
    pickerItems,
    pickerBusy,
    pickerError,
    showProperties,
    saveProperties,
    searchLinks,
    showLinkPicker,
    chooseLink,
  };
}
