<script setup lang="ts">
// The workspace owns search results, queries and guarded analysis navigation.
import { ref } from "vue";
import type { LibraryItem } from "../backend";
import { formatMoney } from "../numberFormatting";
import { focusResultButton } from "../resultNavigation";
import AppIcon from "./AppIcon.vue";

defineProps<{
  projectName: string;
  projectOpen: boolean;
  activeCode?: string;
  busy: boolean;
  uiBusy: boolean;
  canInsertResource: boolean;
  schedule: readonly LibraryItem[];
  resources: readonly LibraryItem[];
  schedulePage: number;
  resourcePage: number;
}>();
const emit = defineEmits<{
  searchSchedule: [page?: number];
  searchResources: [page?: number];
  loadAnalysis: [code: string];
  insertResource: [code: string];
  openProject: [];
}>();
const scheduleQuery = defineModel<string>("scheduleQuery", { required: true });
const resourceQuery = defineModel<string>("resourceQuery", { required: true });
const explorer = ref<"schedule" | "resources">("schedule");
const results = ref<HTMLElement>();

function navigateResults(event: KeyboardEvent) {
  if (event.isComposing || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (focusResultButton(results.value, event.key)) event.preventDefault();
}
</script>

<template>
  <aside class="explorer">
    <div class="panel-heading"><span>PROJECT EXPLORER</span></div>
    <div class="explorer-project">
      <span class="project-icon"><AppIcon name="folder" :size="20" /></span>
      <div>
        <strong>{{ projectName }}</strong
        ><small>{{ projectOpen ? "Project working copy" : "No project open" }}</small>
      </div>
    </div>
    <div class="explorer-tabs" role="tablist" aria-label="Explorer">
      <button
        role="tab"
        :aria-selected="explorer === 'schedule'"
        :class="{ active: explorer === 'schedule' }"
        @click="explorer = 'schedule'"
      >
        <AppIcon name="grid" :size="15" />Schedule</button
      ><button
        role="tab"
        :aria-selected="explorer === 'resources'"
        :class="{ active: explorer === 'resources' }"
        @click="
          explorer = 'resources';
          if (projectOpen) emit('searchResources');
        "
      >
        <AppIcon name="library" :size="15" />Resources
      </button>
    </div>
    <form
      class="search-field"
      @submit.prevent="explorer === 'schedule' ? emit('searchSchedule') : emit('searchResources')"
    >
      <AppIcon name="search" :size="15" /><input
        v-if="explorer === 'schedule'"
        id="navigator-search"
        v-model="scheduleQuery"
        placeholder="Find schedule items…"
        aria-label="Find schedule items"
        :disabled="!projectOpen"
        @keydown.up.down="navigateResults"
      /><input
        v-else
        id="navigator-search"
        v-model="resourceQuery"
        placeholder="Find resources…"
        aria-label="Find resources"
        :disabled="!projectOpen"
        @keydown.up.down="navigateResults"
      /><button type="submit" class="icon-button" aria-label="Search explorer" :disabled="uiBusy || !projectOpen">
        <AppIcon name="chevron" :size="14" />
      </button>
    </form>
    <div class="explorer-caption">
      <span>{{ explorer === "schedule" ? "SCHEDULE ITEMS" : "RESOURCE LIBRARY" }}</span
      ><span>{{ (explorer === "schedule" ? schedule : resources).length }} shown</span>
    </div>
    <nav
      ref="results"
      class="item-list"
      :aria-label="explorer === 'schedule' ? 'Schedule items' : 'Resource library'"
      @keydown.up.down.home.end="navigateResults"
    >
      <template v-if="explorer === 'schedule'"
        ><button
          v-for="item in schedule"
          :key="item.code"
          class="item-card"
          :class="{ active: activeCode === item.code }"
          :disabled="uiBusy"
          @click="emit('loadAnalysis', item.code)"
        >
          <span class="item-code"
            ><AppIcon name="file" :size="14" />{{ item.code
            }}<span v-if="activeCode === item.code" class="item-active-dot" /></span
          ><span class="item-description">{{ item.description }}</span
          ><span class="item-unit">{{ item.unit || "Heading" }}</span>
        </button></template
      >
      <template v-else
        ><button
          v-for="item in resources"
          :key="item.code"
          class="item-card"
          :disabled="uiBusy || !canInsertResource"
          @click="emit('insertResource', item.code)"
        >
          <span class="item-code"><AppIcon name="resource" :size="14" />{{ item.code }}</span
          ><span class="item-description">{{ item.description }}</span
          ><span class="item-unit">{{ formatMoney(item.rate) }} / {{ item.unit }}</span>
        </button></template
      >
      <div v-if="!(explorer === 'schedule' ? schedule : resources).length" class="empty-explorer">
        <AppIcon :name="projectOpen ? 'search' : 'folder'" :size="30" /><strong>{{
          projectOpen ? "No items to show" : "Your project starts here"
        }}</strong>
        <p>
          {{
            projectOpen
              ? "Search by code or description."
              : "Open a GEstimator project to explore its schedule and resources."
          }}
        </p>
        <button v-if="!projectOpen" class="button secondary" :disabled="uiBusy" @click="emit('openProject')">
          Open project
        </button>
      </div>
    </nav>
    <div v-if="projectOpen" class="pagination">
      <button
        class="icon-button"
        aria-label="Previous page"
        :disabled="busy || (explorer === 'schedule' ? schedulePage : resourcePage) === 0"
        @click="
          explorer === 'schedule' ? emit('searchSchedule', schedulePage - 1) : emit('searchResources', resourcePage - 1)
        "
      >
        <AppIcon name="up" :size="15" /></button
      ><span>Page {{ (explorer === "schedule" ? schedulePage : resourcePage) + 1 }}</span
      ><button
        class="icon-button"
        aria-label="Next page"
        :disabled="busy || (explorer === 'schedule' ? schedule : resources).length < 100"
        @click="
          explorer === 'schedule' ? emit('searchSchedule', schedulePage + 1) : emit('searchResources', resourcePage + 1)
        "
      >
        <AppIcon name="down" :size="15" />
      </button>
    </div>
    <div class="explorer-foot"><AppIcon name="check" :size="14" /><span>Isolated working copy</span></div>
  </aside>
</template>
