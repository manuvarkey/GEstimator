<script setup lang="ts">
import AppIcon from "./AppIcon.vue";

defineProps<{
  busy: boolean;
  recent: string[];
  recovery: { id: string; updated: number }[];
}>();
const emit = defineEmits<{
  new: [];
  open: [];
  openRecent: [path: string];
  recover: [id: string];
  clearRecent: [];
}>();

const fileName = (path: string) => path.split(/[\\/]/).pop()?.replace(/\.eproj$/i, "") || path;
const folder = (path: string) => path.slice(0, Math.max(0, path.length - (path.split(/[\\/]/).pop()?.length || 0) - 1));
</script>
<template>
  <section class="project-landing" aria-labelledby="project-landing-title">
    <div class="project-landing-body">
      <h1 id="project-landing-title">Start an estimate</h1>
      <p class="field-hint">Create a new project or open an existing <code>.eproj</code> file. Projects open in an isolated working copy.</p>
      <div class="project-landing-actions">
        <button type="button" class="landing-action" :disabled="busy" @click="emit('new')">
          <AppIcon name="file" :size="24" />
          <span><strong>New project</strong><small>Start a blank estimate</small></span>
        </button>
        <button type="button" class="landing-action" :disabled="busy" @click="emit('open')">
          <AppIcon name="folder" :size="24" />
          <span><strong>Open project…</strong><small>Browse for a .eproj file</small></span>
        </button>
      </div>

      <section v-if="recovery.length" class="project-landing-section" aria-labelledby="landing-recovery">
        <h2 id="landing-recovery">Recover unsaved work</h2>
        <ul class="landing-list">
          <li v-for="copy in recovery" :key="copy.id">
            <button type="button" class="landing-item" :disabled="busy" @click="emit('recover', copy.id)">
              <AppIcon name="refresh" :size="18" />
              <span><strong>Recover project</strong><small>Checkpoint from {{ new Date(copy.updated * 1000).toLocaleString() }}</small></span>
            </button>
          </li>
        </ul>
      </section>

      <section class="project-landing-section" aria-labelledby="landing-recent">
        <div class="project-landing-heading">
          <h2 id="landing-recent">Recent projects</h2>
          <button v-if="recent.length" type="button" class="text-button" :disabled="busy" @click="emit('clearRecent')">Clear list</button>
        </div>
        <ul v-if="recent.length" class="landing-list" aria-label="Recent projects">
          <li v-for="path in recent" :key="path">
            <button type="button" class="landing-item" :disabled="busy" :title="path" @click="emit('openRecent', path)">
              <AppIcon name="file" :size="18" />
              <span><strong>{{ fileName(path) }}</strong><small>{{ folder(path) }}</small></span>
            </button>
          </li>
        </ul>
        <p v-else class="field-hint">Projects you open or save appear here.</p>
      </section>
    </div>
  </section>
</template>
