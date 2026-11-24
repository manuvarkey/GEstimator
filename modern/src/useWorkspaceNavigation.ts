import { nextTick, onBeforeUnmount, ref, watch, type Ref } from "vue";
import type { AnalysisState } from "./backend";
import { updateDocument } from "./documents";
import { forgetTabState, recallTabState, rememberTabState } from "./tabMemory";

export type WorkspaceView = "analysis" | "schedule" | "resources" | "measurement";
export type ProjectView = Exclude<WorkspaceView, "analysis">;
export type RibbonTab = WorkspaceView | "databases" | "mcp";
type NavigationEntry = { view: WorkspaceView; tab: RibbonTab; code?: string; measurement?: string };
type WorkspaceMemory = {
  tab: RibbonTab;
  measurementEntry?: string;
  navigation: NavigationEntry[];
  navigationIndex: number;
  inspector: boolean;
};
interface NavigationContext {
  documentId: string;
  initialView: WorkspaceView;
  state: Ref<AnalysisState | undefined>;
  projectSession: Ref<number>;
  uiBusy: Readonly<Ref<boolean>>;
  mcpEnabled: () => boolean;
  guard: (action: (discard: boolean) => Promise<unknown>) => Promise<void>;
  load: (code: string, discard?: boolean) => Promise<boolean>;
  focusAnalysis: () => Promise<void>;
  focusSchedule: (code?: string) => Promise<void>;
}

/** Document-local navigation and memory. The shell supplies the one unsaved-work guard. */
export function useWorkspaceNavigation(context: NavigationContext) {
  const { documentId, state, projectSession } = context;
  const remembered = recallTabState<WorkspaceMemory>("workspace");
  const activeView = ref<WorkspaceView>(context.initialView);
  const activeTab = ref<RibbonTab>(remembered?.tab ?? context.initialView);
  const measurementEntry = ref(remembered?.measurementEntry);
  const inspector = ref(remembered?.inspector ?? true);
  const visitedViews = ref<ProjectView[]>([]);

  watch(context.mcpEnabled, (enabled) => {
    if (!enabled && activeTab.value === "mcp") activeTab.value = activeView.value;
  });
  watch(activeView, (view) => updateDocument(documentId, { view }));
  watch(
    activeView,
    (view) => {
      if (view !== "analysis" && !visitedViews.value.includes(view)) visitedViews.value.push(view);
    },
    { immediate: true },
  );
  watch(projectSession, () => {
    visitedViews.value = activeView.value === "analysis" ? [] : [activeView.value];
  });

  const navigation = ref<NavigationEntry[]>(remembered?.navigation ?? []);
  const navigationIndex = ref(remembered?.navigationIndex ?? -1);
  let restoringNavigation = false;
  watch(
    [activeView, activeTab, measurementEntry, () => (activeView.value === "analysis" ? state.value?.code : undefined)],
    () => {
      if (restoringNavigation) return;
      const entry: NavigationEntry = {
        view: activeView.value,
        tab: activeTab.value,
        code: activeView.value === "analysis" ? state.value?.code : undefined,
        measurement: activeView.value === "measurement" ? measurementEntry.value : undefined,
      };
      if (JSON.stringify(navigation.value[navigationIndex.value]) === JSON.stringify(entry)) return;
      navigation.value.splice(navigationIndex.value + 1);
      navigation.value.push(entry);
      navigationIndex.value = navigation.value.length - 1;
    },
    { immediate: true, flush: "post" },
  );
  watch(projectSession, () => {
    forgetTabState(documentId);
    navigation.value = [{ view: activeView.value, tab: activeTab.value }];
    navigationIndex.value = 0;
    measurementEntry.value = undefined;
  });

  async function travelNavigation(delta: number) {
    const index = navigationIndex.value + delta;
    const entry = navigation.value[index];
    if (!entry || context.uiBusy.value) return;
    await context.guard(async (discard) => {
      // Step 1: resolve the target analysis through the existing draft guard/load path.
      restoringNavigation = true;
      try {
        if (entry.view === "analysis" && entry.code && entry.code !== state.value?.code) {
          if (!(await context.load(entry.code, discard))) return;
        } else if (discard && state.value?.project) await context.load(state.value.code, true);
        // Step 2: restore one history entry without recording another navigation step.
        activeView.value = entry.view;
        activeTab.value = entry.tab;
        measurementEntry.value = entry.measurement;
        navigationIndex.value = index;
        await nextTick();
      } finally {
        restoringNavigation = false;
      }
    });
  }

  async function returnToSchedule() {
    const code = state.value?.code;
    await context.guard(async (discard) => {
      if (discard && state.value?.project) await context.load(state.value.code, true);
      activeView.value = "schedule";
      activeTab.value = "schedule";
      await nextTick();
      await context.focusSchedule(code);
    });
  }

  async function switchView(view: RibbonTab) {
    if (view === "analysis" && state.value?.dirty) {
      activeView.value = "analysis";
      activeTab.value = "analysis";
      return;
    }
    if (view === "databases" || view === "mcp" || view === activeView.value) {
      activeTab.value = view;
      return;
    }
    await context.guard(async (discard) => {
      if (discard && state.value?.project) await context.load(state.value.code, true);
      activeView.value = view;
      activeTab.value = view;
    });
  }

  async function loadAnalysis(code: string) {
    await context.guard(async (discard) => {
      if (await context.load(code, discard)) {
        const alreadyActive = activeView.value === "analysis";
        activeView.value = "analysis";
        activeTab.value = "analysis";
        if (alreadyActive) await context.focusAnalysis();
      }
    });
  }

  async function changeMeasurementEntry(id: string | undefined) {
    await context.guard(async () => {
      measurementEntry.value = id;
    });
  }

  onBeforeUnmount(() => {
    rememberTabState(documentId, "workspace", {
      tab: activeTab.value,
      measurementEntry: measurementEntry.value,
      navigation: navigation.value,
      navigationIndex: navigationIndex.value,
      inspector: inspector.value,
    } satisfies WorkspaceMemory);
  });

  return {
    activeView,
    activeTab,
    measurementEntry,
    inspector,
    visitedViews,
    navigation,
    navigationIndex,
    travelNavigation,
    returnToSchedule,
    switchView,
    loadAnalysis,
    changeMeasurementEntry,
  };
}
