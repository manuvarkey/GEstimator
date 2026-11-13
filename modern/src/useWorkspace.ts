import { computed, ref } from "vue";
import {
  request,
  type AnalysisRow,
  type AnalysisState,
  type LibraryItem,
} from "./backend";

export function useWorkspace() {
  const state = ref<AnalysisState>();
  const busy = ref(false);
  const error = ref("");
  const status = ref("Connecting to calculation engine…");
  const connected = ref(false);
  const selected = ref<AnalysisRow[]>([]);
  const schedule = ref<LibraryItem[]>([]);
  const resources = ref<LibraryItem[]>([]);
  const scheduleQuery = ref("");
  const resourceQuery = ref("");
  const resourceSource = ref("");
  const schedulePage = ref(0);
  const resourcePage = ref(0);
  const clipboardReady = ref(false);
  const projectName = computed(
    () =>
      state.value?.project_name ||
      state.value?.source_path
        ?.split(/[\\/]/)
        .pop()
        ?.replace(/\.eproj$/i, "") ||
      "Untitled workspace",
  );
  const resourceCount = computed(
    () =>
      state.value?.rows.reduce(
        (sum, row) => sum + (row._children?.length || 0),
        0,
      ) || 0,
  );
  const groups = computed(
    () => state.value?.rows.filter((row) => row.kind === "Group") || [],
  );
  const selection = computed(() =>
    selected.value.length === 1 ? selected.value[0] : undefined,
  );
  const destinationGroup = computed(() => {
    const row = selected.value[0];
    return groups.value.find(
      (group) =>
        group.id === row?.id ||
        group._children?.some((child) => child.id === row?.id),
    );
  });
  async function run(
    work: () => Promise<void>,
    message = "Working…",
  ): Promise<boolean> {
    if (busy.value) return false;
    busy.value = true;
    error.value = "";
    status.value = message;
    try {
      await work();
      status.value = "All calculations up to date";
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
      status.value = "Operation failed";
      return false;
    } finally {
      busy.value = false;
    }
  }
  async function refresh(next?: AnalysisState) {
    const value = next ?? (await request<AnalysisState>("state"));
    const rows = value.rows.flatMap((row) => [row, ...(row._children || [])]);
    selected.value = selected.value
      .map((old) => rows.find((row) => row.id === old.id))
      .filter((r): r is AnalysisRow => !!r);
    state.value = value;
  }
  async function reconnect() {
    await run(async () => {
      await refresh();
      connected.value = true;
    }, "Connecting to engine…");
  }
  async function command(method: string, params: Record<string, unknown> = {}) {
    return run(async () => {
      try {
        await refresh(
          await request<AnalysisState>(method, {
            revision: state.value?.revision,
            ids: selected.value.map((row) => row.id),
            id: selected.value[0]?.id,
            ...params,
          }),
        );
        if (method === "copy" || method === "duplicate")
          clipboardReady.value = true;
      } catch (e) {
        await refresh().catch(() => {
          connected.value = false;
        });
        throw e;
      }
    }, "Updating analysis…");
  }
  async function searchSchedule(page = 0) {
    await run(async () => {
      schedule.value = await request("schedule.list", {
        query: scheduleQuery.value,
        offset: page * 100,
      });
      schedulePage.value = page;
    }, "Finding schedule items…");
  }
  async function searchResources(page = 0) {
    await run(async () => {
      resources.value = await request("resources.search", {
        query: resourceQuery.value,
        source: resourceSource.value,
        offset: page * 100,
      });
      resourcePage.value = page;
    }, "Finding resources…");
  }
  async function openProject(path: string, discard = false, recovery = false) {
    return run(async () => {
      if (recovery) await request("recovery.open", { id: path, discard });
      else await request("project.open", { path, discard });
      await refresh();
      scheduleQuery.value = "";
      resourceQuery.value = "";
      resourceSource.value = "";
      schedulePage.value = 0;
      resourcePage.value = 0;
      schedule.value = await request("schedule.list");
      resources.value = [];
      selected.value = [];
      clipboardReady.value = false;
    }, "Opening project…");
  }
  async function load(code: string, discard = false) {
    return run(async () => {
      await refresh(await request("analysis.load", { code, discard }));
      selected.value = [];
    }, "Loading rate analysis…");
  }
  async function saveCopy(path: string) {
    const saved = await run(async () => {
      await request("project.save_copy", { path });
      await refresh();
    }, "Saving project copy…");
    if (saved) status.value = `Saved ${path}`;
    return saved;
  }
  async function saveProject() {
    let path = "";
    const saved = await run(async () => {
      path = (await request<{ saved: string }>("project.save")).saved;
      await refresh();
    }, "Saving project…");
    if (saved) status.value = `Saved ${path}`;
    return saved;
  }
  return {
    state,
    busy,
    error,
    status,
    connected,
    selected,
    schedule,
    resources,
    scheduleQuery,
    resourceQuery,
    resourceSource,
    schedulePage,
    resourcePage,
    clipboardReady,
    projectName,
    resourceCount,
    groups,
    selection,
    destinationGroup,
    run,
    refresh,
    reconnect,
    command,
    searchSchedule,
    searchResources,
    openProject,
    load,
    saveCopy,
    saveProject,
  };
}
