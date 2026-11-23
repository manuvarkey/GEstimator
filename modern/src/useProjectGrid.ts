/** Data loading, search and incremental refresh for a mounted project grid. */
import { nextTick, ref, watch, type Ref } from "vue";
import { request } from "./backend";
import type { DataTableHandle, TableView } from "./dataTableTypes";
import { useLiveSearch } from "./liveSearch";
import { flattenGridRows } from "./projectGridRows";
import type {
  GridRow,
  GridState,
  MeasurementDetailState,
  MeasurementListState,
  ProjectTableDelta,
  ProjectTablePage,
  View,
} from "./projectViewTypes";

interface ProjectGridContext {
  props: Readonly<{ view: View; projectOpen: boolean; entryId?: string }>;
  state: Ref<GridState | undefined>;
  busy: Readonly<Ref<boolean>>;
  isMeasurement: Readonly<Ref<boolean>>;
  query: Ref<string>;
  categoryFilters: Ref<string[]>;
  source: Readonly<Ref<string>>;
  page: Ref<number>;
  selectionIds: Ref<string[] | undefined>;
  mainTable: Readonly<Ref<DataTableHandle<GridRow> | undefined>>;
  rememberedTable?: TableView;
  activeMeasurement: Readonly<Ref<string | undefined>>;
  recordPage: Ref<number>;
  syncMeasurementSummary: () => void;
  restoreRecords: () => Promise<void>;
  run: (work: () => Promise<void>) => Promise<boolean>;
  changed: () => void;
}

/** Use the view's command boundary and restore its table state after a load. */
export function useProjectGrid(context: ProjectGridContext) {
  const {
    props,
    state,
    busy,
    isMeasurement,
    query,
    categoryFilters,
    source,
    page,
    selectionIds,
    mainTable,
    activeMeasurement,
    recordPage,
    syncMeasurementSummary,
    restoreRecords,
    run,
    changed,
  } = context;
  const libraries = ref<{ id: string; name: string }[]>([]);
  watch(categoryFilters, () => {
    void search();
  });
  let searchedQuery = "";
  const liveSearch = useLiveSearch(
    query,
    () => searchedQuery,
    () => (isMeasurement.value ? Promise.resolve(true) : search()),
  );

  /** Load the current page, or refresh the active measurement record editor. */
  async function refresh(revealId?: string) {
    if (!props.projectOpen) {
      state.value = undefined;
      return;
    }
    if (!isMeasurement.value) libraries.value = await request("library.list");
    const detailOnly = isMeasurement.value && !!props.entryId && !!state.value;
    searchedQuery = query.value;
    const params = {
      query: query.value,
      categories: categoryFilters.value,
      source: source.value,
      offset: page.value * 100,
      id: props.entryId ? activeMeasurement.value : undefined,
      record_offset: recordPage.value * 100,
      reveal_id: revealId,
    };
    if (detailOnly) {
      const detail = await request<MeasurementDetailState>("measurement.detail", params);
      state.value = { ...state.value!, ...detail };
    } else {
      state.value = isMeasurement.value
        ? await request<MeasurementListState>("measurement.state", params)
        : await request<ProjectTablePage>(props.view + ".editor.state", params);
    }
    // Open the requested draft before displaying its authoritative record page.
    if (props.entryId && state.value.detail && state.value.measurement_draft?.id !== props.entryId) {
      await request("measurement.draft.open", { id: props.entryId, revision: state.value.revision });
      Object.assign(
        state.value,
        await request<MeasurementDetailState>("measurement.detail", {
          id: props.entryId,
          record_offset: recordPage.value * 100,
        }),
      );
      changed();
    }
    syncMeasurementSummary();
    if (!isMeasurement.value) {
      const retained = categoryFilters.value.filter((name) => state.value?.categories?.includes(name));
      if (retained.length !== categoryFilters.value.length) {
        categoryFilters.value = retained;
        page.value = 0;
        await refresh(revealId);
        return;
      }
    }
    if (isMeasurement.value && state.value?.detail) recordPage.value = state.value.detail.offset / 100;
    if (!isMeasurement.value) page.value = (state.value?.offset || 0) / 100;
  }

  async function revealCode(code: string) {
    if (isMeasurement.value) return;
    let row = flattenGridRows(state.value?.rows || []).find((row) => row.code === code);
    if (!row) {
      const result = await request<{ id: string }>(props.view + ".editor.locate", { code });
      query.value = "";
      categoryFilters.value = [];
      await refresh(result.id);
      row = flattenGridRows(state.value?.rows || []).find((row) => row.id === result.id);
    }
    if (row) selectionIds.value = [row.id];
  }
  /** Type-ahead on the main table: load the page holding the next match and select it. */
  async function findAcross(text: string, from: string | undefined, direction: 1 | -1) {
    if (isMeasurement.value || busy.value || !props.projectOpen) return false;
    try {
      const next = await request<ProjectTablePage>(props.view + ".editor.state", {
        query: searchedQuery,
        categories: categoryFilters.value,
        source: source.value,
        offset: page.value * 100,
        find: text,
        find_from: from,
        find_direction: direction,
      });
      if (!next.found_id) return false;
      state.value = next;
      page.value = (next.offset || 0) / 100;
      selectionIds.value = [next.found_id];
      return true;
    } catch {
      return false;
    }
  }
  /** Patch visible rows on working schedule/resource pages and reload other views. */
  async function refreshChanges() {
    if (!state.value || isMeasurement.value || source.value) {
      await load();
      return;
    }
    const current = flattenGridRows(state.value.rows);
    const update = async () => {
      const next = await request<ProjectTablePage | ProjectTableDelta>(props.view + ".editor.state", {
        since: state.value!.view_seq,
        visible_ids: current.map((row) => row.id),
        query: query.value,
        categories: categoryFilters.value,
        offset: page.value * 100,
      });
      if (next.delta) {
        for (const update of next.updates) Object.assign(current.find((row) => row.id === update.id) || {}, update);
        Object.assign(state.value!, {
          revision: next.revision,
          view_seq: next.view_seq,
          undo: next.undo,
          redo: next.redo,
          enrichment: next.enrichment,
          grand_total: next.grand_total,
        });
        await mainTable.value?.patchRows(next.updates);
      } else state.value = next;
      await nextTick();
      await mainTable.value?.redraw();
    };
    // A command can refresh within the busy boundary that it already holds.
    if (busy.value) await update();
    else await run(update);
  }

  let pendingView = context.rememberedTable;
  async function load() {
    const result = await run(refresh);
    // The first load with the project open restores the remembered rows and scroll.
    if (pendingView && mainTable.value && state.value) {
      const view = pendingView;
      pendingView = undefined;
      await mainTable.value.restoreViewState(view);
    }
    await restoreRecords();
    return result;
  }
  /** Load the first page of results for the current search and filters. */
  async function search() {
    liveSearch.cancel();
    return goToPage(0);
  }
  async function goToPage(index: number) {
    page.value = index;
    await mainTable.value?.scrollToTop();
    return load();
  }

  return { libraries, refresh, refreshChanges, revealCode, findAcross, load, search, goToPage };
}
