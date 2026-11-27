<script setup lang="ts">
/** Embed a selected local logo so a saved report has no file dependency. */
import { ref } from "vue";
const logo = defineModel<string>({ required: true });
defineProps<{ label?: string }>();
const error = ref("");
const reading = ref(false);
async function choose(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  input.value = "";
  error.value = "";
  if (file.size > 384 * 1024) {
    error.value = "Choose a logo up to 384 KiB.";
    return;
  }
  const mime = file.type || (/\.svg$/i.test(file.name) ? "image/svg+xml" : "");
  if (!["image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"].includes(mime)) {
    error.value = "Choose a PNG, JPEG, GIF, WebP or SVG logo.";
    return;
  }
  reading.value = true;
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    const chunks: string[] = [];
    for (let start = 0; start < bytes.length; start += 8192) {
      chunks.push(String.fromCharCode(...bytes.subarray(start, start + 8192)));
    }
    logo.value = "data:" + mime + ";base64," + btoa(chunks.join(""));
  } catch {
    error.value = "Could not read the logo.";
  } finally {
    reading.value = false;
  }
}
</script>
<template>
  <div class="logo-field">
    <label class="field"
      >Logo<input
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml,.svg"
        :aria-label="label || 'Report logo'"
        :disabled="reading"
        @change="choose"
    /></label>
    <div v-if="logo" class="selected-logo">
      <img :src="logo" alt="Selected report logo" />
      <button type="button" :disabled="reading" @click="logo = ''">Remove logo</button>
    </div>
    <p v-if="error" class="dialog-error" role="alert">{{ error }}</p>
  </div>
</template>
<style scoped>
.selected-logo {
  display: flex;
  align-items: center;
  gap: 8px;
}
img {
  max-inline-size: 120px;
  max-block-size: 56px;
  object-fit: contain;
}
</style>
