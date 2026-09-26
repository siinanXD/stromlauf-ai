# Testwerk Teil 4: Test-Dokumentation für komplexe Maschinen

Stand: 2026-09-27 · Auftrag: „mach Teil 4“ (Test-Doku für komplexe Maschinen: Schaltplan, Klemmenplan,
Stückliste, AWL, Handbuch). Echte Herstellerdoku ist lizenzrechtlich nicht nutzbar (Recherche
2026-09-26), deshalb generiert wie FB-01: frei erfunden, in sich stimmig, ohne Herstellerbezug.

## Ziel

Zwei Maschinen des Testwerks bekommen eine vollständige Elektrodokumentation, damit Chat, Befundkarte,
Signalweg, Fehlersuche und Onboarding an etwas Größerem als dem Förderband geprüft werden können:

1. **UR-01 Umroller Toilettenpapier** (Maschine L1-UR): 7 Antriebe (5 an Frequenzumrichtern über
   PROFIBUS, 2 über Schütze), Bahnriss-, Durchmesser- und Hülsensensoren, 4 Schutztüren, 3 Not-Halt,
   Bedienpult, Sicherheitsrelais für Not-Halt und Schutztüren, SPS mit 2 Eingabe- und 1 Ausgabebaugruppe.
2. **PM1-AR Aufrollung** (Maschine PM1-S6): Tragtrommel 75 kW und Tambourantrieb an Umrichtern,
   Hydraulik- und Ölpumpe, Tambourwechsel als Schrittkette, Reißleine, Bahnriss, Druck- und
   Ölstandsüberwachung.

Je Maschine: Stromlaufplan (PDF, 9–11 Blätter, Blattraster 8 Spalten), Stückliste (xlsx), Klemmenplan
(csv), SPS-Programm (AWL: FB mit Netzwerken, Instanz-DB, OB1-Aufruf), Symboltabelle (sdf),
Betriebsanleitung (md) mit Fehlertabelle `Symptom | Mögliche Ursache | Prüfung`. Jeder Blatt/Spalten-
Verweis zeigt auf die Spalte, in der das Kennzeichen tatsächlich steht (Test wie bei FB-01).

## Generator (`scripts/testdoku/`)

Datengetrieben statt handgezeichnet: `model.py` (Maschine, Antriebe, Ein-/Ausgänge, Klemmleisten,
Sicherheitskreise, Netzwerke, Fehlertabelle), `render_pdf.py` (Deckblatt + Inhalt, Einspeisung,
Antriebsblätter mit je bis zu 3 Abgängen, Sicherheitskreis, DI/DO-Blätter, Klemmenplan-Blätter),
`render_rest.py` (xlsx, csv, awl, sdf, md), `machines/ur01.py`, `machines/pm1_ar.py`, `build.py`.
Blattverweise werden aus dem Layout berechnet, nicht von Hand eingetragen. FB-01 bleibt unverändert.
Ausgabe: `examples/umroller/`, `examples/aufrollung/` (README je Ordner).

## Lader

`scripts/load_testwerk.py --docs`: legt je Maschine eine Wissensquelle an, lädt die Dateien hoch,
wartet auf die Ingestion (lokal, kein Vision), verknüpft die Quelle mit der Testwerk-Maschine (L1-UR,
PM1-S6) und übernimmt die Fehlertabelle aus dem Onboarding-Vorschlag in die Fehlerliste der Maschine.
Idempotent: vorhandene Quelle gleichen Namens wird wiederverwendet (`--refresh` lädt neu).

## Tests

pytest, ohne DB: je Dokumentensatz Verweise vs. Plan (pdfium-Textsuche wie FB-01), Stückliste und
Klemmenplan nennen nur Kennzeichen, die im Plan vorkommen, alle Adressen der Symboltabelle stehen im
AWL, Signalgraph aus den Dateien liefert einen Weg vom Start-Taster bis zum Wickler-Umrichter bzw.
von der Reißleine bis zum Tragtrommel-Umrichter, Onboarding-Parser findet ≥ 8 Fehler je Handbuch,
Fehlersuche-Schritte für einen Fehler mit Blattverweisen. Live: Lader, dann Maschinenseite L1-UR:
Befundkarte, Signalweg, Fehler mit Diagnose.
