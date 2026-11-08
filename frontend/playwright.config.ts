import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "dashboard.spec.ts",
  outputDir: "../tests/playwright-results",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5174", headless: true, channel: "chrome" },
  reporter: "list",
  timeout: 120000,
  webServer: [
    {
      command:
        "uv run --project .. --extra api uvicorn multigas.api.app:create_app --factory --host 127.0.0.1 --port 8002 --workers 1 --no-access-log",
      url: "http://127.0.0.1:8002/api/v1/health",
      env: { MULTIGAS_APP_DIR: "../tests/e2e-storage" },
      timeout: 120000,
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 5174 --strictPort",
      url: "http://127.0.0.1:5174",
      env: { MULTIGAS_API_TARGET: "http://127.0.0.1:8002" },
      timeout: 120000,
      reuseExistingServer: false,
    },
  ],
});
