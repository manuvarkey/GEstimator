import { onBeforeUnmount, watch, type Ref } from "vue";
import { request } from "./backend";
import { initializeMCP, mcpStatus, refreshMCP } from "./mcp";
import type { useWorkspace } from "./useWorkspace";
import type { RibbonTab } from "./useWorkspaceNavigation";

interface MCPContext {
  workspace: ReturnType<typeof useWorkspace>;
  uiBusy: Readonly<Ref<boolean>>;
  activeTab: Ref<RibbonTab>;
  reloadProjectView: () => Promise<unknown>;
}

/** Poll agent changes for one mounted workspace while preserving active human inputs. */
export function useWorkspaceMCP(context: MCPContext) {
  const w = context.workspace;
  let observedChange = 0;
  let observedProject = 0;
  let poll: ReturnType<typeof setInterval> | undefined;

  watch(context.activeTab, (tab) => {
    if (tab === "mcp") void refreshMCP();
  });

  async function synchronize() {
    // Step 1: defer refresh while a human is editing or a dialog owns their input.
    if (
      !mcpStatus.value ||
      (!mcpStatus.value.running && mcpStatus.value.change_seq === observedChange) ||
      context.uiBusy.value ||
      document.querySelector('.tabulator-editing,textarea.measurement-entry-title,[role="dialog"]')
    )
      return;
    if (!(await refreshMCP())) return;
    if (mcpStatus.value.change_seq === observedChange) return;
    await w.run(async () => {
      // Step 2: a replaced project invalidates the old project's searches and selections.
      if (mcpStatus.value!.project_epoch !== observedProject) {
        w.projectSession.value++;
        w.selected.value = [];
        w.scheduleQuery.value = w.resourceQuery.value = w.resourceSource.value = "";
        w.schedulePage.value = w.resourcePage.value = 0;
      }
      await w.refresh();
      await context.reloadProjectView();
      if (w.state.value?.project_open) {
        w.schedule.value = await request("schedule.list", {
          query: w.scheduleQuery.value,
          offset: w.schedulePage.value * 100,
        });
        w.resources.value = await request("resources.search", {
          query: w.resourceQuery.value,
          offset: w.resourcePage.value * 100,
          source: w.resourceSource.value,
        });
      }
      observedChange = mcpStatus.value!.change_seq;
      observedProject = mcpStatus.value!.project_epoch;
    }, "Updated by MCP");
  }

  async function start() {
    await initializeMCP();
    // A remounted tab already reflects earlier agent writes; do not replay them as a new project.
    if (mcpStatus.value) {
      observedChange = mcpStatus.value.change_seq;
      observedProject = mcpStatus.value.project_epoch;
    }
    if (poll) clearInterval(poll);
    poll = setInterval(() => {
      void synchronize();
    }, 1500);
  }

  onBeforeUnmount(() => {
    if (poll) clearInterval(poll);
  });
  return { start };
}
