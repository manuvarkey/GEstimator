<script setup lang="ts">
// The file workflow owns chooser actions and state shared with the native open queue.
import Dialog from "primevue/dialog";
import AppIcon from "./AppIcon.vue";
import { pathsEqual } from "../documents";

const fileMode = defineModel<"open" | "save" | null>("mode", { required: true });
const filePath = defineModel<string>("path", { required: true });
defineProps<{
  error: string;
  busy: boolean;
  uiBusy: boolean;
  recentProjects: readonly string[];
  recoveryProjects: readonly { id: string; updated: number }[];
}>();
const emit = defineEmits<{
  browse: [];
  submit: [];
  clearRecent: [];
  recover: [id: string];
}>();
</script>

<template>
  <Dialog
    :visible="fileMode !== null"
    modal
    :header="fileMode === 'open' ? 'Open project' : 'Save project copy'"
    class="workspace-dialog file-dialog"
    @update:visible="fileMode = null"
    ><p class="dialog-intro">
      {{
        fileMode === "open"
          ? "Choose an existing GEstimator project. You will edit a working copy."
          : "Save your analysis and dependent rates to a new project file."
      }}
    </p>
    <form @submit.prevent="emit('submit')">
      <label class="field"
        >Project file
        <div class="file-input">
          <input
            v-model="filePath"
            data-primary-input
            :placeholder="fileMode === 'open' ? '/path/to/project.eproj' : '/path/to/project-edited.eproj'"
            required
            autofocus
          /><button type="button" class="button secondary" @click="emit('browse')">
            <AppIcon name="folder" :size="16" />Browse
          </button>
        </div></label
      >
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <p class="field-hint">
        {{
          fileMode === "save"
            ? "Choose a new filename. Existing files cannot be overwritten."
            : "Supports version 2 .eproj projects."
        }}
      </p>
      <label v-if="fileMode === 'open' && recentProjects.length" class="field">
        Recent projects
        <select
          aria-label="Recent projects"
          :value="recentProjects.find((item) => pathsEqual(item, filePath)) || ''"
          @change="filePath = ($event.target as HTMLSelectElement).value"
        >
          <option value="">Choose a recent project</option>
          <option v-for="path in recentProjects" :key="path" :value="path">{{ path }}</option>
        </select>
        <button type="button" class="button secondary" @click="emit('clearRecent')">Clear recent projects</button>
      </label>
      <div v-if="fileMode === 'open' && recoveryProjects.length" class="field">
        <strong>Recover unsaved work</strong>
        <button
          v-for="copy in recoveryProjects"
          :key="copy.id"
          type="button"
          class="button secondary"
          :disabled="uiBusy"
          @click="emit('recover', copy.id)"
        >
          Recover project from {{ new Date(copy.updated * 1000).toLocaleString() }}
        </button>
      </div>
      <div class="dialog-footer">
        <button type="button" class="button secondary" @click="fileMode = null">Cancel</button
        ><button class="button primary" :disabled="uiBusy || !filePath.trim()">
          <AppIcon :name="fileMode === 'open' ? 'folder' : 'save'" :size="16" />{{
            busy ? "Working…" : fileMode === "open" ? "Open project" : "Save copy"
          }}
        </button>
      </div>
    </form></Dialog
  >
</template>
