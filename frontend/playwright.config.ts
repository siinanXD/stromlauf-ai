import { defineConfig, devices } from "@playwright/test";

/**
 * E2E gegen das gebaute Frontend mit gemockter API (e2e/api-mock.ts): drei Breiten aus docs/product/ux-spec.md §4.
 * Lokal: `npx playwright test` (nutzt einen laufenden Dev-Server auf 3100, sonst startet es einen).
 * Gegen ein echtes Backend (e2e/staging.spec.ts): E2E_API_URL setzt die API des lokalen Servers; mit E2E_BASE_URL
 * (z. B. Vercel-Preview) wird kein Server gestartet.
 */
const PORT = 3100;
const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${PORT}`;
const API_URL = process.env.E2E_API_URL || "http://localhost:8010";
const executablePath = process.env.PW_CHROMIUM || undefined;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    launchOptions: executablePath ? { executablePath } : undefined,
  },
  projects: [
    { name: "mobile-390", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } },
    { name: "tablet-768", use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 } } },
    { name: "desktop-1440", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: process.env.CI ? `npm run build && npm run start -- -p ${PORT}` : `npm run dev -- -p ${PORT}`,
        url: `http://localhost:${PORT}/login`,
        reuseExistingServer: !process.env.CI,
        timeout: 240_000,
        env: { NEXT_PUBLIC_API_URL: API_URL },
      },
});
