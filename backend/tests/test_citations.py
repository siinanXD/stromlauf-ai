"""Zitat-Resolver (Issue #46): [[Datei|Ort]] deterministisch gegen Fundstellen und Index pruefen, ohne Modell."""

from pathlib import Path

from app.citations import DocIndex, check_citations, parse_markers, summary

PLAN = DocIndex(
    filename="01_Stromlaufplan_FB-01.pdf", is_pdf=True, pages=frozenset(range(1, 8)), page_count=7
)
BOM = DocIndex(
    filename="02_Stueckliste_FB-01.xlsx",
    is_pdf=False,
    tags=frozenset({"-F2", "-K1", "-X3", "-X4", "-A1", "/3.2"}),
)
AWL = DocIndex(
    filename="04_SPS_Programm_FB-01.awl",
    is_pdf=False,
    sections=(
        "FB 10 - Foerderband FB-01 Steuerung",
        "FB 10 - Foerderband FB-01 Steuerung / NW 4 Stoerung Motorschutz",
    ),
)
MANUAL = DocIndex(filename="06_Betriebsanleitung_FB-01.md", is_pdf=False)
DOCS = [PLAN, BOM, AWL, MANUAL]
CITED = {d.filename for d in DOCS}


def test_parse_markers_dedupliziert_und_trimmt():
    text = "-F2 [[01_Stromlaufplan_FB-01.pdf|/3.2]] und nochmal [[01_Stromlaufplan_FB-01.pdf|/3.2]], dazu [[ 06_Betriebsanleitung_FB-01.md | Kap. 6 ]] [[unfertig"
    assert parse_markers(text) == [
        ("[[01_Stromlaufplan_FB-01.pdf|/3.2]]", "01_Stromlaufplan_FB-01.pdf", "/3.2"),
        ("[[ 06_Betriebsanleitung_FB-01.md | Kap. 6 ]]", "06_Betriebsanleitung_FB-01.md", "Kap. 6"),
    ]


def test_seite_im_pdf_ist_gueltig():
    [check] = check_citations("Siehe [[01_Stromlaufplan_FB-01.pdf|S. 3]]", DOCS, CITED)
    assert (check.file, check.locator, check.valid, check.checked, check.reason) == (
        "01_Stromlaufplan_FB-01.pdf",
        "S. 3",
        True,
        True,
        "",
    )


def test_datei_ausserhalb_der_fundstellen_ist_ungueltig():
    [check] = check_citations(
        "Laut Liste [[02_Stueckliste_FB-01.xlsx|-K1]]", DOCS, cited={"01_Stromlaufplan_FB-01.pdf"}
    )
    assert check.valid is False
    assert check.reason == "Datei nicht in den Fundstellen der Antwort"


def test_unbekannte_datei_ist_ungueltig():
    [check] = check_citations("[[99_Fremd.pdf|S. 1]]", DOCS, CITED)
    assert check.valid is False
    assert check.reason == "Datei nicht in der Wissensquelle"


def test_seite_ausserhalb_des_pdf_ist_ungueltig():
    [check] = check_citations("[[01_Stromlaufplan_FB-01.pdf|S. 9]]", DOCS, CITED)
    assert check.valid is False
    assert check.reason == "Seite 9 nicht in 01_Stromlaufplan_FB-01.pdf (7 Seiten)"


def test_kennzeichen_das_nicht_in_der_datei_vorkommt_ist_ungueltig():
    # Referenzlauf 2026-09-28, fb01-f2-typ: -X3:3 steht im Klemmenplan, nicht in der Stueckliste
    [check] = check_citations(
        "Stueckliste: MSS 3P [[02_Stueckliste_FB-01.xlsx|-X3:3]]", DOCS, CITED
    )
    assert check.valid is False
    assert check.reason == "Kennzeichen -X3:3 nicht in 02_Stueckliste_FB-01.xlsx"


def test_kennzeichen_in_der_datei_ist_gueltig():
    [check] = check_citations("[[02_Stueckliste_FB-01.xlsx|-F2]]", DOCS, CITED)
    assert (check.valid, check.checked, check.reason) == (True, True, "")


def test_querverweis_in_nicht_pdf_ueber_den_index():
    [check] = check_citations("[[02_Stueckliste_FB-01.xlsx|/3.2]]", DOCS, CITED)
    assert (check.valid, check.checked) == (True, True)
    [check] = check_citations("[[02_Stueckliste_FB-01.xlsx|/9.9]]", DOCS, CITED)
    assert (check.valid, check.reason) == (
        False,
        "Kennzeichen /9.9 nicht in 02_Stueckliste_FB-01.xlsx",
    )


