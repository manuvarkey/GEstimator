<script setup lang="ts">
import App from "./App.vue";
import { activeDocument } from "./documents";
</script>
<template>
  <!-- Each project tab remounts the workspace bound to its own backend session. -->
  <App :key="activeDocument" />
</template>
