<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import {
  mcpStatus,
  mcpBusy,
  mcpError,
  mcpMessage,
  mcpAutostart,
  mcpConfig,
  saveMCP,
  rotateMCPToken,
  copyMCPConfig,
  refreshMCPTools,
  startMCP,
  stopMCP,
} from "../mcp";
import { loadSkillLibraries, skillLibraries } from "../skillLibraries";
const visible = defineModel<boolean>({ required: true });
const port = ref(8765);
const autostart = ref(false);
const access = ref<"read" | "read-write">("read");
const reveal = ref(false);
const skillLibraryName = computed(
  () => skillLibraries.value?.libraries.find((library) => library.id === skillLibraries.value?.active_library)?.name,
);
const skillLibraryError = ref("");
watch(visible, async (value) => {
  if (!value) return;
  await refreshMCPTools();
  port.value = mcpStatus.value?.port || 8765;
  autostart.value = mcpAutostart.value;
  access.value = mcpStatus.value?.access || "read";
  reveal.value = false;
  skillLibraryError.value = "";
  try {
    await loadSkillLibraries();
  } catch (failure) {
    skillLibraryError.value = String(failure);
  }
});
async function save() {
  await saveMCP(port.value, autostart.value, access.value);
}
</script>
<template>
  <Dialog
    v-model:visible="visible"
    modal
    header="Configure MCP server"
    class="workspace-dialog mcp-settings-dialog"
    :closable="!mcpBusy"
    :close-on-escape="!mcpBusy"
  >
    <p role="status">
      <strong>{{ mcpStatus?.running ? "Running" : "Stopped" }}</strong> · Local access ·
      {{ mcpStatus?.access === "read-write" ? "Read and write" : "Read only" }}
    </p>
    <form @submit.prevent="save">
      <label class="field"
        >Port<input
          v-model.number="port"
          type="number"
          min="1024"
          max="65535"
          required
          :disabled="mcpBusy || mcpStatus?.running"
      /></label>
      <label class="field"
        >Access mode<select v-model="access" aria-label="Access mode" :disabled="mcpBusy || mcpStatus?.running">
          <option value="read">Read only</option>
          <option value="read-write">Read and write</option>
        </select></label
      >
      <label class="library-remember"
        ><input v-model="autostart" type="checkbox" :disabled="mcpBusy || mcpStatus?.running" />Start automatically when
        GEstimator opens</label
      >
      <p class="field-hint">
        Save changes before starting. Stop the server to change settings or rotate its token. Closing this dialog leaves
        a running server available; exiting GEstimator stops it.
      </p>
      <label class="field">Endpoint<input :value="mcpStatus?.url" readonly /></label>
      <label class="field"
        >Connection token<input :value="mcpStatus?.token" :type="reveal ? 'text' : 'password'" readonly
      /></label>
      <div class="project-tools">
        <button class="button secondary" type="button" @click="reveal = !reveal">
          {{ reveal ? "Hide token" : "Show token" }}</button
        ><button
          class="button secondary"
          type="button"
          :disabled="mcpBusy || mcpStatus?.running"
          @click="rotateMCPToken"
        >
          Rotate token</button
        ><button class="button secondary" type="button" :disabled="mcpBusy || !mcpStatus" @click="copyMCPConfig">
          Copy client configuration
        </button>
      </div>
      <p class="field-hint">
        The token grants the configured access to project, database and file operations. Clients use the endpoint and
        Bearer header below.
      </p>
      <label v-if="reveal" class="field"
        >Client configuration<textarea :value="mcpConfig()" readonly rows="9" spellcheck="false" />
      </label>
      <details>
        <summary>Available tools ({{ mcpStatus?.tools.length || 0 }})</summary>
        <dl class="mcp-tools">
          <template v-for="tool in mcpStatus?.tools" :key="tool.name"
            ><dt>{{ tool.name }} <small v-if="!tool.annotations?.readOnlyHint">Write</small></dt>
            <dd>{{ tool.description }}</dd></template
          >
        </dl>
      </details>
      <details
        v-if="skillLibraries"
        :open="!!skillLibraries.issues.length || skillLibraries.active_library !== skillLibraries.requested_library"
      >
        <summary>Estimation skill libraries</summary>
        <p>Active library: {{ skillLibraryName || skillLibraries.active_library }}</p>
        <p v-if="skillLibraries.active_library !== skillLibraries.requested_library" role="status">
          “{{ skillLibraries.requested_library }}” is unavailable. Generic is active.
        </p>
        <ul v-if="skillLibraries.issues.length">
          <li v-for="(issue, index) in skillLibraries.issues" :key="index">{{ issue }}</li>
        </ul>
        <label class="field">User skill folder<input :value="skillLibraries.user_directory" readonly /></label>
      </details>
      <p v-if="skillLibraryError" class="dialog-error" role="alert">{{ skillLibraryError }}</p>
      <p class="field-hint">
        {{ mcpStatus?.requests || 0 }} requests · {{ mcpStatus?.last_activity || "No client activity yet" }} · Protocol
        {{ mcpStatus?.protocol }}
      </p>
      <p v-if="mcpError" class="dialog-error" role="alert">{{ mcpError }}</p>
      <p v-if="mcpMessage" role="status">{{ mcpMessage }}</p>
      <div class="dialog-footer">
        <button
          class="button secondary"
          type="button"
          aria-label="Close MCP settings"
          :disabled="mcpBusy"
          @click="visible = false"
        >
          Close</button
        ><button
          class="button secondary"
          type="button"
          :disabled="
            mcpBusy ||
            (!mcpStatus?.running &&
              (port !== mcpStatus?.port || autostart !== mcpAutostart || access !== mcpStatus?.access))
          "
          @click="mcpStatus?.running ? stopMCP() : startMCP()"
        >
          {{ mcpStatus?.running ? "Stop server" : "Start server" }}</button
        ><button class="button primary" type="submit" :disabled="mcpBusy || mcpStatus?.running">Save settings</button>
      </div>
    </form>
  </Dialog>
</template>
