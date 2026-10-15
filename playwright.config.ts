/// <reference types="node" />
import { defineConfig, devices } from "@playwright/test";

// Two kinds of test run side by side.
//
// "chromium" — screen tests (FRD AD-6): the screens run on the Vite dev server
// and the engine API is answered in the browser (e2e/support/api.ts), so no
// engine, data root or model is needed.
//
// "integration" — the specs under e2e/integration drive the REAL engine
// (e2e/support/engine.ts) on its own port and its own disposable data root,
// with CREDITIQ_INGEST=stub so document processing replays the recorded results
// in tests/fixtures/ingest/. Deterministic plumbing; NOT a test of extraction
// accuracy.
//
// Results are written outside the repository.
// Override the ports when they are taken by another project (each dev server
// below is reused if one is already listening, which would otherwise test the
// wrong app).
const PORT = Number(process.env["E2E_PORT"] ?? 5173);
const INTEGRATION_PORT = Number(process.env["E2E_INTEGRATION_PORT"] ?? 4174);
const ENGINE_PORT = Number(process.env["E2E_ENGINE_PORT"] ?? 8011);
const ENGINE_URL = process.env["E2E_ENGINE_URL"] ?? `http://localhost:${ENGINE_PORT}`;
const DATA_ROOT = process.env["E2E_DATA_ROOT"] ?? "workflow/data-e2e";

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
  projects: [
    {
      name: "chromium",
      testIgnore: "integration/**",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "integration",
      testMatch: "integration/**/*.spec.ts",
      // The pipeline runs for real, so these are slower than a screen test.
      timeout: 240_000,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: `http://localhost:${INTEGRATION_PORT}`,
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
        video: "retain-on-failure",
      },
    },
  ],
  webServer: [
    {
      command: `npx vite dev --port ${PORT} --strictPort`,
      url: `http://localhost:${PORT}/sign-in`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: { VITE_API_BASE_URL: "http://localhost:8201" },
    },
    {
      // The engine under test: stub ingest, isolated data root. Its configuration
      // must already be published into that root (npm run config:publish).
      command: `.venv/bin/uvicorn engine.api:app --port ${ENGINE_PORT}`,
      url: `${ENGINE_URL}/api/health`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        CREDITIQ_DATA_ROOT: DATA_ROOT,
        CREDITIQ_INGEST: "stub",
        // The integration frontend is not on a default port, so its origin has
        // to be allowed explicitly (engine/api.py CORS).
        CREDITIQ_FRONTEND_ORIGINS: `http://localhost:${INTEGRATION_PORT},http://127.0.0.1:${INTEGRATION_PORT}`,
      },
    },
    {
      command: `npx vite dev --port ${INTEGRATION_PORT} --strictPort`,
      url: `http://localhost:${INTEGRATION_PORT}/sign-in`,
      reuseExistingServer: true,
      timeout: 120_000,
      env: { VITE_API_BASE_URL: ENGINE_URL },
    },
  ],
});
