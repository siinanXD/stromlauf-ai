# Recherche: Testwerk und Werkssimulation

Abgerufen 2026-09-26 (Websuche). Gilt für die Teile 1–4 der Werkssimulation
(`docs/superpowers/specs/2026-09-26-testwerk-standort-design.md`).

```yaml
problem:
  summary: >
    Realistisches Testwerk (Grundstoffmaschine in Sektoren -> 6 Linien -> Lager/Versand -> Büro)
    mit echten Kennzahlen, später deterministische Simulation Auftrag -> Auslieferung und Vorkalkulation.
  components: [Domäne und Kennzahlen, echte Maschinendoku als Testdaten, Simulationskern, Zeitplan-Anzeige, Logistik-Richtwerte]

solutions:
  official:
    - Valmet Advantage DCT: 2,8 m -> 2.200 m/min -> ~30.000 t/a; 5,6 m -> ~65.000 t/a
      (valmet.com/tissue/tissue-making-solutions/Advantage-DCT/)
    - Andritz PrimeLine S/W 2200: 2.200 m/min (andritz.com/newsroom-en/pulp-paper/2021-06-10-primeline-group)
    - Voith XcelLine: 2.001 m/min (TM16), Yankee 5,5 m (TM10) (voith.com press 72431; paperindustryworld.com)
    - Perini X3 (Valmet): 200 m/min, 10 Logs/min (valmet.com/.../perini-x3/)
    - Casmatic CMW208: bis 220 Pakete/min (valmet.com/.../casmatic-cmw208-kp060/)
    - PCMC Säge: 135 Schnitte/min (flexography.org, Branchenmeldung)
    - Gambini Flex600: bis 600 m/min, Rollenbreite bis 2.850 mm (tissueonlinenorthamerica.com, Branchenmedium)
  github:
    - LICSTER (thainnos/LICSTER): offene ICS-Testumgebung, Fischertechnik-Maßstab, gemischte OSS-Lizenzen
    - OpenPLC (GPL-3.0): Laufzeit, keine Maschinendoku
  packages:
    - SimPy 4.1.2 (MIT, 2026-05-24, 4 Maintainer, GitLab), deterministisch mit Seed, env.run(until=t)
    - salabim 26.0.8 (MIT, faktisch 1 Maintainer)
    - Ciw 3.2.7 (MIT, Warteschlangennetze, keine Schrittsteuerung)
    - Gantt React 19: @svar-ui/react-gantt 2.7.3 (MIT, Repo < 1 Jahr); andere veraltet oder nicht React-nativ
  services: []

comparison:
  criteria: [Lizenz, Pflegeaufwand für Einzelentwickler, Determinismus, Schrittsteuerung, Integration]
  domain: >
    Tissue: eine Papiermaschine liefert Mutterrollen für 6 verschiedene Linien, natürliche Verzweigung.
    Molkerei: kurze lineare Kette (Annahme -> Separator -> UHT -> Abfüllung), 6 Linien wirken konstruiert.
  real_docs: >
    Festo Didactic MPS: Nutzung/Weitergabe ohne schriftliche Zustimmung untersagt (AGB Festo Didactic LX 2022).
    Siemens SCE: nicht für kommerzielle Schulung von Industriekunden; Produktnutzung ungeklärt.
    OpenPLC/LICSTER: offen, aber Spielzeugmaßstab.

recommendation:
  selected_option: >
    Domäne Tissue; fiktive Maschinen mit belegten Kennzahlen; Doku generiert (wie FB-01);
    Simulationskern als eigene heapq-Ereignisschleife (~200 Zeilen); Zeitplan als SVG.
  reason: >
    Keine real nutzbare Doku mit passender Lizenz. Simulationslogik (Arbeitspläne, Rüstzeiten,
    Stücklisten) ist Geschäftslogik und ohnehin eigen; eine eigene Schleife vermeidet
    Abhängigkeit und erlaubt "bis Zeitpunkt T rechnen, dann anhalten" ohne Umweg.
  custom_build_required: true

risks:
  - Kennzahlen für Palettierer, Kartonierer, Interfolder, Faltmaschinen nur als Richtwert (keine Herstellerangabe gefunden)
  - Mutterrollen-Gewicht/Durchmesser nur aus Handelsquelle (yuanhuapaper.com), geringe Belastbarkeit
next_steps:
  - Rückweg Simulationskern: bei wachsender Komplexität (Störungen, Schichtmodelle) auf SimPy wechseln; Schnittstelle Ereignis -> Zustand bleibt gleich
  - Rückweg Zeitplan: bei Bedarf an Drag/Resize @svar-ui/react-gantt prüfen
```

Logistik-Richtwerte: Sattelzug 33 Europaletten (cargolo.com, eurowag.com), Torbelegung 30–90 min,
~6 min/Palette Beladung (datadocks.com, arrivy.com), mittleres Verteilzentrum 10–20 Tore
(renoindustrial.com, metricrig.com).
