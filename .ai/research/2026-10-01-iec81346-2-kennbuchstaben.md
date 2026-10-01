# Recherche: Kennbuchstaben nach IEC 81346-2 (Issue #99)

Abgerufen 2026-10-01. Nur frei zugaengliche Quellen; die Norm wurde nicht gekauft (Entscheidung des Owners).
Bedeutungen in eigenen Worten.

- **Primaerquellen**
  - IEC 81346-2:2019, Leseprobe mit Tabelle 1 (Hauptklassen) und den Unterklassen von B und C:
    https://cdn.standards.iteh.ai/samples/21908/1b996d119d0945b2b28359332ffa9b3f/IEC-81346-2-2019.pdf
  - IEC 81346-2:2009, Leseprobe:
    https://cdn.standards.iteh.ai/samples/50858/1c3148c6446e46a8b8a670e0ec9160c1/IEC-81346-2-2009.pdf
  - IHK Region Stuttgart / PAL, Merkblatt zur DIN EN IEC 81346-2:2020-10 (KF, KH, MB, MM, QA, QM, RN, SG, SH, SJ;
    Taster von -SF zu -SJ, Drosselrueckschlagventil von -RZ zu -RN):
    https://www.ihk.de/blueprint/servlet/resource/blob/5090560/d005ab9b73c3e45d81920e28f72b7160/din-en-iec-81346-2-2020-10-referenzkennzeichnung-data.pdf
  - Siemens-Datenblatt 3NA3810 (FC); andere Siemens-Datenblaetter nennen meist nur den ersten Buchstaben:
    https://apim.industry.siemens.cloud/ted/datasheet?format=PDF&mlfbs=3NA3810&language=en&caller=SiePortal
  - ISO-Projektseite IEC/FDIS 81346-2, Ausgabe 3 in der Schlussabstimmung: https://www.iso.org/standard/87205.html
- **Sekundaer, nur Hinweis**: de.wikipedia „EN IEC 81346“ (alle 166 Unterklassen der Ausgabe 2019) und
  „DIN 40719-2“ (alte Kennbuchstaben); Verbandsschrift IG EVU-001 (2010).

## Befunde

- Ausgabe 2019: Hauptklassen B, C, E, F, G, H, K, M, N, P, Q, R, S, T, U, W, X. A ist nicht mehr zulaessig, D, J, L,
  V, Y und Z sind reserviert, N ist neu. Eingeordnet wird nach der eigentlichen Funktion des Objekts, nicht nach
  seinem Zweck in der Anlage; es gibt eine dritte Buchstabenebene.
- Von 166 zweibuchstabigen Unterklassen sind 42 primaer belegt: 31 aus B und C, 10 aus dem PAL-Merkblatt, FC.
  Die uebrigen 124 stehen nur in Sekundaerquellen.
- Widersprueche, nicht aufgeloest: Hauptschalter QA (PAL) oder QB (Wikipedia), Schrittmotor MB oder MAB,
  Ueberlastrelais BC (IEC-Leseprobe) oder FCC (Wikipedia), Motorschutzschalter Q (Siemens) oder FC (Blog-Beispiel),
  Netzteil TBA oder TCA/TCB, Not-Halt-Pilztaster SGC oder SJ, alter Code fuer Frequenzumrichter U oder G.
- Franzoesische Paare wie in QElectroTech: KE, EV und HL bedeuten nach IEC 81346-2 etwas anderes; QF, KM, KA, SB
  und FU kommen dort nicht vor (nur sekundaer belegt).

## Entscheidung

- `backend/app/ingestion/letter_codes.py` bestimmt die Lesart je Quelle: `2019` bei primaer belegten Unterklassen
  oder dritter Buchstabenebene, `alt` bei Buchstaben, die 2019 nicht zulaessig oder reserviert sind, bei
  franzoesischen Paaren und beim Blatt-Stil ohne Minus. Eine Seite gewinnt nur mit mindestens doppelt so vielen
  Kennzeichen; sonst und ohne Hinweis `offen`.
- Arten: aeltere Lesart unveraendert. Lesart 2019: Hauptklassen aus Tabelle 1, schaerfer nur bei primaer belegten
  Unterklassen (FC, KH, MB, MM, QA, QM, RN, SG, SH, SJ). Bei `offen` keine Art fuer H, K, N, Q, U und franzoesische
  Paare; das Teil bleibt im Modell.
- Lizenz: Die Wikipedia-Tabelle (CC BY-SA 4.0) wird nicht uebernommen; das Repo ist MIT. Im Code stehen nur Codes mit
  eigenen Bedeutungen und Quellenangabe. Die vollstaendige Ergebnisdatei der Recherche (YAML, 274 Eintraege mit
  Wikipedia-Ableitungen) liegt deshalb nur lokal unter `testdata/recherche/`.
- Rueckweg: Alle Tabellen stehen in `letter_codes.py`. Neue Belege oder Ausgabe 3 ergaenzen dort; liefert
  `detect_edition` immer `alt`, gilt wieder das Verhalten vor #99.
