import { defineConfig } from "@playwright/test";

// Logic tests that need no browser and no server (the case assistant panel's stream parser).
export default defineConfig({
  testDir: "services/copilot/ui/test",
  outputDir: "/tmp/ciq-unit-playwright",
  reporter: [["list"]],
});
