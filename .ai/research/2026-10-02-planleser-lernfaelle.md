# Planleser: Lernfälle aus dem Lehrerlauf

Stand: 2026-10-02. Grundlage sind zwei Lehrerläufe mit `openai:gpt-5-mini` auf den öffentlichen Beispielplänen FB-01
und UR-01 (`eval/plan_teacher.py`, Ergebnisse lokal unter `eval/results/`, nicht im Repo). Neu ausgewertet wurde nur
mit `--from-result`, ohne weiteren Modellaufruf. Gruppe „Modell richtig, Regeln fehlen“: 5 Fälle auf FB-01, 48 auf
UR-01, zusammen 53.

## Vorgehen

Für jedes Paar die Seite mit `plan_wires` nachgelesen: Segmente (`page_segments`), Netze (`page_nets`), freie Enden,
die Symbole (geschlossene Pfade), auf deren Rand ein Ende liegt, und die nächsten Anschlusstexte mit Abstand. Daraus
der Grund, warum die Regeln das Ende nicht benennen. Die Zuordnung ist eindeutig: Jeder der 53 Fälle hat genau eine
Ursache, die die Leitung oder ihr Gegenende betrifft.

## Klassifikation der 53 Fälle

| Kategorie | FB-01 | UR-01 | Summe |
| --- | ---: | ---: | ---: |
| 1. Leitung endet am Rand eines Gerätesymbols ohne Anschlussnummern; das Kennzeichen steht neben dem Symbol, nicht am Leitungsende | 5 | 23 | 28 |
| 2. Klemmenreihe mit Sammelbeschriftung („-X4:U -X4:V -X4:W“ als eine Zeile); die zweite und dritte Klemme bleiben ohne Namen, am anderen Ende ein Gerätesymbol wie in 1 | 0 | 24 | 24 |
| 3. Zuleitung endet im Inneren eines Spulenkörpers statt an einem Anschluss | 0 | 1 | 1 |
| **Summe** | **5** | **48** | **53** |

Zu 1, nach Symbolart: Rechteck mit Kennzeichen links (Schutzschalter, Netzteil, Schütz, Umrichter, Reparaturschalter)
oder Kreis mit Kennzeichen rechts (Motor, Meldeleuchte, Zähler). Der Abstand zwischen Kennzeichen und Symbolrand liegt
bei 3 bis 6 pt, das Kennzeichen steht auf der Höhe des Symbols. 10 Fälle verbinden zwei Gerätesymbole (Schutzschalter
mit Schütz oder Umrichter, Reparaturschalter mit Motor), 18 ein Gerätesymbol mit einer Klemme oder einem
Kontaktanschluss. Von den 18 sind 12 die erste Klemme einer Sammelbeschriftung, die schon vorher richtig hieß.

Zu 2: Nur das erste Wort einer Zeile zählt als Anschlusstext („Klemmen zählen nur am Anfang ihrer Zeile“). Die
Klemmen V und W bekamen deshalb keinen Namen; die Klemme W bekam sogar den Namen der PE-Klemme daneben, deren
Beschriftung ihr näher stand als jeder andere Text. Ohne die Regel 1 unten hätte die Regel 2 deshalb 14 falsche
Kanten erzeugt (UR-01), auf PM1-AR 8.

Zu 3: Der Erzeuger der Testdokumentation zeichnet auf den Ausgangsblättern die Zuleitung bis in die Mitte der Spule.
Ein echter Plan führt die Leitung an den Anschluss A1. Bewusst ohne Regel.

Nicht vorgekommen sind: gedrehte Beschriftungen, Querverweis-Pfeile, eine zu strenge Schienenregel, Klemmleisten als
Kasten und Leitungen, die durch ein Klemmensymbol laufen. Die Gruppe „Regeln falsch“ (3 auf FB-01, 15 auf UR-01)
besteht nur aus Kanten der Lage im Plan (Feldgerät jenseits der Klemme). Das Gold `wires` kennt nur gezeichnete
Leitungen; diese Kanten bleiben unverändert.

## Umgesetzte Regeln (`backend/app/ingestion/plan_wires.py`)

1. **Beschriftung an der nächsten Klemme** (`_terminal_of`): Ein Anschlusstext benennt ein Ende an einer Klemme nur,
   wenn diese Klemme dem Text am nächsten ist. Voraussetzung für die anderen Regeln, ändert allein keine Zahl.