def test_abschnitt_in_nicht_pdf_ueber_die_chunk_abschnitte():
    [check] = check_citations("[[04_SPS_Programm_FB-01.awl|FB 10 NW 4]]", DOCS, CITED)
    assert (check.valid, check.checked, check.reason) == (True, True, "")
    [check] = check_citations("[[04_SPS_Programm_FB-01.awl|FB 10 NW 9]]", DOCS, CITED)
    assert (check.valid, check.reason) == (
        False,
        "Abschnitt 'FB 10 NW 9' nicht in 04_SPS_Programm_FB-01.awl",
    )


def test_ort_ohne_abschnitte_im_dokument_ist_nicht_pruefbar():
    [check] = check_citations("[[06_Betriebsanleitung_FB-01.md|Kap. 7]]", DOCS, CITED)
    assert (check.valid, check.checked) == (True, False)
    assert check.reason == "Ort nicht pruefbar: 06_Betriebsanleitung_FB-01.md hat keine Abschnitte"


def test_abschnitt_mit_alternativen_netzwerken_trifft_wenn_eines_passt():
    # gpt-5-mini zitiert "FB 10 NW 2/3": Netzwerk 2 oder 3 desselben Bausteins
    awl = DocIndex(
        filename="04_SPS_Programm_FB-01.awl",
        is_pdf=False,
        sections=(
            "FB 10 - Steuerung / NW 2 Vorwaerts",
            "FB 10 - Steuerung / NW 3 Rueckwaerts",
            "OB 1 - Main / NW 1 Aufruf",
        ),
    )
    [either] = check_citations("[[04_SPS_Programm_FB-01.awl|FB 10 NW 2/3]]", [awl], None)
    [neither] = check_citations("[[04_SPS_Programm_FB-01.awl|FB 10 NW 7/8]]", [awl], None)
    [wrong_block] = check_citations("[[04_SPS_Programm_FB-01.awl|FB 10 NW 1/9]]", [awl], None)
    assert (either.valid, either.checked, either.reason) == (True, True, "")
    assert neither.valid is False and wrong_block.valid is False


def test_leerer_ort_ist_ungueltig():
    [check] = check_citations(
        "[[05_Symboltabelle_FB-01.sdf|-]]",
        [
            DocIndex(
                filename="05_Symboltabelle_FB-01.sdf", is_pdf=False, sections=("Symboltabelle",)
            )
        ],
        None,
    )
    assert (check.valid, check.reason) == (False, "Ortsangabe fehlt")


def test_blattverweis_im_echten_plan(tmp_path: Path):
    pdf = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "foerderband"
        / "01_Stromlaufplan_FB-01.pdf"
    )
    plan = DocIndex(
        filename=pdf.name, is_pdf=True, path=pdf, pages=frozenset(range(1, 8)), page_count=7
    )
    ok, bad, bare, bare_bad = check_citations(
        f"[[{pdf.name}|/3.8]] [[{pdf.name}|/12.1]] [[{pdf.name}|/7]] [[{pdf.name}|/12]]",
        [plan],
        None,
    )
    assert (ok.valid, ok.checked, ok.reason) == (True, True, "")
    assert (bad.valid, bad.reason) == (False, f"Blatt 12 nicht in {pdf.name}")
    assert (bare.valid, bare.checked) == (True, True)  # "/7": Blatt ohne Spalte
    assert (bare_bad.valid, bare_bad.reason) == (False, f"Blatt 12 nicht in {pdf.name}")


def test_kennzeichen_beleg_der_dem_satz_widerspricht_bleibt_gueltig_mit_hinweis():
    # Satz ueber -A1, Beleg zeigt auf die Stuecklistenzeile eines anderen Betriebsmittels
    text = "## Kurzantwort\n-A1 ist laut Stückliste eine SPS-CPU mit PROFIBUS DP [[02_Stueckliste_FB-01.xlsx|-K1]].\n- Stromlaufplan [[01_Stromlaufplan_FB-01.pdf|S. 5]]"
    suspicious, plain = check_citations(text, DOCS, CITED)
    assert (suspicious.valid, suspicious.checked) == (True, True)
    assert suspicious.reason == "Satz nennt -A1, Beleg zeigt auf -K1"
    assert plain.reason == ""


