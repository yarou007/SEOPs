import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "*.spec.ts",
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "https://localhost:3443",
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
  },
  reporter: "list",
});
