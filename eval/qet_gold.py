"""Ground Truth fuer die QElectroTech-Testdaten aus deren Stueckliste (Issue #67): Geraet -> Folio -> Seite.

Aufruf:  python eval/qet_gold.py [--pdf testdata/qelectrotech/QET_Beispielprojekt_industrial_50S.pdf]
                                 [--out testdata/qelectrotech/qet.json]
Messen:  python eval/run_ingest.py --gold testdata/qelectrotech/qet.json --types device

Die Testdaten (GPL v2+, https://download.qelectrotech.org/qet/schemas_pdf/) liegen nur lokal unter testdata/, bis
die Lizenzfrage geklaert ist; das Gold deshalb auch. Die Stueckliste ("Nomenclature") nennt je Zeile Folio,
Folio-Titel, Kennzeichen und Bezeichnung: "4 Mains Power Supply 4Q1 80A". Das Folio wird ueber die Blatt-Map zur
PDF-Seite, und zwar nur ueber im Schriftfeld gelesene Nummern. Als Kennzeichen zaehlt, was tags.extract_tags im
Blatt-Stil aus der Zeile liest und mit dem Folio der Zeile beginnt (4Q1, 5F31); so misst das Gold das Lesen der
Planseiten, nicht die Grammatik (4EH, X1 oder 9HF liest sie nicht). Precision ist hier nicht aussagekraeftig:
Kontakte eines Schuetzes tragen sein Kennzeichen auch auf anderen Folios.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_PDF = ROOT / "testdata" / "qelectrotech" / "QET_Beispielprojekt_industrial_50S.pdf"
_ROW = re.compile(r"^(\d{1,3})\s+(\S.*)$")


def nomenclature_rows(lines: list[str]) -> list[tuple[int, str]]:
    """(Folio, Kennzeichen) je Stuecklistenzeile, deren Kennzeichen mit ihrem Folio beginnt."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.ingestion.tags import TagType, extract_tags

    rows = []
    for line in lines:
        match = _ROW.match(line.strip())
        if not match:
            continue
        folio, rest = int(match.group(1)), match.group(2)
        tags = [
            tag.tag
            for tag in extract_tags(rest, folio_style=True)
            if tag.tag_type == TagType.DEVICE and re.match(rf"{folio}[A-Z]", tag.tag)
        ]
        if tags:
            rows.append((folio, tags[0]))
    return rows


def _relative(path: Path) -> str:
    """Pfad relativ zum Repo wie in eval/ingest_gold; testdata/ darf ein Link auf den Haupt-Checkout sein."""
    try:
        return path.absolute().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_gold(pdf: Path) -> dict:
    """Gold im Format von eval/ingest_gold: Seite -> {"device": [...]}, nur Planseiten."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.ingestion.docling_parser import ParsedPage, pdf_raw_text
    from app.ingestion.page_titles import page_titles
    from app.ingestion.pdf_layout import sheet_map

    raw = pdf_raw_text(pdf)
    sheets = sheet_map(pdf)
    parsed = [ParsedPage(page=page, markdown="", raw_text=text) for page, text in sorted(raw.items())]
    _titles, parts = page_titles(parsed, sheets.page_sheets)
    if not parts:
        raise ValueError(f"{pdf.name}: keine Stuecklistenseite (Nomenclature)")
    pages: dict[int, set[str]] = {}
    for page in sorted(parts):
        for folio, tag in nomenclature_rows(raw[page].splitlines()):
            found = sheets.page_of(folio)
            if found.page is None or found.guessed:
                raise ValueError(f"{pdf.name}: Folio {folio} steht in keinem gelesenen Schriftfeld")
            pages.setdefault(found.page, set()).add(tag)
    return {
        "dokument": _relative(pdf),
        "doc_type": "schematic",
        "generator": "eval/qet_gold.py",
        "hinweis": "Geraet -> Folio aus der Stueckliste (Nomenclature), Folio -> Seite ueber die Blatt-Map; "
        "nur lokal, Testdaten nicht im Repo. Precision nicht aussagekraeftig (Kontakte tragen das "
        "Kennzeichen ihres Geraets auch auf anderen Folios).",
        "seiten": {str(page): {"device": sorted(tags)} for page, tags in sorted(pages.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, help="Standard: qet.json neben der PDF")
    args = parser.parse_args()
    if not args.pdf.exists():
        sys.exit(f"{args.pdf} fehlt: QElectroTech-Testdaten liegen nur lokal (testdata/README.md)")
    gold = build_gold(args.pdf)
    out = args.out or args.pdf.with_name("qet.json")
    out.write_text(json.dumps(gold, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    count = sum(len(entry["device"]) for entry in gold["seiten"].values())
    print(f"{count} Kennzeichen auf {len(gold['seiten'])} Seiten -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
