# Demo vom eigenen PC

Die öffentliche Demo läuft so: Das **Backend** (mit Datenbank und der Beispielmaschine FB-01) läuft in Docker auf dem
eigenen PC, ein **Tunnel** macht nur Port 8010 aus dem Internet erreichbar, das **Frontend** liegt auf Vercel und
spricht über `NEXT_PUBLIC_API_URL` mit dem Tunnel. Es fällt kein Hosting-Geld an (Hintergrund: SIN-1251). Die
verworfene Cloud-Variante (Railway) steht nicht mehr im Repo-Ablauf.

Stand der Anleitung: 2026-11-05. Was am echten PC noch nicht ausgeführt wurde, steht unter „Nicht getestet“.

## Was öffentlich erreichbar ist

- Nur das Backend, nur Port 8010, nur über den Tunnel. Alle Ports von `docker-compose.public.yml` liegen auf
  `127.0.0.1`: Datenbank (5433), Frontend-Container (3100) und Backend (8010) sind im Heim- oder Firmennetz nicht sichtbar.
- Das Backend läuft mit `DEMO_MODE=true`: Alle schreibenden Aufrufe unter `/api` liefern 403 (Upload, Löschen,
  Änderungen). Offen bleiben nur `/api/chat`, die Belegprüfung und der Login-Fluss. Je IP gilt ein Rate-Limit
  (`DEMO_RATE_LIMIT`, `DEMO_CHAT_RATE_LIMIT`, Antwort 429). Hinter dem Tunnel zählt `DEMO_TRUST_PROXY=true` die IP
  aus `X-Forwarded-For`.
- `ANTHROPIC_API_KEY` ist im Container leer gesetzt. Es kann also kein Modellaufruf Guthaben verbrauchen, auch wenn in
  der lokalen `.env` ein Schlüssel steht.
- Ohne `API_KEY` ist die API für jeden mit der Adresse lesbar. Das ist hier gewollt, weil die Instanz nur die
  öffentliche Beispielmaschine FB-01 enthält. **Deshalb darf hinter dem Tunnel nie die Entwicklungsdatenbank hängen**
  (siehe „Neben dem Entwicklungs-Stack“).

## Variablen

| Variable | Wo | Wert | Ein Schlüssel? |
| --- | --- | --- | --- |
| `CORS_ORIGINS` | Backend (`.env` im Repo-Wurzelordner) | `https://stromlauf-ai.vercel.app` (genau die Frontend-Adresse, ohne `/` am Ende; mehrere kommagetrennt) | nein |
| `NEXT_PUBLIC_API_URL` | Vercel, Projekt `stromlauf-ai`, Umgebung Production | `https://<adresse>` (Tunnel-Adresse, ohne `/` am Ende) | nein |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `VOYAGE_API_KEY` | nur lokale `.env` | – | **ja, nie in Vercel** |
| `API_KEY`, `JWT_SECRET`, `SMTP_URL`, `LANGFUSE_SECRET_KEY` | nur lokale `.env` | – | **ja, nie in Vercel** |

Regeln:

- **Alles mit dem Präfix `NEXT_PUBLIC_` steht im Frontend-Bundle und ist für jeden lesbar.** Deshalb gehört dort nur
  die Tunnel-Adresse hin. `NEXT_PUBLIC_API_KEY` bleibt in Vercel leer oder ungesetzt; die Demo braucht keinen
  API-Schlüssel, weil sie nur lesend ist.
- `NEXT_PUBLIC_API_URL` wird beim **Build** in das Frontend geschrieben. Nach einer Änderung in Vercel muss neu
  deployt werden („Redeploy“ am letzten Production-Deployment), sonst nutzt die Seite die alte Adresse.
- `CORS_ORIGINS` erlaubt nur die Production-Adresse. Preview-Adressen von Vercel (`…-git-<branch>-….vercel.app`)
  werden vom Backend abgelehnt, bis man sie zusätzlich einträgt; für die öffentliche Demo ist das so gewollt.
- In `.env.example` stehen alle Namen ohne Werte. Echte Werte, auch die Tunnel-Adresse, gehören in keine Datei im Repo.

## Start

