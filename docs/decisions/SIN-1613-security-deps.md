# Sicherheits-Patch Next.js/sharp (SIN-1613)

Status: Lockfile aktualisiert, lokal zweimal geprueft (Implementierung und unabhaengiger Nachlauf), OSV-Nachscan liegt vor.

## Entscheidung

- `next` und `eslint-config-next` von `16.3.6` auf `16.4.6` (npm-Tag `latest` am 2026-11-10, gleiche Major-Version).
  Die 16.3-Linie endet bei `16.3.8` (2026-09-30) und verlangt weiter `sharp ^0.35.4`; erst `16.4.6` verlangt
  `sharp ^0.35.5`. Ziel laut Auftrag: GHSA-2464-fhr4-w9xw und GHSA-673q-mjm6-r5xr (Critical fuer 16.3.6).
- Lockfile: `sharp` und alle `@img/sharp-*` auf `0.35.5`, `@img/sharp-libvips-*` auf `1.3.4`, darunter
  `@img/sharp-linux-x64` fuer das glibc-Image `node:22-slim`. Sonst bewegt sich nur `sharp/node_modules/semver`
  (`7.8.5` -> `7.8.6`). Kein Paket kommt hinzu oder faellt weg.
- Unveraendert: `shadcn` (liefert `shadcn/tailwind.css` fuer `globals.css`), ESLint 9, Dockerfile, Backend.
- Laut `next/dist/docs/01-app/02-guides/upgrading/version-16.md` entfernt 16.4 nur `experimental.appNewScrollHandler`;
  das Frontend setzt keine Experimental-Flags. Node `>=20.9.0` passt zu `node:22-slim`.

## Geprueft (lokal, ohne Netzdienste der App)

- `npm ls --all` ohne Fehler; `next@16.4.6`, `eslint-config-next@16.4.6`, `sharp@0.35.5`.
- `npm run lint`: 0 Fehler, 2 Warnungen (`session.test.ts` unbenutztes `_init`; `lib/auth.ts:46`
  `@next/next/no-location-assign-relative-destination`).
- `npm test -- --maxWorkers=1`: 32 Dateien, 219 Tests gruen.
- `npm run build`: gruen, inklusive des TypeScript-Schritts von `next build`. Ein eigener Aufruf `tsc --noEmit`
  war in dieser Sitzung nicht freigegeben.

## Unabhaengiger Nachlauf (10.11.2026, zweite Sitzung, gleicher Checkout)

- `npx tsc --noEmit`: Exit 0, keine Fehler (in der ersten Sitzung nicht freigegeben, hier nachgeholt).
- `npm run lint`: 0 Fehler, 2 Warnungen. `npm test -- --maxWorkers=2`: 32 Dateien, 219 Tests gruen.
- `npm run build`: gruen, 8 Routen.
- `npm ls`: `next@16.4.6`, `eslint-config-next@16.4.6`, `sharp@0.35.5`.

## OSV-Nachscan (OSV-Scanner 2.7.1, nur `frontend/package-lock.json`)

Vorher (Audit, master `84d3cef`): 48 Vorkommen, davon 2 Critical. Nachher: **37 Vorkommen in 16 Paketen,
0 Critical, 13 High, 20 Medium, 4 Low**. `next` und `sharp` tauchen nicht mehr auf; damit sind
GHSA-2464-fhr4-w9xw und GHSA-673q-mjm6-r5xr im Lockstand geschlossen.

Verbleibende Pakete nach Herkunft (`npm ls <paket> --all`):

| Herkunft | Betroffene Pakete | Einsatz | Naechster Schritt |
| --- | --- | --- | --- |
| `shadcn` (dependencies) | `@modelcontextprotocol/sdk`, `hono`, `@hono/node-server`, `undici`, `body-parser`, `qs`, `fast-uri`, `ip-address`, `deepmerge`, `systeminformation`, `zod`, `minimatch` | Die App importiert aus `shadcn` nur `shadcn/tailwind.css` (`src/app/globals.css`). Der CLI-/MCP-Code wird nicht geladen. Die Pakete liegen aber im Laufzeit-Image, weil das Dockerfile `node_modules` vollstaendig kopiert. | Eigenes Issue: `shadcn` aus dem Laufzeit-Image heraushalten (z. B. `npm ci --omit=dev` in der Laufzeitstufe und `shadcn` als devDependency, oder die CSS-Datei ins Repo uebernehmen). Aendert Dockerfile und Build, deshalb nicht Teil dieses Patches. |
| `vitest` (devDependencies) | `vite`, `@vitest/mocker` | Nur Tests, lokal und in CI. | Mit dem naechsten Vitest-Update. |
| `eslint`, `eslint-config-next` (devDependencies) | `minimatch`, `zod` | Nur Lint. `minimatch` 10.2.6: Korrektur erst in 11.0.1, die Werkzeuge verlangen `^10`. | Warten auf Upstream. |
| `next`, `@tailwindcss/postcss` | `source-map-js` 1.2.1 | Build. | Laesst sich innerhalb der Spanne anheben (`npm update source-map-js`); hier nicht getan, um den Patch auf Next/sharp zu begrenzen. |

Keines der verbleibenden Vorkommen ist als ausnutzbar nachgewiesen; die Einordnung beruht auf dem Importpfad,
nicht auf einer Aufrufanalyse. Backend-Abhaengigkeiten (Python) sind von diesem Scan nicht erfasst.

## Offen

- Unabhaengiges Review und GitHub-CI auf dem PR.
- Folge-Issue fuer `shadcn` im Laufzeit-Image (siehe Tabelle).
- Lint-Warnung in `lib/auth.ts:46` (ob sie erst mit 16.4.6 kommt, ist nicht geprueft): eigenes kleines Issue,
  nicht Teil dieses Patches.
