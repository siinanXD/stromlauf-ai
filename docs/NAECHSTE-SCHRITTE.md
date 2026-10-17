# Nächste Schritte (SIN-821)

Stand: 2026-10-17. Grundlage: `docs/FERTIG.md` (Fertig-Liste und Lücken). Jeder Schritt ist als Linear-Issue im Backlog
gedacht (Projekt „Stromlauf AI“). Reihenfolge laut FERTIG.md: 1 und 3 zuerst, dann 4; 2 läuft parallel; 7 zuletzt.
Punkt 5 (Hosting) und 6 bleiben gesperrt, bis 1 bis 4 abgehakt sind.

## 1. Entscheidung Beispiel-Doku (Label `sinan`)

**Ziel:** Klären, ob die erfundene Anlage FB-01 (Stromlaufplan und AWL) als öffentliche Demo reicht, oder ob eine
weitere frei lizenzierte Anlage nötig ist. Festo-MPS-Dateien bleiben draußen (Lizenz verbietet Weitergabe).

**Fertig, wenn:** Sinan hat die Entscheidung im Issue festgehalten.

## 2. `docs/DATEN.md` und Demo-Daten festschreiben (FERTIG.md Punkt 1)

**Ziel:** Alle Dateien der Demo-Maschine mit Herkunft und Lizenz in `docs/DATEN.md` auflisten.

**Fertig, wenn:** `docs/DATEN.md` existiert, nennt je Datei Herkunft und Lizenz, und kein Fremdmaterial mit
Weitergabeverbot liegt im Repo. Abhängig von Schritt 1.

## 3. Demo-Modus im Backend (Punkt 3)

**Ziel:** Setting `DEMO_MODE`: keine Uploads, kein Löschen und Ändern, Rate-Limit je Besucher (IP) auf Chat und teure
Endpunkte, kein Login. Fertig indexierte Beispiel-Maschine beim Start.

**Fertig, wenn:** Backend-Tests belegen: Upload und Schreibzugriffe liefern 403 im Demo-Modus, das Rate-Limit greift
(429), Chat funktioniert weiter. `AGENTS.md` nennt die Einstellung.

## 4. `docker compose up` startet die ganze Demo (Punkt 4, Teil 1)

**Ziel:** Frontend-Dockerfile und Compose-Dienste für Backend, Frontend und DB mit der Beispiel-Maschine im Demo-Modus.

**Fertig, wenn:** `docker compose up` auf einer sauberen Maschine zeigt unter `http://localhost:3100` die
Maschine mit beantwortbarem Chat; der Container-Build läuft in CI grün. Abhängig von Schritt 3.

## 5. Playwright-Test mit 10 Fragen, 3 Läufe in Folge (Punkt 4, Teil 2)

**Ziel:** E2E-Test gegen den Compose-Stack (nicht gemockt): 10 Fragen, geprüft werden Antwort und Quelle.

**Fertig, wenn:** Der Test ist als CI-Job grün, 3 Läufe hintereinander. Abhängig von Schritt 4.

## 6. Eval-Gate auf dem ganzen Set (Punkt 2, Label `sinan` für Freigabe der Token-Kosten)

**Ziel:** Der Agentenlauf deckt alle 69 Fragen ab (aktuell nur FB-01 und Injection, wöchentlich) und prüft
„richtig mit Quelle“ ≥ 80 %. Kosten bei etwa 0,046 USD je Antwort mit Sonnet 5.5 grob 3 USD je Lauf; Sinan gibt sie frei.

**Fertig, wenn:** Ein CI-Lauf über alle 69 Fragen ist belegt und das Gate `--min 0.8` hält.

---

Aufgaben, die nur Sinan erledigen kann: Schritt 1 und die Kostenfreigabe in Schritt 6 (Label `sinan`).
Schritt 7 (README-Auftritt) folgt, sobald 3 bis 5 stehen.
