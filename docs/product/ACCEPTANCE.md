# Machine Assistant v1 — Abnahme-Kandidat (Entwurf)

Stand: wird mit jedem Merge fortgeschrieben; die Staging-Spalten füllen sich, sobald das Backend auf Railway
läuft (Freigabe des Owners, kostenpflichtig). Bis dahin gilt: **Preview (Vercel) + CI-Evidenz**, kein Label.

| Feld | Wert |
| --- | --- |
| Git-SHA (master) | _wird beim Setzen des Labels eingetragen_ |
| PRs | #22 Spezifikation · #30 MB-0 · #31 MB-1 · #32 MB-2 · #33 MB-3 · #34 MB-4 · #35 MB-5 · MB-6 (dieser Stand) |
| Vercel-Preview | `stromlauf-ai-git-<branch>-siinanxds-projects.vercel.app` (je PR im Vercel-Kommentar) |
| Staging (Railway) | _ausstehend_ |
| Abnahme-Nachweise (CI) | Job „Retrieval-Gate“ in `eval.yml`: `scripts/acceptance.py --load` (Kaltstart, Ingestion-Dauer, Modell, Kostenbuch, Schätzung) und `frontend/scripts/lighthouse-a11y.mjs` (Gate ≥ 90) gegen den Produktions-Build; Artefakt `abnahme-nachweise` je Lauf |
| Langfuse-Läufe | _ausstehend (Nightly `eval.yml` schreibt `eval:<lauf>`-Tags und Scores)_ |
| Gemessene Kosten | Anlegen FB-01: _ausstehend (Staging)_ · je Antwort: _ausstehend_; Schätzung laut `cost-model.md`: ≈ 2,4 $ / ≈ 0,02 $ |

## Akzeptanzzeilen aus `contract.md` §5

