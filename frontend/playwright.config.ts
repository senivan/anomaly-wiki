import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
const useExistingServer = process.env.PLAYWRIGHT_SKIP_WEBSERVER === "1";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  outputDir: "../e2e-artifacts/playwright-results",
  reporter: process.env.CI
    ? [
        ["html", { outputFolder: "../e2e-artifacts/playwright-report", open: "never" }],
        ["json", { outputFile: "../e2e-artifacts/frontend-e2e-results.json" }],
        ["github"],
        ["list"],
      ]
    : [
        ["html", { outputFolder: "../e2e-artifacts/playwright-report", open: "never" }],
        ["json", { outputFile: "../e2e-artifacts/frontend-e2e-results.json" }],
        ["list"],
      ],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  ...(useExistingServer
    ? {}
    : {
        webServer: {
          command: "mkdir -p ../e2e-artifacts && npm run start > ../e2e-artifacts/next.log 2>&1",
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          stdout: "pipe",
          stderr: "pipe",
        },
      }),
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium-mobile",
      grep: /@mobile/,
      use: { ...devices["Pixel 7"] },
    },
  ],
});