2. **Kennzeichen neben dem Symbol** (`_box_labels`, Kategorie 1): Endet eine Leitung am Rand eines großen Symbols ohne
   Anschluss darin, heißt das Ende wie das Gerätekennzeichen links oder rechts neben dem Symbol auf seiner Höhe, bis
   `LABEL_GAP` = 8 pt. Ein Kennzeichen neben zwei Symbolen und ein Symbol mit zwei Kennzeichen bleiben offen. Stehen
   Anschlussnummern am Symbol (Spule oder Ventil A1/A2), gilt das Kennzeichen nicht: Auf den Ausgangsblättern berührt
   die Zuleitung einer Spule das Nachbarsymbol, das ergab ohne diese Ausnahme je 2 falsche Kanten auf UR-01 und
   PM1-AR. Ein Anschluss schlägt sein Gerät („-K1:A1“ und „-K1“ im selben Netz).
3. **Sammelbeschriftung** (`_terminal_runs`, `_listed_terminals`, Kategorie 2): Eine Zeile, die nur Klemmen derselben
   Leiste nennt, benennt die Klemmen bis `PIN_REACH` um sie von links nach rechts, wenn es genau so viele in einer
   Reihe sind. Klemmen mit eigener Beschriftung zählen nicht mit. Geht die Zeile mit anderem Text weiter, ist sie
   ein Hinweis.
4. **Richtung aus der Lage**: Eine ungerichtete Leitungskante (Klemme mit Umrichter oder Leuchte) verdrängt die
   gerichtete Lage-Kante desselben Paars nicht mehr. Sonst wären die Hauptwege kürzer geworden.

`PLAN_READER_VERSION` = 3.

## Ergebnis

`eval/run_plan_graph.py`, Gate Precision >= 0,95 auf beiden Ebenen:

| Plan | Leitungen vorher | Leitungen nachher | Tabellen vorher | Tabellen nachher |
| --- | --- | --- | --- | --- |
| FB-01 | P 1,00, R 0,48 (16/33) | P 1,00, R 0,85 (28/33) | P 1,00, R 0,66 (21/32) | P 1,00, R 0,72 (23/32) |
| UR-01 | P 1,00, R 0,42 (50/119) | P 1,00, R 0,95 (113/119) | P 1,00, R 0,47 (64/136) | P 1,00, R 0,80 (109/136) |
| PM1-AR | P 1,00, R 0,48 (44/91) | P 1,00, R 0,91 (83/91) | P 1,00, R 0,52 (56/108) | P 1,00, R 0,77 (83/108) |

Lehrerlauf neu ausgewertet: Von den 53 Fällen finden die Regeln jetzt 52 (FB-01 5 von 5, UR-01 47 von 48); offen ist
der eine Fall aus Kategorie 3. Startknoten mit einem Hauptweg ab 3 Knoten (`signal_view.main_view`): FB-01 29 -> 33,
UR-01 83 -> 89, PM1-AR 74 -> 80. Laufzeit ohne messbaren Unterschied (QElectroTech „industrial“, 50 Seiten: 2,4 bis
3,6 s je Lauf, vorher wie nachher).

Lokales Fremddokument (11 Seiten, nicht im Repo): unverändert 16 Kanten (Leitung 10, Lage 6), 18 Startknoten mit
Hauptweg ab 3 Knoten. Regel 2 benennt dort 16 Symbole; die 15 Netze mit einem so benannten Ende haben aber kein
zweites benanntes Ende. Die QElectroTech-Beispiele ergeben weiter keine Leitungskante (Kennzeichen im Blatt-Stil ohne
Minus).

## Offen

- **Hinweiszeile mit Klemmen (FB-01, 3 Leitungen):** „-X4:U -X4:V -X4:W (Leitung …)“ zählt als Hinweis. Als
  Sammelbeschriftung gelesen wären die drei Leitungen zum Reparaturschalter richtig, aber die Tabellen-Ebene könnte sie
  nicht bestätigen: Der Klemmenplan nennt den Motor als Ziel, nicht den Reparaturschalter dazwischen. Die Precision
  der Tabellen-Ebene fiele auf FB-01 unter 0,95.
- **Spulenkörper (Kategorie 3):** 2 Leitungen auf FB-01, 1 auf UR-01, 4 auf PM1-AR (Spulen und Ventile). Besser im
  Erzeuger beheben (Leitung an A1 führen) als mit einer Regel.
- **Zweiter Kanal einer Reihenschaltung:** Öffner ohne eigenes Kennzeichen in den Sicherheitskreisen (UR-01 5,
  PM1-AR 4). Ihre Anschlussnummern liegen gleich weit von zwei Kennzeichen; auf UR-01 fand sie auch das Modell nicht.
