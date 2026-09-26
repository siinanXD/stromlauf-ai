# Testwerk Teil 2: Vorkalkulation

Stand: 2026-09-26 · Auftrag: „vorher kalkulieren, wie lange es dauert und welche Materialien man
braucht“. Baut auf Teil 1 (Standortplan, Testwerk Tissue) auf. Deterministisch, kein LLM-Aufruf.

## Ergebnis für den Nutzer

Seite **Planung** (`/planung`, neuer Eintrag in der Navigation): Auftrag mit Positionen eingeben
(Artikel, Menge in Paketen oder Paletten), Auftragseingang und Wunschtermin. Sofort sichtbar:

1. **Verladebereit am** (frühester Termin) und ob der Wunschtermin hält (grün „hält“, sonst
   „+2 Tage“ in Schwarz; Rot bleibt Fehlern vorbehalten).
2. **Zeitplan** als Balken je Station über Kalendertage: Büro (Kundenservice, Finanzen,
   Arbeitsvorbereitung, ggf. Geschäftsführung), PM1 (Rohpapier), Linie(n), Einlagerung, Verladung.
   Geschlossene Zeiten schraffiert, Engpass markiert.
3. **Materialbedarf**: Rohpapier und daraus Zellstoff, Altpapier, Chemie, Wasser; Verpackung
   (Hülsen, Folie, Kartons), Paletten, Stretchfolie; je Zeile die Herleitung.
4. **Kennzahlen**: Pakete, Paletten, LKW, Rohpapier t, Linienzeit, Engpassmaschine.
5. **Kosten** (Nutzerentscheid: mit Richtwerten): Material, Fertigung je Maschine, Büro, Versand,
   Summe und je Einheit pro Position. Jeder Preis heißt „Richtwert (Annahme)“.

Annahme, sichtbar auf der Seite: freie Kapazität, keine anderen Aufträge, Rohstoffe vorrätig.
Warteschlangen und Bestände kommen mit Teil 3 (Simulation).

## Rechenmodell (rein, `backend/app/werk/calc.py`, `calendar.py`)

- **Rohpapier je Einheit** aus Artikeldaten: Blatt × Blattfläche × Lagen × g/m² × (1 + Verschnitt).
  Beispiel Toilettenpapier 8 × 150 Blatt, 9,8 × 12,5 cm, 3 Lagen, 16 g/m², 3 %: 0,727 kg/Paket.
- **Stückliste mehrstufig**: Artikel → Materialien (je Einheit oder je Palette); Eigenfertigung
  (Rohpapier auf PM1) → eigene Rezeptur je t (Zellstoff, Altpapier, Chemie, Wasser).
- **Arbeitsplan je Artikel**: Schritte mit Maschine, Leistung (Einheiten/min oder Paletten/h),
  Rüstzeit, Herleitung (z. B. „10 Logs/min × 28 Rollen/Log ÷ 8 Rollen/Paket = 35 Pakete/min“).
  Gekoppelte Schritte (Linie + Einlagerung) laufen gleichzeitig: Dauer = längste Rüstzeit +
  Menge ÷ Engpassleistung.
- **Ablauf**: Büro-Stationen nacheinander (Geschäftsführung nur ab 100 Paletten) → PM1 erzeugt das
  Rohpapier je Position nacheinander → Linie startet, wenn ihr Papier fertig und die Linie frei ist
  (Positionen auf verschiedenen Linien parallel, auf derselben Linie nacheinander) → Verladung:
  LKW = ⌈Paletten ÷ 33⌉, 45 min je LKW, bis zu 8 Tore gleichzeitig.
- **Kalender**: Büro Mo–Fr 07:00–16:00, Produktion 24/7, Versand Mo–Fr 06:00–22:00. Arbeitszeit
  wird über Fenster addiert (Freitag 15:30 + 60 min = Montag 07:30). Feiertage: noch nicht.
- Alle Parameter mit Quelle oder „Richtwert“ (LKW 33 Paletten, 30–90 min Torbelegung aus der Recherche).
- **Kosten**: Material = Menge × Preis (nur Zukaufteile; Rohpapier zählt über Rezeptur + PM1-Zeit).
  Fertigung = belegte Minuten × Maschinenstundensatz; in einer gekoppelten Linie ist jede Maschine
  die ganze Gruppendauer belegt. Der Stundensatz ist die Kennzahl „Maschinenstundensatz“ (€/h) der
  Maschine, also im Tab Kennzahlen änderbar. Büro = Minuten × Bürostundensatz, Versand = LKW ×
  Beladezeit × Satz der Verladetore. Büro und Versand werden nach Paletten auf die Positionen
  verteilt; je Position Kosten je Einheit. Fehlt ein Satz: 0 € und Hinweis.

## Daten

Neue Tabellen (nur neue, `create_all`): `articles`, `materials` (Preis €/Einheit mit Quelle,
optional Eigenfertigung auf Maschine mit Leistung), `bom_lines` (Artikel- oder Material-Eltern), `routing_steps`
(Artikel → Maschine, FK CASCADE), `plant_settings` (Schlüssel → JSON: Büro-Stationen, Kalender,
LKW, Tore, Freigabegrenze). Testwerk-Daten in `examples/testwerk/testwerk.json` (8 Artikel,
~14 Materialien), der Lader legt sie nach den Hallen an (`--refresh` ersetzt sie).

## API

`GET /api/articles` (mit Stückliste, Arbeitsplan, Rohpapier je Einheit), `GET /api/materials`,
`GET /api/plant-settings`, `POST /api/calc` (`{received_at, due_date, positions: [{article_id,
quantity, unit: "unit"|"pallet"}]}` → Termin, Stationen mit Start/Ende, Materialien, Kennzahlen,
Hinweise). 400 bei unbekanntem Artikel oder Menge ≤ 0; fehlender Arbeitsplan → Hinweis statt Fehler.

## Oberfläche (Blaupause)

Links Auftragsformular (Positionen als Zeilen, „+ Position“), rechts Ergebnis: Terminkopf,
Zeitplan-SVG (Zeilen = Stationen, Spalten = Tage, Nachtschraffur, Jetzt-Linie), Materialtabelle,
Kennzahlen, Herleitung aufklappbar. Neu berechnen bei jeder Änderung (kein Knopf nötig). Tab
**Stammdaten** zeigt Artikel mit Stückliste und Arbeitsplan (nur lesen). Mobil: untereinander.

## Nicht in Teil 2

Aufträge speichern, Bestände, Kapazitätskonflikte zwischen
Aufträgen, Stammdaten bearbeiten, Feiertage.

## Tests

pytest: Kalenderaddition (Nacht, Wochenende), Rohpapierformel, Stücklistenauflösung, Engpass,
LKW/Tore, Freigabegrenze, zwei Positionen gleiche/andere Linie, Wunschtermin, Ende-zu-Ende mit
Testwerk-Daten und festem Eingangszeitpunkt, Testwerk-Stammdaten vollständig.
vitest: Zeitachse (Zeit → x, Tagesraster, geschlossene Fenster). Browser: Auftrag eingeben,
Termin/Zeitplan/Material prüfen, mobil.
