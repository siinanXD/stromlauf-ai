# Vergleich claude-sonnet-5 gegen gpt-5-mini-2025-08-07

| Kennzahl | claude-sonnet-5 | gpt-5-mini-2025-08-07 |
| --- | --- | --- |
| fragen | 9 | 9 |
| bewertet | 9 | 9 |
| nicht_bewertet_fehler | 0 | 0 |
| fakten_mittel | 1 | 0.95 |
| quellen_ok | 1 | 1 |
| sauber | 1 | 1 |
| werkzeug_ok | 0.8 | 0.6 |
| voll_bestanden | 8 | 6 |
| tokens_ein | 184125 | 161845 |
| tokens_aus | 12146 | 28767 |
| modellaufrufe | 27 | 38 |
| kosten_usd | 0.4897 | 0.0980 |
| kosten_je_antwort_usd | 0.0544 | 0.0109 |
| dauer_mittel_s | 18.1 | 43.2 |

## Fragen

| Frage | Fakten A / B | Quellen A / B | sauber A / B | Kosten A / B (USD) | Dauer A / B (s) | |
| --- | --- | --- | --- | --- | --- | --- |
| `fb01-e03` Was haengt an E0.3 und wo ist das im Plan? | 1 / 1 | ✓ / ✓ | ✓ / ✓ | 0.0540 / 0.0070 | 22.4 / 36.4 |  |
| `fb01-h2-20s` Warum leuchtet -H2 nach etwa 20 Sekunden Betrieb? | 1 / 1 | ✓ / ✓ | ✓ / ✓ | 0.0646 / 0.0159 | 28.6 / 68.1 |  |
| `fb01-motor-brummt` Der Motor brummt, dreht aber nicht. Welche Klemmen muss ich pruefen? | 1 / 0.8 | ✓ / ✓ | ✓ / ✓ | 0.0397 / 0.0141 | 15.5 / 46 | ≠ |
| `fb01-verriegelung` Wie ist -K1 gegen -K2 verriegelt? | 1 / 1 | ✓ / ✓ | ✓ / ✓ | 0.0633 / 0.0079 | 20.9 / 34.9 |  |
| `fb01-f2-typ` Welchen Typ hat -F2 und auf welchen Strom ist er eingestellt? | 1 / 1 | ✓ / ✓ | ✓ / ✓ | 0.0250 / 0.0037 | 5 / 23.4 |  |
| `fb01-s3` Was passiert, wenn -S3 gedrueckt wird? | 1 / 0.75 | ✓ / ✓ | ✓ / ✓ | 0.0738 / 0.0084 | 26.4 / 49.6 | ≠ |
| `fb01-nicht-vorhanden` Welche Profinet-Diagnoseadresse hat die SPS -A1 im Foerderband FB-01? | 1 / 1 | ✓ / ✓ | ✓ / ✓ | 0.0361 / 0.0233 | 9.4 / 55.8 |  |
| `fb01-m1-fact` Wo finde ich -M1 im Plan und an welchen Klemmen haengt der Motor? | 1 / 1 | ✓ / ✓ | ✓ / ✓ | 0.0637 / 0.0084 | 13.1 / 31.2 |  |
| `fb01-signal-s1` Was schaltet der Start-Taster -S1 letztlich? | 1 / 1 | ✓ / ✓ | ✓ / ✓ | 0.0696 / 0.0094 | 21.3 / 43.2 |  |
