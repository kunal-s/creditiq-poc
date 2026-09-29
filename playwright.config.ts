/// <reference types="node" />
import { defineConfig, devices } from "@playwright/test";

// Screen tests (FRD AD-6): the screens run on the Vite dev server and the
// engine API is answered in the browser (e2e/support/api.ts), so no engine,
// data root or model is needed. Results are written outside the repository.
const PORT = 5173;

export default defineConfig({
  testDir: "e2e",
  outputDir: "/tmp/ciq-screens-playwright",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: 3,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "off",
    screenshot: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npx vite dev --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}/sign-in`,
    reuseExistingServer: true,
    timeout: 120_000,
    env: { VITE_API_BASE_URL: "http://localhost:8201" },
  },
});
