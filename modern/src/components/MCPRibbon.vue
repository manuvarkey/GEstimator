<script setup lang="ts">
import { ref } from "vue";
import AppIcon from "./AppIcon.vue";
import { copyMCPConfig, mcpBusy, mcpError, mcpMessage, mcpStatus, refreshMCP, startMCP, stopMCP } from "../mcp";
import { loadSkillLibraries, openUserSkillDirectory } from "../skillLibraries";

const emit = defineEmits<{ configure: [] }>();
const skillsBusy = ref(false);

async function manageSkills(refresh: boolean) {
  skillsBusy.value = true;
  mcpError.value = "";
  mcpMessage.value = "";
  try {
    if (refresh) {
      const result = await loadSkillLibraries(true);
      const unavailable = result.active_library !== result.requested_library;
      mcpMessage.value =
        result.issues.length || unavailable
          ? "Skill libraries refreshed. Review library messages in Configure server."
          : "Skill libraries refreshed.";
    } else {
      await openUserSkillDirectory();
    }
  } catch (failure) {
    mcpError.value = String(failure);
  } finally {
    skillsBusy.value = false;
  }
}
</script>

<template>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action"
        aria-label="Start MCP server"
        title="Start the authenticated local MCP server using the access mode selected in Configure server."
        :disabled="mcpBusy || !mcpStatus || mcpStatus.running"
        @click="startMCP"
      >
        <AppIcon name="play" /><span class="ribbon-label">Start server</span></button
      ><button
        class="ribbon-action"
        aria-label="Stop MCP server"
        title="Stop listening and prevent further MCP requests. The current project and editor stay open."
        :disabled="mcpBusy || !mcpStatus?.running"
        @click="stopMCP"
      >
        <AppIcon name="stop" /><span class="ribbon-label">Stop server</span>
      </button>
    </div>
    <small>SERVER</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action"
        aria-label="Configure MCP server"
        title="Configure the local port, automatic startup and connection token; inspect available tools and client configuration."
        :disabled="mcpBusy"
        @click="emit('configure')"
      >
        <AppIcon name="settings" /><span class="ribbon-label">Configure server</span></button
      ><button
        class="ribbon-action"
        aria-label="Copy MCP client configuration"
        title="Copy the server URL and authorization header as JSON for a Streamable HTTP MCP client."
        :disabled="mcpBusy || !mcpStatus"
        @click="copyMCPConfig"
      >
        <AppIcon name="copy" /><span class="ribbon-label">Client config</span></button
      ><button
        class="ribbon-action"
        aria-label="Refresh MCP status"
        title="Refresh server status and client activity without changing the project."
        :disabled="mcpBusy"
        @click="refreshMCP"
      >
        <AppIcon name="refresh" /><span class="ribbon-label">Refresh status</span>
      </button>
    </div>
    <small>CONNECTION</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action"
        aria-label="Open user skill folder"
        title="Open the user skill library folder in your file manager."
        :disabled="skillsBusy"
        @click="manageSkills(false)"
      >
        <AppIcon name="folder" /><span class="ribbon-label">User skill folder</span>
      </button>
      <button
        class="ribbon-action"
        aria-label="Refresh skills"
        title="Rescan packaged and user skill libraries."
        :disabled="skillsBusy"
        @click="manageSkills(true)"
      >
        <AppIcon name="refresh" /><span class="ribbon-label">Refresh skills</span>
      </button>
    </div>
    <small>ESTIMATION SKILLS</small>
  </div>
  <span class="ribbon-note" role="status"
    >{{ mcpStatus?.running ? "Running" : "Stopped" }} ·
    {{ mcpStatus?.access === "read-write" ? "Read and write" : "Read only" }}<br />{{
      mcpStatus?.url || "Connecting…"
    }}</span
  >
</template>
