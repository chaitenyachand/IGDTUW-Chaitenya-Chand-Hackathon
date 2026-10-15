import { defineConfig } from "@playwright/test";

/**
 * Visual regression suite for the landing story scenes.
 * Run against the dev server: `bun run test:visual` (update baselines with `bun run test:visual:update`).
 */
export default defineConfig({
  testDir: "tests/visual",
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}/{arg}{ext}",
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.015, animations: "disabled", caret: "hide" } },
  use: { baseURL: process.env["BASE_URL"] ?? "http://localhost:8080", deviceScaleFactor: 1 },
  webServer: {
    command: "bun run dev",
    url: "http://localhost:8080",
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 1800 } } },
    { name: "laptop", use: { viewport: { width: 1141, height: 710 } } },
    {
      name: "mobile",
      use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
    {
      name: "reduced-motion",
      use: { viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" },
    },
  ],
});
