import { describe, expect, it } from "vitest";
import { satz, sekunden, zeilen, zellenKlasse } from "./zeiten";

const k = (extra = {}) => ({ anzahl: 1, mittel_s: null, median_s: null, max_s: null, letzter_s: null, ziel_s: null, ueber_ziel: false, langsamster_run_id: null, langsamster_trace_url: null, ...extra });
const KEYS = ["hochladen", "lesen", "maschine", "steckbrief", "modell", "zusammenfassung", "fertig"];
const zeiten = (laeufe = 3, schritte: Record<string, ReturnType<typeof k>> = {}) => ({
  laeufe,
  schritte: Object.fromEntries(KEYS.map((key) => [key, schritte[key] ?? k()])),
  gesamt: k(),
  fragen: k(),
});

describe("zeiten", () => {
  it("liefert Zeilen in Schrittreihenfolge, dann Gesamt und Fragen", () => {
    expect(zeilen(zeiten()).map((z) => z.label)).toEqual(["Hochladen", "Lesen je Dokument", "Maschine anlegen", "Steckbrief", "Maschinenmodell", "Zusammenfassung", "Fertig", "Gesamt je Lauf", "Je Frage (Schritt 6)"]);
  });
  it("verträgt einen fehlenden Schritt", () => {
    const z = zeiten();
    delete z.schritte.lesen;
    const lesen = zeilen(z).find((r) => r.key === "lesen");
    expect(lesen?.kennzahl.anzahl).toBe(0);
    expect(lesen?.kennzahl.median_s).toBeNull();
    expect(satz({ ...z, schritte: {} })).toContain("Noch keine Zeiten");
  });
  it("formatiert Sekunden deutsch", () => {
    expect(sekunden(12.34)).toBe("12,3 s");
    expect(sekunden(null)).toBe("–");
  });
  it("färbt Überschreitungen nur über Tokens", () => {
    expect(zellenKlasse(true)).toContain("text-danger");
    expect(zellenKlasse(true)).toContain("bg-error-soft");
    expect(zellenKlasse(false)).not.toContain("text-danger");
    expect(zellenKlasse(false)).not.toContain("bg-error-soft");
  });
  it("nennt den Satz ohne Läufe", () => {
    expect(satz(zeiten(0))).toBe("Noch keine Läufe");
  });
  it("nennt den langsamsten Schritt nach Median, bei Gleichstand den ersten", () => {
    expect(satz(zeiten(5, { lesen: k({ median_s: 48 }), modell: k({ median_s: 48 }), fertig: k({ median_s: 2 }) }))).toBe("Langsamster Schritt der letzten 5 Läufe: Lesen je Dokument, im Median 48,0 s");
  });
});
