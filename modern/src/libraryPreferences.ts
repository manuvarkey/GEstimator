import { ref } from "vue";
import { request } from "./backend";

export interface SavedLibrary { path: string; name: string; error?: string }
interface Source { id: string; name: string; attached?: boolean }
const storageKey = "gestimator.libraries.v1";
export const savedLibraries = ref<SavedLibrary[]>([]);
export const libraryStorageError = ref("");
const attached = new Map<string, string>();
try {
  const entries: unknown = JSON.parse(sessionStorage.getItem("gestimator.library-attachments") || "[]");
  if (Array.isArray(entries)) for (const entry of entries.slice(0, 50)) {
    if (Array.isArray(entry) && entry.length === 2 && entry.every(value => typeof value === "string")) attached.set(entry[0], entry[1]);
  }
} catch { /* Attachments can be rebuilt when session storage is unavailable. */ }

function identity(path: string) {
  const value = path.trim().replaceAll("\\", "/");
  return /^[a-z]:\//i.test(value) ? value.toLowerCase() : value;
}
try {
  const stored = JSON.parse(localStorage.getItem(storageKey) || "null");
  if (stored?.version === 1 && Array.isArray(stored.libraries)) {
    const seen = new Set<string>();
    savedLibraries.value = stored.libraries.filter((entry: SavedLibrary) => {
      if (!entry || typeof entry.path !== "string" || !entry.path.trim() || entry.path.length > 4096 || seen.has(identity(entry.path))) return false;
      seen.add(identity(entry.path));
      return true;
    }).slice(0, 50).map((entry: SavedLibrary) => ({ path: entry.path.trim(), name: typeof entry.name === "string" ? entry.name : entry.path }));
  }
} catch {
  libraryStorageError.value = "Saved library preferences could not be read. Libraries can still be attached for this session.";
}
function persist() {
  try {
    localStorage.setItem(storageKey, JSON.stringify({ version: 1, libraries: savedLibraries.value.map(({ path, name }) => ({ path, name })) }));
    libraryStorageError.value = "";
  } catch {
    libraryStorageError.value = "Library preferences could not be saved. Current attachments remain available for this session.";
  }
}
export function forgetLibrary(path: string) {
  savedLibraries.value = savedLibraries.value.filter(entry => identity(entry.path) !== identity(path));
  persist();
}
export async function attachLibrary(path: string, remember = true) {
  path = path.trim();
  if (!path || path.length > 4096) throw new Error("Enter a library project path.");
  const key = identity(path);
  if (remember && savedLibraries.value.length >= 50 && !savedLibraries.value.some(entry => identity(entry.path) === key)) {
    throw new Error("Up to 50 libraries can be remembered. Forget an entry or attach this library for the session only.");
  }
  const sources = await request<Source[]>("library.list");
  let source = sources.find(entry => entry.id === attached.get(key));
  if (!source) {
    const next = await request<Source[]>("library.attach", { path });
    source = next.find(entry => entry.attached) || next.find(entry => !sources.some(old => old.id === entry.id));
    if (!source) throw new Error("The library did not return an attachment identifier.");
    attached.set(key, source.id);
    try { sessionStorage.setItem("gestimator.library-attachments", JSON.stringify([...attached].slice(-50))); }
    catch { /* The active connection still works without persisted session identifiers. */ }
  }
  const existing = savedLibraries.value.find(entry => identity(entry.path) === key || attached.get(identity(entry.path)) === source!.id);
  if (existing) { existing.name = source.name; existing.error = undefined; }
  if (remember) {
    if (!existing) savedLibraries.value.push({ path, name: source.name });
    persist();
  }
  return source;
}
/** Bundled databases and the user database folder are attached automatically. */
export const catalogWarnings = ref<string[]>([]);
export async function restoreLibraries() {
  try { catalogWarnings.value = (await request<{ warnings: string[] }>("library.attach_catalog")).warnings; }
  catch (error) { catalogWarnings.value = [String(error)]; }
  for (const library of savedLibraries.value) {
    try { await attachLibrary(library.path, false); }
    catch (error) { library.error = error instanceof Error ? error.message : String(error); }
  }
}
