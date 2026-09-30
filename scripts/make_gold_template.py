"""Gold-Vorlage fuer eigene Dokumente (Issue #68): Kennzeichen je Seite aus dem heutigen Lesestand.

Aufruf:  python scripts/make_gold_template.py --doc testdata/private/anlage.pdf --out testdata/private/anlage.gold.json
                                              [--doc-type schematic]
Messen:  python eval/run_ingest.py --gold testdata/private/anlage.gold.json

Liest das Dokument ueber dieselbe Kette wie der Upload (eval/run_ingest.py, measure) und schreibt jeden Fund im
Gold-Format. Unveraendert misst sich die Vorlage mit Recall = Precision = 1,0. Aussagekraeftig wird sie erst, wenn
jede Seite von Hand gegen das Dokument geprueft ist: fehlende Kennzeichen ergaenzen, falsch gelesene loeschen.
Firmendokumente und ihre Vorlagen gehoeren nach testdata/private/ (gitignored). An eine Stelle, die git committen
wuerde, schreibt das Skript nicht.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "backend"))

import run_ingest  # noqa: E402

NOTE = (
    "Vorlage aus dem Lesestand von scripts/make_gold_template.py, noch keine Ground Truth: jede Seite von Hand "
    "gegen das Dokument pruefen, fehlende Kennzeichen ergaenzen, falsch gelesene loeschen."
)


def committable(path: Path) -> bool:
    """True, wenn path im Repo liegt und git ihn nicht ignoriert, also mit committet werden koennte."""
    target = path.resolve()
    try:
        target.relative_to(ROOT)
    except ValueError:
        return False
    return subprocess.run(["git", "check-ignore", "-q", str(target)], cwd=ROOT).returncode != 0


def detect_doc_type(doc: Path) -> str:
    # erst hier importiert: app liegt nur ueber sys.path vor, und ruff sortiert es je nach Startordner anders
    from app.ingestion.doctype import detect

    return str(detect(doc.name, doc).doc_type)


def template(doc: Path, doc_type: str, pages: run_ingest.Pages) -> dict:
    return {
        "dokument": run_ingest._relative(doc),
        "doc_type": doc_type,
        "generator": "scripts/make_gold_template.py",
        "hinweis": NOTE,
        "seiten": {
            str(page): {kind: sorted(tags) for kind, tags in sorted(pages[page].items())}
            for page in sorted(pages)
        },
    }


def main(argv: list[str] | None = None, measure_fn: run_ingest.Measure = run_ingest.measure) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--doc", type=Path, required=True, help="Dokument, z. B. testdata/private/anlage.pdf"
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Vorlage, z. B. testdata/private/anlage.gold.json"
    )
    parser.add_argument(
        "--doc-type", help="Dokumenttyp wie beim Upload; ohne Angabe erkannt wie bei 'auto'"
    )
    args = parser.parse_args(argv)
    if committable(args.out):
        print(
            f"{args.out} wuerde mit committet. Vorlagen fuer Firmendokumente nach testdata/private/ "
            "(ignoriert) oder ausserhalb des Repos schreiben.",
            file=sys.stderr,
        )
        return 2

    doc_type = args.doc_type or detect_doc_type(args.doc)
    pages, page_count, seconds = measure_fn(args.doc, doc_type)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(template(args.doc, doc_type, pages), ensure_ascii=False, indent=2) + "\n"
    args.out.write_text(text, encoding="utf-8", newline="\n")
    found = sum(len(tags) for by_type in pages.values() for tags in by_type.values())
    print(
        f"Vorlage {args.out}: {found} Kennzeichen auf {len(pages)} Seiten (Dokumenttyp {doc_type}, "
        f"{page_count or '-'} Seiten gelesen in {seconds:.1f} s). Jetzt jede Seite von Hand pruefen."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
