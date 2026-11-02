# Drehbuch Screencast (ca. 60 s)

Nur FB-01 (`examples/foerderband`, erfundene Doku), kein Modellaufruf, keine Schluessel im Bild.
Aufnahme: `frontend/e2e/screencast.spec.ts`, Schnitt: `scripts/screencast.sh`.

| # | Schritt | Zeigt |
|---|---------|-------|
| 1 | `/werk/maschinen` | Maschinenuebersicht mit FB-01 |
| 2 | FB-01 oeffnen | Stoerfaelle der Maschine |
| 3 | Aufbau, Bauteil `-M1` | Steckbrief mit Wert und Quelle |
| 4 | SPS, „Warum kommt A4.0 nicht?“ | Rueckverfolgung bis zur Klemme |
| 5 | Signalweg ab `-S1` | Taster -> Klemme -> SPS -> `-K1` -> Motor `-M1` |

Ablauf:

```bash
docker compose --profile demo up --build            # warten, bis FB-01 gelesen ist
cd frontend && npx playwright install chromium
SCREENCAST=1 E2E_API_URL=http://localhost:8010 E2E_BASE_URL=http://localhost:3100 \
  npx playwright test e2e/screencast.spec.ts --project=desktop-1440
cd .. && bash scripts/screencast.sh                 # braucht ffmpeg
```

Der Link `sjcode.de/-K3` und der Upload liegen bei Sinan (SIN-1240).
