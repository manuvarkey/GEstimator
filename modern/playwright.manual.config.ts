import { defineConfig } from "@playwright/test";
// Screenshots for the user manual (docs/manual/images); see manual/screenshots.spec.ts.
export default defineConfig({
  testDir: "./manual",
  timeout: 120000,
  expect: { timeout: 10000 },
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:1420",
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:1420",
    reuseExistingServer: true,
  },
});
