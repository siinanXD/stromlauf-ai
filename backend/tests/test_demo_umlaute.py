"""Sichtbare Demo-Texte haben echte Umlaute, keine ASCII-Umschrift (SIN-1463).

Die Beispielanlage FB-01 ist die Demo. "Foerderband", "Schuetz", "vorwaerts", "Oeffner" standen in Namen, Stueckliste,
Klemmenplan, Anleitung und Plan und sahen in der Anzeige falsch aus. Bezeichner im SPS-Programm und in der
Symboltabelle (`K1_Vorwaerts`, `Stoerung`) bleiben ASCII, sie sind keine Texte, und zaehlen deshalb hier nicht.
Dateinamen auch nicht: `02_Stueckliste_FB-01.xlsx` ist ein Pfad, auf den Lader, Tests und CI zeigen.
"""

import ast
import csv
import io
import re
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from openpyxl import load_workbook

from app import demo

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "foerderband"

ASCII_UMSCHRIFT = set(
    """Abkuehlen Aenderungen Ausgaenge Bestimmungsgemaesse Betriebsstundenzaehler Blaetter Digitalausgaenge
    Digitaleingaenge Druecken Eingaenge Feldgeraet Feldgeraete Foerderband Foerderbandsteuerung Foerdermotor Gehaeuse
    Geraet Halbjaehrlich Jaehrlich Kanaele Leistungsschuetz Moegliche Oeffner Pruefung Ruecksetzen Rueckwaerts
    Rueckwaertsbetrieb Sammelstoerung Schliesser Schuetz Schuetzes Schuetzspulen Sicherheitsschaltgeraet Stoerung
    Stoerungen Stoerungsauswertung Stueckliste Stueckzaehlung Stueckzahl Ueberlast Ueberwachung Vorwaerts Wendeschuetz
    Wendeschuetze Werkstuecke Zaehler Zaehlwerk Zielgeraet Zugehoerige abschliessbar abschliessen aehnliches ausfuehren
    ausgeloest ausserhalb betaetigen betaetigt betaetigten druecken duerfen faellt fuenf fuer gruen haengt laedt laeuft
    loest moeglich muessen noetig oeffnet pruefen sekundaer ueber ueberall uebergibt uebernimmt unabhaengig vollstaendiger
    zaehlt zurueck zuruecksetzen zusaetzlich zusammenfuehren""".split()
)
# Bezeichner mit Unterstrich (`K1_Vorwaerts`) sind ein Wort fuer sich und zaehlen nicht
_WORD = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]+(?![A-Za-z0-9_])")


def umschrift(text: str) -> set[str]:
    return {
        word for word in _WORD.findall(text) if word.lower() in {w.lower() for w in ASCII_UMSCHRIFT}
    }


def awl_texte(text: str) -> str:
    """Kommentare und TITLE-Zeilen des AWL-Programms; der Code dazwischen (Variablennamen) ist ASCII."""
    teile = []
    for zeile in text.splitlines():
        if "//" in zeile:
            teile.append(zeile.split("//", 1)[1])
        elif zeile.startswith("TITLE ="):
            teile.append(zeile[len("TITLE =") :])
    return "\n".join(teile)


def pdf_text(pfad: Path) -> str:
    pdf = pdfium.PdfDocument(str(pfad))
    try:
        return "\n".join(page.get_textpage().get_text_range() for page in pdf)
    finally:
        pdf.close()


def xlsx_text(pfad: Path) -> str:
    book = load_workbook(pfad)
    zellen = [
        str(cell.value) for sheet in book for row in sheet.iter_rows() for cell in row if cell.value
    ]
    return "\n".join([*book.sheetnames, *zellen])


def sdf_text(pfad: Path) -> str:
    """Nur die Kommentarspalte der Symboltabelle (Symbol, Adresse, Typ, Kommentar)."""
    zeilen = csv.reader(io.StringIO(pfad.read_text(encoding="latin-1")))
    return "\n".join(zeile[3] for zeile in zeilen if len(zeile) > 3)


def demo_texte() -> str:
    """Alle Saetze in demo.py (Zeichenketten mit Leerzeichen, ohne Docstrings): Beschreibungen, Fehlerliste, Meldung."""
    baum = ast.parse(Path(demo.__file__).read_text(encoding="utf-8"))
    scopes = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(baum)
        if isinstance(node, scopes) and node.body and isinstance(node.body[0], ast.Expr)
    }
    return "\n".join(
        node.value
        for node in ast.walk(baum)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and " " in node.value
        and id(node) not in docstrings
    )


def quellen() -> dict[str, str]:
    return {
        "demo.py": " ".join([demo.SOURCE_NAME, demo.HALL_NAME, demo_texte()]),
        "README.md": (EXAMPLE / "README.md").read_text(encoding="utf-8"),
        "01 Stromlaufplan": pdf_text(EXAMPLE / "01_Stromlaufplan_FB-01.pdf"),
        "02 Stueckliste": xlsx_text(EXAMPLE / "02_Stueckliste_FB-01.xlsx"),
        "03 Klemmenplan": (EXAMPLE / "03_Klemmenplan_FB-01.csv").read_text(encoding="utf-8"),
        "04 SPS-Programm": awl_texte(
            (EXAMPLE / "04_SPS_Programm_FB-01.awl").read_text(encoding="utf-8")
        ),
        "05 Symboltabelle": sdf_text(EXAMPLE / "05_Symboltabelle_FB-01.sdf"),
        "06 Betriebsanleitung": (EXAMPLE / "06_Betriebsanleitung_FB-01.md").read_text(
            encoding="utf-8"
        ),
        "07 Schaltschrank-Bauteile": (EXAMPLE / "07_Schaltschrank_Hotspots_FB-01.json").read_text(
            encoding="utf-8"
        ),
    }


@pytest.mark.parametrize(("name", "text"), quellen().items())
def test_keine_ascii_umschrift_in_sichtbaren_demo_texten(name, text):
    assert umschrift(text) == set(), f"{name}: ASCII-Umschrift statt Umlaut"


def test_die_demo_zeigt_die_echten_woerter():
    alle = " ".join(quellen().values())
    for wort in ("Förderband", "Schütz", "vorwärts", "Öffner", "Störung", "Stückliste"):
        assert wort in alle, wort
    assert demo.SOURCE_NAME == "Förderband FB-01"


def test_die_pruefung_erkennt_umschrift():
    assert umschrift("Schuetz Foerdermotor vorwaerts, Oeffner") == {
        "Schuetz",
        "Foerdermotor",
        "vorwaerts",
        "Oeffner",
    }
    assert umschrift("K1_Vorwaerts und Stoer_Quitt") == set()
    assert umschrift("Schütz Fördermotor vorwärts, Öffner") == set()
    assert "Stoerung" in umschrift(awl_texte("Stop : BOOL ;\t//Stoerung quittiert"))
    assert umschrift(awl_texte("  Vorwaerts : BOOL ;")) == set()
