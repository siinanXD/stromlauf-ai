# Agent-Testnutzer Stromlauf AI (SIN-1102)

Status: umgesetzt im Code, Aktivierung offen. Vorlage: SIN-913 (Leitstand).

## Entscheidung

- **Anmeldung** ist hier ein eigener Magic-Link mit JWT (`backend/app/api/auth.py`), kein Supabase. Die Schritte
  `auth.admin.createUser/generateLink/verifyOtp` aus dem Auftrag werden deshalb auf `POST /api/auth/magic-link` und
  `POST /api/auth/exchange` abgebildet. Das Konto entsteht beim ersten Tausch von selbst, das ist idempotent.
- **Kein neues Secret.** Die Adresse steht in `AGENT_TEST_EMAIL` (Repo-Variable, kein Geheimnis). Der Helfer
  `frontend/src/lib/agent-testnutzer/session.ts` baut daraus den Playwright-`storageState` (localStorage `stromlauf.token`),
  nur im Speicher des Jobs, nie als Artefakt.
- **Nur lesend.** Ist die Anmelde-Adresse gleich `AGENT_TEST_EMAIL`, bekommt das JWT die Rolle `agent`. Die Middleware
  (`app/auth.py::agent_may`) antwortet auf alles ausser GET/HEAD/OPTIONS mit 403. Das Konto ist nie `admin`.
  Folge: auch der Chat (`POST /api/chat`) ist für das Konto gesperrt; der Smoke öffnet nur Seiten.

## Voraussetzung und Risiko

Der Helfer holt den Link aus der Antwort (`dev_link`). Das geht nur mit `AUTH_DEV_LINK=true` auf dem Backend, und dann
kann jeder für jede Adresse einen Link abrufen. Nur für Test-/Staging-Backends mit eigener Datenbank einschalten, nie
in Produktion. Für Produktion bräuchte es einen anderen Weg (zum Beispiel ein nur für den Job gültiges, kurzes JWT mit
`JWT_SECRET`, das wäre ein neues Secret im Workflow) – Entscheidung beim Owner.

## Offen

- Kennzahlen (Punkt 4 im Auftrag): Testdaten des Kontos filtern. Dieses Repo hat keine Nutzungs-Kennzahlen pro Nutzer
  (`/api/costs` ist Modellkosten), deshalb nicht umgesetzt; `AGENT_TEST_EMAIL` ist der Filterschlüssel, sobald es sie gibt.
- Aktivierung: Repo-Variable `AGENT_TEST_EMAIL` setzen, Workflow ergänzen (`.github/` darf der Agent nicht ändern),
  Probe in `docs/abnahme.yml` (Datei existiert in diesem Repo nicht).
