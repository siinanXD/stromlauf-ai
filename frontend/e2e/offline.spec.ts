import { expect, test } from "@playwright/test";

/**
 * Backend nicht erreichbar (SIN-1522): jede API-Anfrage scheitert wie das 502/CORS der oeffentlichen Seite.
 * Erwartet: Fehler statt Leerzustand, kein Knopf, der scheitern muss, und die Erklaerung, was das Produkt ist.
 */
test.beforeEach(async ({ page }) => {
  await page.route(/\/api\//, (route) => route.abort("failed"));
});

test("Startseite zeigt den Fehler und erklaert das Produkt", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("produkt-erklaerung")).toContainText("Chatbot für die Instandhaltung");
  await expect(page.getByTestId("chat-notice")).toContainText("Keine Verbindung zum Server");
  await expect(page.getByText("Backend nicht erreichbar")).toBeVisible();
  await expect(page.getByLabel(/Frage zur Anlage stellen/)).toBeDisabled();
  await expect(page.getByLabel("Senden")).toBeDisabled();
  await expect(page.getByLabel("Wissensquelle anlegen")).toBeDisabled();
  // kein falscher Leerzustand, kein Knopf der scheitern muss
  await expect(page.getByText("Noch keine Maschine")).toHaveCount(0);
  await expect(page.getByTitle("Maschine hinzufügen")).toHaveCount(0);
});

test("Maschinenuebersicht zeigt den Fehler statt 'Noch keine Maschinen'", async ({ page }) => {
  await page.goto("/werk/maschinen");
  await expect(page.getByTestId("maschinen-fehler")).toContainText("Die Maschinenübersicht ist nicht verfügbar");
  await expect(page.getByText("Noch keine Maschinen")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Aus Dokumentation anlegen/ })).toHaveCount(0);
});