Voraussetzung: Docker Desktop läuft. Im Repo-Wurzelordner, in der `.env` steht `CORS_ORIGINS=https://stromlauf-ai.vercel.app`:

```powershell
docker compose -f docker-compose.yml -f docker-compose.public.yml --profile demo up --build -d
```

Der erste Start baut die Images (der Backend-Healthcheck wartet bis zu etwa 5 Minuten). FB-01 legt das Backend beim
Start im Hintergrund an; es erscheint kurz danach in `/werk/maschinen`. Prüfen, ob das Backend antwortet:

```powershell
curl http://127.0.0.1:8010/api/health
```

Den Frontend-Container braucht die Demo nicht (das Frontend liegt auf Vercel). Wer ihn sparen will, startet nur
`backend` (die Datenbank startet als Abhängigkeit mit): `… --profile demo up --build -d backend`.

### Neben dem Entwicklungs-Stack

Auf Sinans PC läuft die Entwicklungsdatenbank `stromlauf-db` (Compose-Projekt `stromlaufai`, Port 5433 auf allen
Adressen) dauerhaft; sie startet mit Docker Desktop (gelesen am 2026-11-05 mit `docker ps` und `docker inspect`).
Der Befehl oben würde damit kollidieren (nicht ausgeführt, abgeleitet aus den Compose-Dateien):

- `docker-compose.yml` vergibt feste Containernamen (`stromlauf-db`, `stromlauf-backend`, `stromlauf-frontend`). Ein
  zweiter Start aus einem anderen Compose-Projekt scheitert am Namen.
- Dev-Backend (`uvicorn` auf 8010) und Demo-Backend wollen beide Port 8010. Ein zweites Programm auf 8010 scheitert still.
  Vor dem Start prüfen: `Get-NetTCPConnection -LocalPort 8010 -State Listen`.
- Die Demo darf **nicht** gegen die Dev-Datenbank laufen: Sie würde dann alle Entwicklungsdaten öffentlich lesbar machen.

Deshalb gilt: Die Demo bekommt ein eigenes Compose-Projekt und eine eigene Datenbank. Dazu eine Override-Datei
**außerhalb des Repos** (zum Beispiel `C:\Dev\demo\compose.override.yml`), die eigene Containernamen setzt und den
Datenbank-Port nicht veröffentlicht:

```yaml
services:
  db:
    container_name: stromlauf-demo-db
    ports: !reset []
  backend:
    container_name: stromlauf-demo-backend
  frontend:
    container_name: stromlauf-demo-frontend
```

```powershell
docker compose -p stromlauf-demo -f docker-compose.yml -f docker-compose.public.yml -f C:\Dev\demo\compose.override.yml --profile demo up --build -d backend
```

Das Dev-Backend auf 8010 muss dafür gestoppt sein (oder die Demo bekommt einen anderen Host-Port und der Tunnel zeigt
darauf). Die Dev-Datenbank wird dabei nicht angefasst und nie gestoppt: Andere Sitzungen arbeiten mit ihr.
Ein dauerhafter Weg ohne Override-Datei (Projektname und Containernamen in `docker-compose.public.yml`) ist als
Folgearbeit offen.

## Stopp

```powershell
docker compose -f docker-compose.yml -f docker-compose.public.yml --profile demo down
```

(bei der Variante mit eigenem Projekt dieselben `-p` und `-f` wie beim Start). Ohne `-v`: Die Volumes mit Datenbank und
Uploads bleiben erhalten, ein späterer Start findet FB-01 wieder. Mit `-v` werden sie gelöscht; dann legt das Backend
FB-01 beim nächsten Start neu an.

Die Container haben keine Neustart-Regel (`restart:` fehlt in den Compose-Dateien). Nach einem Neustart des PCs läuft
die Demo also nicht von selbst; der Startbefehl muss erneut laufen.

## Tunnel

### Weg 1: Tailscale Funnel (Standard)

Tailscale ist auf dem PC installiert, es kostet nichts und braucht keine neue Software. Funnel erlaubt als öffentliche
Ports nur 443, 8443 und 10000. Einschalten im Hintergrund, Beispiel mit Port 10000:

```powershell
tailscale funnel --bg --https=10000 8010
tailscale funnel status
```

