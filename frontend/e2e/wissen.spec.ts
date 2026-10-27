import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { MACHINE_ID, mockApi } from "./api-mock";

const BELEG = { document_id: "d1", filename: "01_Stromlaufplan_FB-01.pdf", page: 3 };
const note = (id: string, text: string, extra: Record<string, unknown> = {}) => ({
  id,
  machine_id: MACHINE_ID,
  text,
  quelle: "lauf",
  belege: [],
  gesperrt: false,
  run_id: null,
  conversation_id: null,
  created_at: "2026-10-26T10:00:00Z",
  ...extra,
});

test("Tab Wissen: Sätze ansehen, einen löschen, axe sauber", async ({ page }) => {
  await mockApi(page);
  let notes = [
    note("n1", "Der Motorschutz -F2 sichert -M1.", { quelle: "mensch", gesperrt: true, belege: [BELEG] }),
    note("n2", "Das Band wird von -K1 geschaltet.", { created_at: "2026-10-25T10:00:00Z" }),
  ];
  const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
  // spaeter registrierte Routen gelten zuerst
  await page.route(`**/api/machines/${MACHINE_ID}/notes**`, (route) => {
    const method = route.request().method();
    if (method === "DELETE") {
      notes = notes.filter((n) => n.id !== "n2");
      return route.fulfill({ status: 204 });
    }
    return route.fulfill(json(notes));
  });

  await page.goto(`/werk/maschine/${MACHINE_ID}?bereich=aufbau&tab=wissen`);
  const saetze = page.getByTestId("wissen-satz");
  await expect(saetze).toHaveCount(2);
  const erste = saetze.first();
  await expect(erste.getByLabel("gesperrt")).toBeVisible();
  await expect(erste).toContainText("01_Stromlaufplan_FB-01.pdf S. 3");
  await expect(erste).toContainText("Mensch");

  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axe.violations, JSON.stringify(axe.violations, null, 1)).toEqual([]);

  await saetze.nth(1).getByRole("button", { name: "Satz löschen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Löschen" }).click();
  await expect(saetze).toHaveCount(1);
});
