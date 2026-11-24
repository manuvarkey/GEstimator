import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { request } from "./backend";

interface SkillLibrary {
  id: string;
  name: string;
  description: string;
  bundled: boolean;
}

interface SkillLibraries {
  libraries: SkillLibrary[];
  active_library: string;
  requested_library: string;
  user_directory: string;
  issues: string[];
}

export const skillLibraries = ref<SkillLibraries>();

/** Refresh is explicit so normal MCP requests can use one cached backend snapshot. */
export async function loadSkillLibraries(refresh = false) {
  const result = await request<SkillLibraries>(refresh ? "mcp.refresh_skill_libraries" : "mcp.skill_libraries");
  skillLibraries.value = result;
  return result;
}

export async function openUserSkillDirectory() {
  const path = await request<string>("mcp.skill_directory");
  await invoke("open_library_directory", { path });
}
