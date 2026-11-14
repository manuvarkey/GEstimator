import { ref } from "vue";
import { writeText } from "@tauri-apps/plugin-clipboard-manager";
import { request } from "./backend";

export interface MCPStatus {
  running: boolean; port: number; token: string; url: string; protocol: string;
  requests: number; last_activity: string; tools: { name: string; description: string }[];
}
const key = "gestimator.mcp.v1";
export const mcpStatus = ref<MCPStatus>();
export const mcpBusy = ref(false);
export const mcpError = ref("");
export const mcpMessage = ref("");
export const mcpAutostart = ref(false);
export const mcpConfig = () => JSON.stringify({ mcpServers: { gestimator: { url: mcpStatus.value?.url, headers: { Authorization: "Bearer " + mcpStatus.value?.token } } } }, null, 2);

async function command(method: string, params = {}, quiet = false) {
  if (mcpBusy.value) return false;
  mcpBusy.value = true;
  if (!quiet) { mcpError.value = ""; mcpMessage.value = ""; }
  try { mcpStatus.value = await request<MCPStatus>(method, params); return true; }
  catch (failure) { mcpError.value = String(failure); return false; }
  finally { mcpBusy.value = false; }
}
export const refreshMCP = () => command("mcp.status", {}, true);
export const startMCP = () => command("mcp.start");
export const stopMCP = () => command("mcp.stop");
function remember() {
  if (!mcpStatus.value) return;
  localStorage.setItem(key, JSON.stringify({ version: 1, port: mcpStatus.value.port, token: mcpStatus.value.token, autostart: mcpAutostart.value }));
}
export async function saveMCP(port: number, autostart: boolean) {
  if (!await command("mcp.configure", { port })) return false;
  mcpAutostart.value = autostart;
  try { remember(); mcpMessage.value = "MCP settings saved."; return true; }
  catch { mcpError.value = "Settings are active for this session, but could not be saved for the next launch."; return false; }
}
export async function rotateMCPToken() {
  if (!await command("mcp.rotate_token")) return;
  try { remember(); mcpMessage.value = "Connection token changed. Update the configuration in your MCP client."; }
  catch { mcpError.value = "Token changed for this session, but could not be saved. Copy the current client configuration."; }
}
export async function copyMCPConfig() {
  if (!mcpStatus.value) { mcpError.value = "Server status is unavailable. Refresh MCP status before copying configuration."; return; }
  try { await writeText(mcpConfig()); mcpMessage.value = "Client configuration copied."; }
  catch { mcpError.value = "Clipboard unavailable. Copy the client configuration from Configure MCP server."; }
}
export async function initializeMCP() {
  if (!await refreshMCP()) return;
  try {
    const saved = JSON.parse(localStorage.getItem(key) || "null");
    if (saved) {
      if (saved.version !== 1 || typeof saved.autostart !== "boolean" || typeof saved.port !== "number" || typeof saved.token !== "string") throw new Error("Invalid preferences");
      if (!mcpStatus.value?.running && !await command("mcp.configure", { port: saved.port, token: saved.token })) return;
      mcpAutostart.value = saved.autostart;
      if (saved.autostart && !mcpStatus.value?.running) await startMCP();
    } else remember();
  } catch { mcpError.value = "Saved MCP settings could not be read. Review and save MCP settings to replace them."; }
}
