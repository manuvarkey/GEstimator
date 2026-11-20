import { createApp } from "vue";
import PrimeVue from "primevue/config";
import Aura from "@primeuix/themes/aura";
import Root from "./Root.vue";
import "./theme.css";
import "./style.css";
import { installUIActions } from "./uiActions";
import { installTextEntry } from "./textEntry";
installTextEntry();
installUIActions();
createApp(Root)
  .use(PrimeVue, {
    theme: { preset: Aura, options: { darkModeSelector: "[data-theme=dark]" } },
  })
  .mount("#app");
