<script setup lang="ts">
import { ref } from "vue";
import Dialog from "primevue/dialog";
import AppIcon from "./AppIcon.vue";
import { open } from "@tauri-apps/plugin-dialog";
import { attachLibrary, forgetLibrary, savedLibraries, libraryStorageError } from "../libraryPreferences";
import { request } from "../backend";
import { invoke } from "@tauri-apps/api/core";

const props = defineProps<{ projectOpen: boolean }>();
const visible = defineModel<boolean>({ required: true });
const emit = defineEmits<{ changed: [] }>();
const path = ref("");
const remember = ref(true);
const busy = ref(false);
const error = ref("");
const available = ref<{ name: string; path: string; bundled: boolean }[]>([]);
const availablePath = ref("");
const catalogWarnings = ref<string[]>([]);
const attached = ref<{ id: string; name: string }[]>([]);
const message = ref("");
async function refresh() {
  await discover();
  attached.value = props.projectOpen ? await request("library.list") : [];
}
defineExpose({ openDirectory });
async function openDirectory() {
  try { await invoke("open_library_directory", { path: await request("program.library_directory") }); }
  catch (failure) { error.value = String(failure); visible.value = true; }
}
async function discover() {
  try {
    const result = await request<{ rows: typeof available.value; warnings: string[] }>("program.libraries");
    available.value = result.rows;
    catalogWarnings.value = result.warnings;
  } catch (failure) { error.value = String(failure); }
}
async function attach(value = path.value) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const source = await attachLibrary(value, remember.value);
    attached.value = await request("library.list");
    message.value = source.name + " attached. Ready for item selection and rate updates.";
    emit("changed");
  } catch (failure) { error.value = String(failure); }
  finally { busy.value = false; }
}
async function browse() {
  try {
    const selected = await open({ multiple: false, filters: [{ name: "GEstimator library", extensions: ["eproj"] }] });
    if (typeof selected === "string") path.value = selected;
  } catch (failure) { error.value = String(failure); }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal header="Attach resource / schedule library" class="workspace-dialog file-dialog library-manager-dialog" :closable="!busy" :close-on-escape="!busy" @show="refresh">
    <p class="dialog-intro">Browse an external project as a read-only snapshot. Imports and price updates change the working project; the library source stays unchanged.</p>
    <label class="field">Available databases<select v-model="availablePath" :disabled="busy" @change="path = availablePath"><option value="">Choose a bundled or custom database…</option><option v-for="database in available" :key="database.path" :value="database.path">{{ database.name }} ({{ database.bundled ? 'bundled' : 'custom' }})</option></select></label>
    <button class="text-button" :disabled="busy" @click="discover">Refresh available databases</button>
    <p v-for="warning in catalogWarnings" :key="warning" class="dialog-error" role="status">{{ warning }}</p>
    <label class="field">Library project
      <div class="file-input"><input v-model="path" data-primary-input autofocus aria-label="Library project" :disabled="busy" placeholder="Absolute path to a .eproj library" @keydown.enter.prevent="attach()" />
        <button class="button secondary" :disabled="busy" @click="browse">Browse</button></div>
    </label>
    <label class="library-remember"><input v-model="remember" type="checkbox" :disabled="busy" />Remember for future projects</label>
    <p v-if="message" role="status">{{ message }}</p>
    <div v-if="attached.length" class="attached-databases" aria-label="Attached databases"><h3>Attached databases</h3><div v-for="database in attached" :key="database.id" class="attached-database"><AppIcon name="database" /><span>{{ database.name }}</span><small>Ready for selection and rate updates</small></div></div>
    <p v-if="!projectOpen" class="field-hint">Open or create a project to attach libraries. Saved entries can be managed here at any time.</p>
    <div v-if="savedLibraries.length" class="saved-libraries" aria-label="Saved libraries">
      <h3>Saved libraries</h3>
      <p class="field-hint">Reopened automatically with each project. Forget removes the saved path; an already attached snapshot remains available until the project closes.</p>
      <div v-for="library in savedLibraries" :key="library.path" class="saved-library">
        <strong>{{ library.name }}</strong><code>{{ library.path }}</code>
        <p v-if="library.error" class="dialog-error" role="status">Unavailable: {{ library.error }}</p>
        <div class="project-tools">
          <button class="button small secondary" :disabled="busy || !projectOpen" :aria-label="'Retry library ' + library.name" @click="attach(library.path)">Attach / retry</button>
          <button class="button small secondary" :disabled="busy" :aria-label="'Forget library ' + library.name" @click="forgetLibrary(library.path)">Forget</button>
        </div>
      </div>
    </div>
    <p v-if="libraryStorageError" class="dialog-error" role="status">{{ libraryStorageError }}</p>
    <p v-if="error" class="dialog-error" role="alert">{{ error }}</p>
    <div class="dialog-footer"><button class="button secondary" :disabled="busy" @click="openDirectory">Open database folder</button><button class="button secondary" aria-label="Close database manager" :disabled="busy" @click="visible = false">Close</button><button class="button primary" :disabled="busy || !projectOpen || !path.trim()" @click="attach()">Attach library</button></div>
  </Dialog>
</template>
