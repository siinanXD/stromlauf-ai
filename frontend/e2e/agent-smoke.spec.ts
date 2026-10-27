import { expect, test } from "@playwright/test";

import { buildStorageState, type StorageState } from "../src/lib/agent-testnutzer/session";

/**
 * Smoke des Agent-Testnutzers (SIN-1102): Startseite eingeloggt. Laeuft nur mit E2E_API_URL und AGENT_TEST_EMAIL
 * (das Backend braucht AUTH_DEV_LINK=true und dieselbe AGENT_TEST_EMAIL); die Sitzung lebt nur im Speicher.
 */
const API = process.env.E2E_API_URL;
const EMAIL = process.env.AGENT_TEST_EMAIL;
const BASE_URL = process.env.E2E_BASE_URL || "http://localhost:3100";

test.describe("Agent-Testnutzer", () => {
  test.skip(!API || !EMAIL, "E2E_API_URL oder AGENT_TEST_EMAIL nicht gesetzt");
  let state: StorageState;

  test.beforeAll(async () => {
    state = await buildStorageState({ apiUrl: API!, baseUrl: BASE_URL, email: EMAIL! });
  });

  test("oeffnet die Startseite eingeloggt", async ({ browser }) => {
    const context = await browser.newContext({ storageState: state, baseURL: BASE_URL });
    const page = await context.newPage();
    await page.goto("/");
    await expect(page).not.toHaveURL(/\/login/);
    await context.close();
  });
});
