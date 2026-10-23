import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { MACHINE_ID, mockApi } from "./api-mock";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("Tab SPS: Bausteine, Klartext und Warum-Baum, ohne Scroll und axe-Verstöße", async ({ page }, testInfo) => {
  await page.goto(`/werk/maschine/${MACHINE_ID}?bereich=aufbau&tab=sps`);
  await expect(page.getByRole("tab", { name: "SPS" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("navigation", { name: "Bausteine" })).toBeVisible();
  await expect(page.getByText("A4.0 ist an, wenn Taster Start (E0.0) und M1.0.")).toBeVisible();

  await page.getByRole("button", { name: /^OB 1/ }).click();
  await expect(page.getByText("Ruft FB 10 auf.")).toBeVisible();
  await page.getByRole("button", { name: /^FB 10/ }).click();

  await page.getByLabel("Ausgang für „Warum kommt … nicht?“").fill("A4.0");
  await page.getByRole("button", { name: "Warum?" }).click();
  const tree = page.getByTestId("why-tree");
  await expect(tree).toBeVisible();
  await expect(tree.locator('[data-why-network="FB10/NW1"]')).toBeVisible();
  await expect(tree.getByRole("button", { name: "-X1:5" }).first()).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations).toEqual([]);

  await page.screenshot({ path: testInfo.outputPath("sps-tab.png"), fullPage: true });
});

test("Tab SPS: unbekannter Ausgang nennt den Grund", async ({ page }) => {
  await page.goto(`/werk/maschine/${MACHINE_ID}?bereich=aufbau&tab=sps`);
  await page.getByLabel("Ausgang für „Warum kommt … nicht?“").fill("A9.9");
  await page.getByRole("button", { name: "Warum?" }).click();
  await expect(page.getByTestId("why-result")).toContainText("kommt im Programm nicht vor");
});