| # | Kriterium | Evidenz | Stand |
| --- | --- | --- | --- |
| 1 | Maschine anlegen, ≥ 3 Dokumente inkl. Stromlaufplan-PDF und Schaltschrankfoto; ≤ 300 Seiten in < 15 min; Kostenbuch zeigt die Kosten | `scripts/acceptance.py --load` lädt die 6 Dokumente + Aufbauplan wie `load_example.py`, misst Kaltstart und Ingestion-Dauer und liest `GET /api/machines/{id}/costs` (MB-3); im CI-Job „Retrieval-Gate“ (`eval.yml`), Ergebnis `acceptance_<zeit>.md` im Artefakt | CI: Dauer im Artefakt (FB-01 hat 7 PDF-Seiten, nicht 300); Kostenzeilen erst mit Provider-Lauf (Staging) |
| 2 | Modell zeigt ≥ 5 Baugruppen und ≥ 20 Teile mit Kennzeichen, je ≥ 1 Zitat; Korrektur bleibt nach Re-Ingestion | `GET /api/machines/{id}/map` aus Stückliste + Index (MB-4), Fundstelle je Teil über `GET /api/machines/{id}/tags/{tag}` (`scripts/acceptance.py`); Hotspot-Korrektur `PATCH /api/hotspots` mit `origin=manual` (MB-5) | Beispielanlage seit 2026-09-28 mit fünf Einbauorten: +ST1 Schaltschrank (11 Teile), +BP1 Bedienpult (7), +AN1 Antrieb (2), +SE1 Einlauf (1), +SA1 Auslauf (1); **22 Teile**, dazu 4 Leitungen -W1…-W4 als Verbinder, keine Zone „ohne Einbauort“ (nach Fix #38). Deterministisch nachgerechnet in `test_example_consistency.py` (Stückliste → Kennzeichen-Index → Modell); Wert auf laufender Umgebung im CI-Artefakt `abnahme-nachweise`. Offen: Korrektur bleibt nach Re-Ingestion (auf Staging zeigen) |
| 3 | Golden-Set 20 Fragen: Groundedness ≥ 0,90, gültige Zitate ≥ 95 %, Referenzteil-Präzision ≥ 0,85 in CI | Retrieval-Gate (`run_retrieval.py --min 0.9 --min-sources 0.9`, FB-01) bei jedem PR; Nightly `run_eval.py --min 0.8 --max-cost` mit Langfuse-Scores | Retrieval-Gate erstmals grün: [Lauf 36360152510](https://github.com/siinanXD/stromlauf-ai/actions/runs/36360152510) (FB-01 mit bge-m3 in CI, Modellcache 3,2 GB); Agentenlauf: Nightly mit Secret |
| 4 | Referenzierte Teile werden im Modell markiert, Chips öffnen ein Sheet mit Datenblattseite | `meta`-Event + `SchemaMap` (MB-4), `PartSheet` (MB-5); Playwright `machine.spec.ts`, `part-sheet.spec.ts` (gemockte API); `staging.spec.ts` ohne Mocks gegen ein echtes Backend: Login → Maschine → Modell → Bauteil-Sheet → Schaltschrankfoto, Frage nur mit `E2E_ASK=1` | CI: E2E-Job grün; `staging.spec.ts` lokal gegen das echte Backend grün am 2026-09-28 (390 px und 1440 px, ohne bezahlte Frage); Lauf gegen Preview + Staging offen |
| 5 | 10 gelabelte Schaltschrankteile: IoU ≥ 0,5 in ≥ 80 % | `eval/run_cabinet.py` gegen `07_Schaltschrank_Hotspots_FB-01.json` (15 Labels, seit -F3 im Aufbauplan) | Nightly (ein Vision-Aufruf) |
| 6 | 5 Negativtests: keine Inhalte aus anderer Maschine/Workspace | `backend/tests/test_isolation_eval.py` (fünf Retrieval-Fragen über Workspaces) + `test_tenancy_isolation.py` | CI: Backend-Job grün |
| 7 | 390 px ohne horizontalen Scroll; Lighthouse Accessibility ≥ 90 | Playwright bei 390/768/1440 mit „kein Body-Scroll“ und axe WCAG 2 A/AA ohne Verstöße; `frontend/scripts/lighthouse-a11y.mjs` (nur Kategorie Accessibility, mobil emuliert) als Gate ≥ 90 im Job „Retrieval-Gate“ gegen den Produktions-Build mit echten FB-01-Daten | CI: E2E-Job grün; Lighthouse **100** lokal am 2026-09-28 (Dev-Server, Maschinenansicht FB-01), CI-Wert im Artefakt `lighthouse-a11y.report.html`; Lauf gegen die Vercel-Preview braucht ein erreichbares Backend (Staging) |
| 8 | Jeder KI-Aufruf in Langfuse mit Modell, Tokens, Kosten, Maschine, Belegen | Kostenbuch `ai_call_ledger` (MB-3) + Langfuse-Callback (`app/tracing.py`) | Langfuse-Evidenz erst mit Provider-Lauf |

## Teil 2: Ablauf nach Freigabe des Railway-Stagings

Die Nachweise sind automatisiert; nach der Freigabe sind es sechs Schritte, jeder ohne Modellaufruf, außer wo es steht:

1. Railway-Service `backend` + Postgres/pgvector + Volume nach `README.md` („Deployment“). Für den E2E-Login auf Staging
   vorübergehend `AUTH_DEV_LINK=true` setzen (Link in der Antwort statt per Mail), danach wieder entfernen.
2. `python scripts/acceptance.py --api https://<railway> --load --out eval/results` → Kaltstart, Ingestion-Dauer, Modell
   (Baugruppen, Teile, Fundstellen), Hotspots, Kostenbuch. Zugriff über `STROMLAUF_API_KEY` oder `STROMLAUF_TOKEN`.
3. Kosten (Entscheidung des Owners, kostet Tokens): `python scripts/load_example.py --api https://<railway> --vision --refresh`,
   dann `scripts/acceptance.py` ohne `--load` → Schätzung gegen Kostenbuch je Zweck (±50 %), Kosten „Anlegen FB-01“.
4. Vercel: `NEXT_PUBLIC_API_URL` auf die Railway-Domain, Preview-URL notieren.
5. `E2E_BASE_URL=https://<preview> E2E_API_URL=https://<railway> E2E_EMAIL=<adresse> npx playwright test e2e/staging.spec.ts --project=desktop-1440`
   (Login → Maschine → Modell → Bauteil-Sheet → Schaltschrankfoto); mit `E2E_ASK=1` zusätzlich eine bezahlte Frage mit Markierung.
   `node frontend/scripts/lighthouse-a11y.mjs --base https://<preview> --api https://<railway>` (offenes Backend oder API-Key;
   Variante mit Login steht als TODO im Skript).
6. Secret `ANTHROPIC_API_KEY` im GitHub-Environment `eval` → Nightly-Lauf (Agenten-Eval, Schaltschrank-IoU) → Langfuse-Läufe
   verlinken. Werte oben eintragen, unabhängiges Review, Label `READY FOR HUMAN ACCEPTANCE`.

## Bekannte Grenzen (Stand dieses Entwurfs)

- Railway-Staging, Kaltstart- und Kostenmessung (MB-1/MB-3-Abnahme) warten auf die Freigabe des Owners.
- Kriterium 2 ist mit der erweiterten Beispielanlage rechnerisch erfüllt (5 Baugruppen, 22 Teile); der Wert auf einer
  laufenden Umgebung steht im CI-Artefakt und später auf Staging. Lokale Installationen laden die neuen Dokumente mit
  `python scripts/load_example.py --refresh` (Dokument-IDs ändern sich, alte Chat-Belege zeigen dann ins Leere).
  Reale Dokumentation ohne eigene Stücklisten-Datei bekommt seit #39 ein Modell aus dem Kennzeichen-Index (Zonen je
  Blatt mit Titel, Bezeichnungen von Stücklistenseiten in der PDF). Nachweis mit dem QElectroTech-Beispielprojekt
  (50 Seiten, eine PDF, Kennzeichen ohne Minus): 23 Blatt-Zonen, 105 Teile, davon 101 mit Bezeichnung, alle mit
  Fundstelle; Onboarding zählt 129 Betriebsmittel. Kein Schaltschrankfoto in dieser Doku, daher dort keine Hotspots.
- Planung und Leitstand (Nebenmodule) sind noch nicht workspace-scoped (`contract.md`, Known limitations).
- Kosten je Antwort erscheinen nur für live gestreamte Antworten; der Verlauf trägt keine Kosten.
- Figma enthält nur noch die Seite `Foundations`; Screens folgen `ux-spec.md`.

Label `READY FOR HUMAN ACCEPTANCE` wird erst gesetzt, wenn Staging läuft, die Nightly-Läufe grün sind und ein
unabhängiges Review ohne blockierende Findings vorliegt.
