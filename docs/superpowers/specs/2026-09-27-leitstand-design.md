# Testwerk Teil 3: Leitstand (Durchlauf-Simulation)

Stand: 2026-09-27 · Auftrag: „mach Teil 3“, ursprünglich: vom Auftrag über Kundenservice, Finanzen und
Chef bis zur Maschine und zur Auslieferung simulieren; im Lager sehen, wie viel da ist, was heute raus
muss, welcher LKW an welchem Tor. Baut auf Teil 1 (Werk) und Teil 2 (Vorkalkulation) auf.
Deterministisch, kein LLM-Aufruf. Recherche: eigene Ereignisschleife statt SimPy
(`.ai/research/solution-comparisons/2026-09-26-werkssimulation.md`).

## Ergebnis für den Nutzer

Neue Seite **Leitstand** (`/leitstand`, Navigation). Oben die **Simulationsuhr**: Abspielen/Pause,
Tempo (1 h, 6 h, 1 Tag je Sekunde), Schieberegler über die Woche mit Tagesmarken. Darunter der
Zustand des Werks zur eingestellten Uhrzeit:

- **Auftragsbuch**: alle Aufträge mit aktueller Station, Paletten, Wunschtermin, „hält“/„+N Tage“.
- **Büro**: Kundenservice, Finanzen, Arbeitsvorbereitung, Geschäftsführung mit Personen (belegt/frei)
  und Warteschlange (Auftragsnummern); Finanzen zeigt Aufträge in Kreditklärung.
- **Fertigung**: PM1 und Linien L1–L6 mit laufendem Auftrag, Fortschritt und Warteschlange.
- **Lager**: Bestand je Artikel in Paletten; „heute raus“: Aufträge, die heute verladen werden.
- **Versand**: 8 Tore mit LKW (Auftrag, Fortschritt) und wartenden LKW.
- **Kennzahlen** für den ganzen Lauf: Termintreue, Ø Durchlaufzeit, Auslastung je Linie,
  Ø Wartezeit je Büro-Station.

Klick auf einen Auftrag zeigt seinen Weg als Zeitleiste (Warten hell, Arbeiten blau). In der Planung
legt „Als Auftrag anlegen“ die kalkulierte Bestellung ins Auftragsbuch.

## Modell (`backend/app/werk/sim.py`, rein)

- Ereignisschleife (heapq) mit Ressourcen: Büro-Stationen mit Personenzahl (KS 2, Finanzen 1, AV 1,
  GF 1; Richtwerte), PM1 (1), je Linie (1), Tore (8). Kalender und Dauern wie Teil 2 (`calc.py`).
- Reihenfolge: Büro und PM1 nach Ankunft; Linien nach Wunschtermin, dann Eingang; Tore nach Ankunft.
- Finanzen: Auftragswert = Menge × Verkaufspreis (Richtwert je Artikel). Übersteigen offene Aufträge
  des Kunden plus neuer Auftrag das Kreditlimit, folgt eine Klärung von 1 Arbeitstag (Wartezeit ohne
  Person), danach weiter.
- Geschäftsführung ab 100 Paletten (wie Teil 2).
- Lager: Anfangsbestand je Artikel. Die Arbeitsvorbereitung reserviert vorhandenen Bestand, der Rest
  wird gefertigt. Bestand steigt am Linienende, sinkt mit der Verladung.
- Versand, sobald alle Positionen bereit sind: LKW = ⌈Paletten ÷ 33⌉, je LKW 45 min an einem
  freien Tor im Versandfenster.
- Ausgabe: je Auftrag Stufen mit Ankunft, Start, Ende, Ressource; Bestandsverlauf je Artikel;
  Torbelegung; Kennzahlen. Das Frontend leitet den Zustand zu jeder Uhrzeit aus diesen Intervallen
  ab (Abspielen ohne Nachrechnen).

## Daten

Neue Tabellen `customers` (Name, Kreditlimit), `orders` (Nummer, Kunde, Eingang, Wunschtermin),
`order_lines` (Artikel, Menge, Einheit), `stock` (Artikel → Einheiten); Spalte `articles.price`
(Verkaufspreis, Migration). Parameter: `workers` je Büro-Station, `credit_hold_min`. Testwerk:
6 Kunden, 14 Aufträge in KW 40 (28.09.–02.10.2026), Anfangsbestand für 5 Artikel; Lader.

API: `GET /api/customers`, `GET/POST /api/orders`, `DELETE /api/orders/{id}`, `GET /api/stock`,
`POST /api/simulation` (optional nur ausgewählte Aufträge) → Ergebnis.

## Nicht in Teil 3

Maschinenausfälle, Schichtpläne, Nachproduktion aufs Lager, Teillieferungen, Kommissionierung
gemischter Paletten, Bearbeiten von Kunden/Beständen in der Oberfläche.

## Tests

pytest: zwei Aufträge teilen sich eine Person (zweiter wartet), Kreditlimit → Klärung,
Geschäftsführung ab 100 Paletten, Bestand deckt Auftrag (keine Fertigung, früher verladen), Teilbestand,
Linienreihenfolge nach Wunschtermin, Tore begrenzt (9. LKW wartet), Bestandsverlauf, Kennzahlen,
Ende-zu-Ende mit Testwerk-Aufträgen. vitest: Zustand zur Uhrzeit aus Intervallen. Browser: Abspielen,
Schieben, Auftrag anklicken, Auftrag aus Planung anlegen, mobil.
