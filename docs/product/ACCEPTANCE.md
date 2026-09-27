# Machine Assistant v1 — Abnahme-Kandidat (Entwurf)

Stand: wird mit jedem Merge fortgeschrieben; die Staging-Spalten füllen sich, sobald das Backend auf Railway
läuft (Freigabe des Owners, kostenpflichtig). Bis dahin gilt: **Preview (Vercel) + CI-Evidenz**, kein Label.

| Feld | Wert |
| --- | --- |
| Git-SHA (master) | _wird beim Setzen des Labels eingetragen_ |
| PRs | #22 Spezifikation · #30 MB-0 · #31 MB-1 · #32 MB-2 · #33 MB-3 · #34 MB-4 · #35 MB-5 · MB-6 (dieser Stand) |
| Vercel-Preview | `stromlauf-ai-git-<branch>-siinanxds-projects.vercel.app` (je PR im Vercel-Kommentar) |
| Staging (Railway) | _ausstehend_ |
| Langfuse-Läufe | _ausstehend (Nightly `eval.yml` schreibt `eval:<lauf>`-Tags und Scores)_ |
| Gemessene Kosten | Anlegen FB-01: _ausstehend (Staging)_ · je Antwort: _ausstehend_; Schätzung laut `cost-model.md`: ≈ 2,4 $ / ≈ 0,02 $ |

## Akzeptanzzeilen aus `contract.md` §5

| # | Kriterium | Evidenz | Stand |
| --- | --- | --- | --- |
| 1 | Maschine anlegen, ≥ 3 Dokumente inkl. Stromlaufplan-PDF und Schaltschrankfoto; ≤ 300 Seiten in < 15 min; Kostenbuch zeigt die Kosten | `scripts/load_example.py` (6 Dokumente + Aufbauplan) im CI-Job „Retrieval-Gate“ (`eval.yml`); Kostenbuch `GET /api/machines/{id}/costs` (MB-3) | CI: Ingestion-Dauer aus dem Job-Log; Kostenzeilen erst mit Provider-Lauf (Staging) |
| 2 | Modell zeigt ≥ 5 Baugruppen und ≥ 20 Teile mit Kennzeichen, je ≥ 1 Zitat; Korrektur bleibt nach Re-Ingestion | `GET /api/machines/{id}/map` aus Stückliste + Index (MB-4); Hotspot-Korrektur `PATCH /api/hotspots` mit `origin=manual` (MB-5) | FB-01: Zonen +ST1/+FE1/Anlage, 14 gelabelte Hotspots; Zahl der Teile auf Staging prüfen |
| 3 | Golden-Set 20 Fragen: Groundedness ≥ 0,90, gültige Zitate ≥ 95 %, Referenzteil-Präzision ≥ 0,85 in CI | Retrieval-Gate (`run_retrieval.py --min 0.9 --min-sources 0.9`, FB-01) bei jedem PR; Nightly `run_eval.py --min 0.8 --max-cost` mit Langfuse-Scores | Retrieval-Gate erstmals grün: [Lauf 36360152510](https://github.com/siinanXD/stromlauf-ai/actions/runs/36360152510) (FB-01 mit bge-m3 in CI, Modellcache 3,2 GB); Agentenlauf: Nightly mit Secret |
| 4 | Referenzierte Teile werden im Modell markiert, Chips öffnen ein Sheet mit Datenblattseite | `meta`-Event + `SchemaMap` (MB-4), `PartSheet` (MB-5); Playwright `machine.spec.ts`, `part-sheet.spec.ts` | CI: E2E-Job grün |
| 5 | 10 gelabelte Schaltschrankteile: IoU ≥ 0,5 in ≥ 80 % | `eval/run_cabinet.py` gegen `07_Schaltschrank_Hotspots_FB-01.json` (14 Labels) | Nightly (ein Vision-Aufruf) |
| 6 | 5 Negativtests: keine Inhalte aus anderer Maschine/Workspace | `backend/tests/test_isolation_eval.py` (fünf Retrieval-Fragen über Workspaces) + `test_tenancy_isolation.py` | CI: Backend-Job grün |
| 7 | 390 px ohne horizontalen Scroll; Lighthouse Accessibility ≥ 90 | Playwright bei 390/768/1440 mit „kein Body-Scroll“ und axe WCAG 2 A/AA ohne Verstöße | CI: E2E-Job grün; Lighthouse-Lauf gegen Preview ausstehend |
| 8 | Jeder KI-Aufruf in Langfuse mit Modell, Tokens, Kosten, Maschine, Belegen | Kostenbuch `ai_call_ledger` (MB-3) + Langfuse-Callback (`app/tracing.py`) | Langfuse-Evidenz erst mit Provider-Lauf |

## Bekannte Grenzen (Stand dieses Entwurfs)

- Railway-Staging, Kaltstart- und Kostenmessung (MB-1/MB-3-Abnahme) warten auf die Freigabe des Owners.
- Planung und Leitstand (Nebenmodule) sind noch nicht workspace-scoped (`contract.md`, Known limitations).
- Kosten je Antwort erscheinen nur für live gestreamte Antworten; der Verlauf trägt keine Kosten.
- Figma enthält nur noch die Seite `Foundations`; Screens folgen `ux-spec.md`.

Label `READY FOR HUMAN ACCEPTANCE` wird erst gesetzt, wenn Staging läuft, die Nightly-Läufe grün sind und ein
unabhängiges Review ohne blockierende Findings vorliegt.