def test_klemmen_und_querverweise_als_beleg_bekommen_keinen_hinweis():
    # Referenzlauf 2026-09-28, fb01-nicht-vorhanden: -X4 ist eine Klemmleisten-Zeile der Stueckliste; ob sie die
    # Aussage ueber -A1 stuetzt, erkennt der Resolver nicht (Klemmen und Querverweise belegen andere Geraete)
    [terminal] = check_citations(
        "-A1 ist laut Stückliste eine SPS-CPU [[02_Stueckliste_FB-01.xlsx|-X4]]", DOCS, CITED
    )
    [crossref] = check_citations(
        "-M1 haengt an Blatt 3 [[02_Stueckliste_FB-01.xlsx|/3.2]]", DOCS, CITED
    )
    assert (terminal.valid, terminal.reason) == (True, "")
    assert (crossref.valid, crossref.reason) == (True, "")


def test_kennzeichen_beleg_passt_zum_satz_oder_satz_ohne_kennzeichen_bleibt_ohne_hinweis():
    [same] = check_citations(
        "-F2 ist ein Motorschutzschalter [[02_Stueckliste_FB-01.xlsx|-F2]]", DOCS, CITED
    )
    [among] = check_citations(
        "-K1 wird durch -F2 geschuetzt [[02_Stueckliste_FB-01.xlsx|-F2]]", DOCS, CITED
    )
    [none] = check_citations(
        "Der Foerdermotor hat 1,5 kW [[02_Stueckliste_FB-01.xlsx|-K1]]", DOCS, CITED
    )
    [strip] = check_citations(
        "Motorschutz meldet ueber -X3:3 [[02_Stueckliste_FB-01.xlsx|-X3]]", DOCS, CITED
    )
    assert [c.reason for c in (same, among, none, strip)] == ["", "", "", ""]


def test_zusammenfassung_zaehlt_gueltig_geprueft_gesamt():
    checks = check_citations(
        "[[01_Stromlaufplan_FB-01.pdf|S. 3]] [[01_Stromlaufplan_FB-01.pdf|S. 9]] [[06_Betriebsanleitung_FB-01.md|Kap. 7]]",
        DOCS,
        CITED,
    )
    assert summary(checks) == {"valid": 2, "checked": 2, "total": 3}
    assert summary([]) == {"valid": 0, "checked": 0, "total": 0}


# --- Befunde aus dem Review vom 2026-09-29 ---------------------------------------------------------

PDF = (
    Path(__file__).resolve().parents[2] / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
)
REAL_PLAN = DocIndex(
    filename=PDF.name, is_pdf=True, path=PDF, pages=frozenset(range(1, 8)), page_count=7
)


def test_seite_und_blatt_in_wortform():
    text = (
        f"[[{PDF.name}|Seite 5]] [[{PDF.name}|seite 9]] [[{PDF.name}|Blatt 3]] [[{PDF.name}|Bl. 12]] "
        f"[[{PDF.name}|Blatt 5 / 7]] [[{PDF.name}|Blatt 4 Not-Halt-Kreis]]"
    )
    seite, seite9, blatt, bl12, blatt5, blatt4 = check_citations(text, [REAL_PLAN], None)
    assert (seite.valid, seite.checked) == (True, True)
    assert (seite9.valid, seite9.reason) == (False, f"Seite 9 nicht in {PDF.name} (7 Seiten)")
    assert (blatt.valid, blatt.checked) == (True, True)
    assert (bl12.valid, bl12.reason) == (False, f"Blatt 12 nicht in {PDF.name}")
    assert blatt5.valid is True and blatt4.valid is True


def test_baustein_und_netzwerk_werden_strukturiert_verglichen():
    awl = DocIndex(
        filename="p.awl",
        is_pdf=False,
        tags=frozenset({"-K1"}),
        sections=(
            "FB 10 - Foerderband FB-01 Steuerung / NW 1 Selbsthaltung",
            "FB 10 - Foerderband FB-01 Steuerung / NW 4 Stoerung Motorschutz",
            "OB 1 - Main / NW 1 Aufruf",
        ),
    )
    text = "[[p.awl|FB 10 NW 10]] [[p.awl|FB 1 NW 10]] [[p.awl|FB 10 NW 9 Schuetz vorwaerts -K1]] [[p.awl|FB 10 NW 4 Stoerung]] [[p.awl|OB 1 NW 1]] [[p.awl|-K1]]"
    results = check_citations(text, [awl], None)
    assert [r.valid for r in results] == [False, False, False, True, True, True]
    assert results[0].reason == "Abschnitt 'FB 10 NW 10' nicht in p.awl"