`tailscale funnel status` nennt die öffentliche Adresse (`https://<adresse>:10000`). Das ist der Wert für
`NEXT_PUBLIC_API_URL`. Ausschalten für einen einzelnen Port: Syntax mit `tailscale funnel --help` und der Tailscale-Doku prüfen (hier nicht
getestet). **Nicht** `tailscale funnel reset` nehmen: Das löscht die ganze Funnel-Konfiguration, auch den Prüflauf auf 8443.

Hinweise zum Port:

- Ein Port gehört immer zu genau einem Ziel. Wer `--https=<port>` auf einem schon genutzten Port setzt, **ersetzt** das
  bisherige Ziel. Vorher mit `tailscale funnel status` und `tailscale serve status` nachsehen.
- Am 2026-11-05 war am PC belegt: 8443 (Funnel, Ziel ist ein Prüflauf auf 127.0.0.1:8020, nicht anfassen), 443 (nur im
  Tailnet, Ziel 127.0.0.1:3103) und 10000 (nur im Tailnet, Ziel 127.0.0.1:8010). Für die Demo bietet sich 10000 an; das
  Ziel 8010 stimmt dort schon, es fehlt nur der Funnel.
- Funnel muss in der Tailscale-Verwaltung für den Rechner erlaubt sein (siehe die Tailscale-Doku „Funnel“). Auf 8443
  ist es nachweislich an (`tailscale funnel status`).

Prüfen, von außerhalb des Tailnets (zum Beispiel Handy im Mobilfunknetz, ohne Tailscale):

```powershell
curl https://<adresse>:10000/api/health
```

Erwartet wird eine JSON-Antwort mit HTTP 200.

### Weg 2: Cloudflare Tunnel (falls Funnel für den Port nicht geht)

Kostenlos, braucht aber `cloudflared` (nicht installiert) und ein Cloudflare-Konto. Ein „Quick Tunnel“ braucht kein
Konto, ändert aber bei jedem Start die Adresse; dann müsste `NEXT_PUBLIC_API_URL` jedes Mal neu gesetzt und das
Frontend neu deployt werden. Für die Demo taugt deshalb nur ein benannter Tunnel mit fester Adresse (Cloudflare-Doku
„Create a locally-managed tunnel“, Ziel `http://127.0.0.1:8010`); er ist hier nicht durchgespielt. Zum Ausprobieren:
`cloudflared tunnel --url http://127.0.0.1:8010` (die ausgegebene Adresse ist `<adresse>`, gilt bis zum Beenden). Installieren braucht Sinans
Freigabe (`docs/bestand/pc.md` in leitstand-2).

## Vercel einstellen

1. Vercel, Projekt `stromlauf-ai`, Settings, Environment Variables: `NEXT_PUBLIC_API_URL` = `https://<adresse>` für
   Production.
2. Deployments, letztes Production-Deployment, „Redeploy“ (die Variable wird erst beim Build wirksam).
3. Die Seite öffnen, Maschinenübersicht (`/werk/maschinen`) zeigt FB-01.

## Wenn der PC aus ist

Der Tunnel hat dann kein Ziel, das Frontend auf Vercel bleibt erreichbar, aber jeder API-Aufruf scheitert. Die Seite soll
dann eine Fehlermeldung zeigen und **nicht** einen leeren Zustand wie „Keine Maschinen“ (SIN-1522, Pull Request #205).
Solange dieser PR nicht gemergt ist, ist offen, was die Seite zeigt; das gehört zur Prüfung nach dem Merge.

## Nicht getestet (Stand 2026-11-05)

- Der Startbefehl wurde nicht ausgeführt (kein Image-Build, kein Healthcheck). Geprüft ist nur, dass die Compose-Dateien
  die Dienste `db`, `backend`, `frontend` liefern (`docker compose … config --services`).
- Der Funnel wurde nicht geändert; `tailscale funnel status` und `tailscale serve status` wurden nur gelesen.
- Ob Funnel `X-Forwarded-For` setzt (nötig für das Rate-Limit je IP mit `DEMO_TRUST_PROXY=true`): nicht geprüft.
- Cloudflare-Weg, Verhalten bei ausgeschaltetem PC und Neustart-Verhalten der Container: nicht geprüft.
- Der einmalige Handgriff am PC und in Vercel ist SIN-1575.
