<script setup lang="ts">
import { ref, watch } from "vue";
import Dialog from "primevue/dialog";
import { mcpStatus, mcpBusy, mcpError, mcpMessage, mcpAutostart, mcpConfig, saveMCP, rotateMCPToken, copyMCPConfig, refreshMCP, startMCP, stopMCP } from "../mcp";
const visible = defineModel<boolean>({ required: true });
const port = ref(8765);
const autostart = ref(false);
const reveal = ref(false);
watch(visible, async value => {
  if (!value) return;
  await refreshMCP();
  port.value = mcpStatus.value?.port || 8765;
  autostart.value = mcpAutostart.value;
  reveal.value = false;
});
async function save() { await saveMCP(port.value, autostart.value); }
</script>
<template>
  <Dialog v-model:visible="visible" modal header="Configure MCP server" class="workspace-dialog mcp-settings-dialog" :closable="!mcpBusy" :close-on-escape="!mcpBusy">
    <p class="dialog-intro">Connect an MCP client to the project open in GEstimator. Tools read schedule, resources, the active analysis and measurements using the existing calculation engine.</p>
    <p role="status"><strong>{{ mcpStatus?.running ? 'Running' : 'Stopped' }}</strong> · Local access · Read only</p>
    <form @submit.prevent="save">
      <label class="field">Port<input v-model.number="port" type="number" min="1024" max="65535" required :disabled="mcpBusy || mcpStatus?.running" /></label>
      <label class="library-remember"><input v-model="autostart" type="checkbox" :disabled="mcpBusy || mcpStatus?.running" />Start automatically when GEstimator opens</label>
      <p class="field-hint">Save changes before starting. Stop the server to change settings or rotate its token. Closing this dialog leaves a running server available; exiting GEstimator stops it.</p>
      <label class="field">Endpoint<input :value="mcpStatus?.url" readonly /></label>
      <label class="field">Connection token<input :value="mcpStatus?.token" :type="reveal ? 'text' : 'password'" readonly /></label>
      <div class="project-tools"><button class="button secondary" type="button" @click="reveal = !reveal">{{ reveal ? 'Hide token' : 'Show token' }}</button><button class="button secondary" type="button" :disabled="mcpBusy || mcpStatus?.running" @click="rotateMCPToken">Rotate token</button><button class="button secondary" type="button" :disabled="mcpBusy || !mcpStatus" @click="copyMCPConfig">Copy client configuration</button></div>
      <p class="field-hint">The token grants read access to the current project. Settings are saved on this device. Clients supporting Streamable HTTP can use this URL and Bearer authorization header.</p>
      <label v-if="reveal" class="field">Client configuration<textarea :value="mcpConfig()" readonly rows="9" spellcheck="false" /></label>
      <details><summary>Available tools ({{ mcpStatus?.tools.length || 0 }})</summary><dl class="mcp-tools"><template v-for="tool in mcpStatus?.tools" :key="tool.name"><dt>{{ tool.name }}</dt><dd>{{ tool.description }}</dd></template></dl></details>
      <p class="field-hint">{{ mcpStatus?.requests || 0 }} requests · {{ mcpStatus?.last_activity || 'No client activity yet' }} · Protocol {{ mcpStatus?.protocol }}</p>
      <p v-if="mcpError" class="dialog-error" role="alert">{{ mcpError }}</p><p v-if="mcpMessage" role="status">{{ mcpMessage }}</p>
      <div class="dialog-footer"><button class="button secondary" type="button" aria-label="Close MCP settings" :disabled="mcpBusy" @click="visible = false">Close</button><button class="button secondary" type="button" :disabled="mcpBusy || (!mcpStatus?.running && (port !== mcpStatus?.port || autostart !== mcpAutostart))" @click="mcpStatus?.running ? stopMCP() : startMCP()">{{ mcpStatus?.running ? 'Stop server' : 'Start server' }}</button><button class="button primary" type="submit" :disabled="mcpBusy || mcpStatus?.running">Save settings</button></div>
    </form>
  </Dialog>
</template>
