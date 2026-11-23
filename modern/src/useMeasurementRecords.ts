import { computed, nextTick, ref, watch, type Ref } from "vue";
import type { DataTableHandle } from "./dataTableTypes";
import { request } from "./backend";
import { measurementRecordColumns } from "./measurementColumns";
import type {
  GridRow,
  GridState,
  MeasurementDetailState,
  MeasurementListState,
  MeasurementRecord,
  RecordViewMemory,
  ViewCommand,
} from "./projectViewTypes";

interface RecordsContext {
  state: Ref<GridState | undefined>;
  busy: Readonly<Ref<boolean>>;
  error: Ref<string>;
  selected: Ref<GridRow[]>;
  selectionIds: Ref<string[] | undefined>;
  entryId: () => string | undefined;
  remembered?: RecordViewMemory;
  command: ViewCommand;
  run: (work: () => Promise<void>) => Promise<boolean>;
  focus: () => Promise<void>;
  changed: () => void;
}

/** Record-page presentation, selection and detail loading for one project view.
 * Commands reuse the view's busy/error boundary; Python owns drafts and history.
 * The parent saves/restores this record page together with its main-table memory.
 */
export function useMeasurementRecords(context: RecordsContext) {
  const { state, busy, error, selected, selectionIds, command, run } = context;
  const selectedRecord = ref<MeasurementRecord>();
  const selectedRecords = ref<MeasurementRecord[]>([]);
  const recordSelectionIds = ref<string[]>();

  // The open measurement's record page, selection and scroll come back with the tab.
  let pendingRecords = context.remembered?.entryId === context.entryId() ? context.remembered : undefined;
  const recordPage = ref(pendingRecords?.page ?? 0);
  const recordCount = ref(10);
  const recordsOpen = ref(false);

  const detailBusy = ref(false);
  let selectionRequest = 0;
  const activeMeasurement = ref<string | undefined>(context.entryId());
  const recordTable = ref<DataTableHandle<MeasurementRecord>>();
  const measurementDescription = ref<HTMLTextAreaElement>();
  const descriptionDraft = ref<string>();
  const fullMeasurementTitle = computed(() =>
    state.value?.detail?.id === context.entryId()
      ? state.value?.detail?.description || "Measurement entry"
      : "Measurement entry",
  );

  async function editMeasurementDescription() {
    const detail = state.value?.detail;
    if (busy.value || !detail || detail.id !== context.entryId()) return;
    descriptionDraft.value = detail.description;
    await nextTick();
    measurementDescription.value?.focus({ preventScroll: true });
  }

  async function finishMeasurementDescription() {
    const value = descriptionDraft.value;
    const detail = state.value?.detail;
    descriptionDraft.value = undefined;
    if (value === undefined || !detail || detail.id !== context.entryId() || value === detail.description) return;
    if (!(await command("edit", { id: detail.id, field: "description", value })) && context.entryId() === detail.id) {
      descriptionDraft.value = value;
      await nextTick();
      measurementDescription.value?.focus({ preventScroll: true });
    }
  }

  watch(
    () => context.entryId(),
    async (identity) => {
      descriptionDraft.value = undefined;
      if (!identity) {
        if (state.value?.measurement_draft) await command("draft.close");
        if (activeMeasurement.value) selectionIds.value = [activeMeasurement.value];
        await context.focus();
        return;
      }
      activeMeasurement.value = identity;
      const row = state.value?.rows.find((row) => row.id === identity);
      if (row) selected.value = [row];
      recordPage.value = 0;
      await loadDetail();
      await context.focus();
    },
  );

  const recordRows = computed(() =>
    (state.value?.detail?.rows || []).map((row, index: number) => ({
      ...row,
      _serial: (state.value?.detail?.offset || 0) + index + 1,
    })),
  );
  const recordColumns = computed(() => measurementRecordColumns(state.value?.detail?.columns || []));

  function syncMeasurementSummary() {
    const detail = state.value?.detail;
    const row = detail && state.value?.rows.find((row) => row.id === detail.id);
    if (row)
      Object.assign(row, {
        description: detail.description,
        count: detail.total_records,
        totals: detail.totals.join(", "),
      });
  }

  async function finishRecords(operation: "apply" | "discard") {
    return run(async () => {
      await request("measurement.draft." + operation, { revision: state.value?.revision });
      let next = await request<MeasurementListState>("measurement.state", {});
      if (operation === "apply" && next.measurement_draft) {
        await request("measurement.draft.close", { revision: next.revision });
        next = await request<MeasurementListState>("measurement.state", {});
      }
      state.value = next;
    });
  }

  async function loadDetail() {
    // Step 1: identify this request so a later selection can supersede its response.
    const token = ++selectionRequest;
    const identity = activeMeasurement.value;
    detailBusy.value = true;
    try {
      let detail = await request<MeasurementDetailState>("measurement.detail", {
        id: identity,
        record_offset: recordPage.value * 100,
      });
      if (context.entryId() && detail.detail && detail.measurement_draft?.id !== identity) {
        // Step 2: open the backend-owned draft before presenting editable records.
        await request("measurement.draft.open", { id: identity, revision: detail.revision });
        detail = await request<MeasurementDetailState>("measurement.detail", {
          id: identity,
          record_offset: recordPage.value * 100,
        });
        context.changed();
      }
      // Step 3: publish only a response for the current item at a current revision.
      if (
        token === selectionRequest &&
        identity === activeMeasurement.value &&
        state.value &&
        detail.revision >= state.value.revision
      ) {
        state.value = { ...state.value, ...detail };
        syncMeasurementSummary();
        if (detail.detail) recordPage.value = detail.detail.offset / 100;
      }
    } catch (reason) {
      if (token === selectionRequest) error.value = String(reason);
    } finally {
      if (token === selectionRequest) detailBusy.value = false;
    }
  }

  async function changeRecordPage(delta: number) {
    recordPage.value = Math.max(0, recordPage.value + delta);
    selectedRecord.value = undefined;
    selectedRecords.value = [];
    recordSelectionIds.value = undefined;
    await loadDetail();
  }

  async function recordEdit(row: MeasurementRecord, field: string, value: string) {
    return command("record_edit", {
      id: activeMeasurement.value,
      record_id: row.id,
      field,
      value,
    });
  }

  async function recordAction(operation: string, delta?: number) {
    await command("record_" + operation, {
      id: activeMeasurement.value,
      record_id: selectedRecord.value?.id,
      record_ids: selectedRecords.value.map((row) => row.id),
      delta,
    });
  }

  /** Restore a remembered record table once its matching detail has loaded. */
  async function restoreRecords() {
    if (pendingRecords && state.value?.detail) {
      const view = pendingRecords;
      pendingRecords = undefined;
      if (context.entryId() === view.entryId) {
        await nextTick();
        await recordTable.value?.restoreViewState(view.table);
      }
    }
  }

  /** Snapshot record selection/scroll under the same document as the main table. */
  function rememberRecords(): RecordViewMemory | undefined {
    const entryId = context.entryId();
    const table = entryId ? recordTable.value?.viewState() : undefined;
    return table && entryId ? { entryId, page: recordPage.value, table } : undefined;
  }

  /** A view change invalidates an outstanding asynchronous detail response. */
  function invalidateDetail() {
    selectionRequest++;
  }

  return {
    selectedRecord,
    selectedRecords,
    recordSelectionIds,
    activeMeasurement,
    recordPage,
    recordCount,
    recordsOpen,
    detailBusy,
    recordTable,
    measurementDescription,
    descriptionDraft,
    fullMeasurementTitle,
    recordRows,
    recordColumns,
    editMeasurementDescription,
    finishMeasurementDescription,
    syncMeasurementSummary,
    finishRecords,
    loadDetail,
    changeRecordPage,
    recordEdit,
    recordAction,
    restoreRecords,
    rememberRecords,
    invalidateDetail,
  };
}