def test_sps_adressen_mit_leerzeichen_und_folio_kennzeichen_treffen_den_index():
    sdf = DocIndex(
        filename="05_Symboltabelle_FB-01.sdf",
        is_pdf=False,
        tags=frozenset({"A4.0", "E0.3"}),
        sections=("Symboltabelle",),
    )
    qet = DocIndex(
        filename="plan.pdf",
        is_pdf=True,
        tags=frozenset({"4Q1", "9K1"}),
        sections=("Mains Power Supply",),
        page_count=50,
    )
    a, e, q, bad = check_citations(
        "[[05_Symboltabelle_FB-01.sdf|A 4.0]] [[05_Symboltabelle_FB-01.sdf|E 0.3]] [[plan.pdf|4Q1]] [[plan.pdf|4Q9]]",
        [sdf, qet],
        None,
    )
    assert [(c.valid, c.checked) for c in (a, e, q)] == [(True, True)] * 3
    assert bad.valid is False


def test_gleicher_dateiname_in_zwei_quellen_gilt_wenn_eine_datei_passt():
    short = DocIndex(filename="Stromlaufplan.pdf", is_pdf=True, page_count=7)
    long = DocIndex(filename="Stromlaufplan.pdf", is_pdf=True, page_count=12)
    for docs in ([short, long], [long, short]):
        [ok] = check_citations("[[Stromlaufplan.pdf|S. 9]]", docs, None)
        assert (ok.valid, ok.checked) == (True, True)
    [bad] = check_citations("[[Stromlaufplan.pdf|S. 13]]", [short, long], None)
    assert bad.valid is False and "12 Seiten" in bad.reason


def test_abschnitt_mit_umlauten_und_kompakter_schreibweise():
    awl = DocIndex(
        filename="p.awl",
        is_pdf=False,
        sections=("FB 10 - Foerderband / NW 4 Stoerung Motorschutz",),
    )
    umlaut, kompakt = check_citations(
        "[[p.awl|FB 10 Störung Motorschutz]] [[p.awl|FB10 NW4]]", [awl], None
    )
    assert (umlaut.valid, kompakt.valid) == (True, True)


def test_unlesbare_pdf_macht_den_blattverweis_nicht_pruefbar():
    plan = DocIndex(filename="plan.pdf", is_pdf=True, path=Path("/nirgends/plan.pdf"), page_count=7)

    def boom_os(path, sheet):
        raise OSError("weg")

    def boom_pdfium(path, sheet):
        raise RuntimeError("Failed to load document")  # pypdfium2.PdfiumError ist ein RuntimeError

    for lookup in (boom_os, boom_pdfium):
        [c] = check_citations("[[plan.pdf|/3.2]]", [plan], None, sheet_lookup=lookup)
        assert (c.valid, c.checked, c.reason) == (
            True,
            False,
            "Ort nicht pruefbar: plan.pdf nicht lesbar",
        )


def test_leere_antwort_leerer_dateiname_unplausible_zahl_und_belegdeckel():
    assert check_citations("", DOCS, CITED) == []
    [blank] = check_citations("[[ |S. 3]]", DOCS, CITED)
    assert (blank.valid, blank.reason) == (False, "Datei nicht in der Wissensquelle")
    [huge] = check_citations("[[01_Stromlaufplan_FB-01.pdf|S. " + "1" * 5000 + "]]", DOCS, CITED)
    assert (huge.valid, huge.reason) == (False, "Ortsangabe unplausibel")
    many = check_citations(
        " ".join(f"[[01_Stromlaufplan_FB-01.pdf|S. {i}]]" for i in range(1, 251)), DOCS, CITED
    )
    assert summary(many)["total"] == 250
    assert [c.checked for c in many[200:]] == [False] * 50
    assert many[200].reason == "Nicht geprueft: mehr als 200 Belege"


def test_datei_ohne_endung_wird_ueber_den_stamm_gefunden():
    [c] = check_citations("[[01_Stromlaufplan_FB-01|S. 3]]", DOCS, CITED)
    assert (c.valid, c.checked) == (True, True)
