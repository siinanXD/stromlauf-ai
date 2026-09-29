# Ingest-Benchmark fb01 (teilscan-ocr)

Dokument `examples/scan/01_Stromlaufplan_FB-01_teilscan.pdf`, 7 Seiten, 4.5 s (0.64 s je Seite). Gold `eval/ingest_gold/fb01.json`.

OCR: 1 Seiten, 5.2 s, Konfidenz 0.99 (unsichtbare Textebene, RapidOCR lokal auf der CPU).

Gate: Recall und Precision >= 0.00 fuer -: bestanden.

| Typ | Gold | gefunden | Treffer | Recall | Precision |
| --- | ---: | ---: | ---: | ---: | ---: |
| device | 72 | 72 | 72 | 1.00 | 1.00 |
| terminal | 74 | 73 | 73 | 0.99 | 1.00 |
| plc_address | 41 | 41 | 41 | 1.00 | 1.00 |
| cross_ref | 20 | 20 | 20 | 1.00 | 1.00 |

## Abweichungen je Seite

- Seite 3: fehlt terminal: -X4:U
