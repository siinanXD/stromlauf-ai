"""Ingest-Benchmark (Issue #63): Metrik, Gold aus dem Generator und CLI-Gate, ohne Docling und ohne Datenbank."""

import importlib.util
import json
import re
from collections import namedtuple
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "eval" / "ingest_gold" / "fb01.json"
EXAMPLE_DOCS = ROOT / "scripts" / "example_docs"
TYPES = ("device", "terminal", "plc_address", "cross_ref")


def _load(name: str, folder: Path):
    spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_ingest = _load("run_ingest", ROOT / "eval")

PAGES = {
    1: {"device": {"-K1", "-K2"}, "terminal": {"-X1", "-X1:5"}},
    2: {"plc_address": {"E0.0"}, "cross_ref": {"/3.4"}},
}


def _copy(pages: dict) -> dict:
    return {
        page: {kind: set(tags) for kind, tags in by_type.items()} for page, by_type in pages.items()
    }


def test_gleiche_mengen_ergeben_recall_und_precision_eins():
    metrics, deviations = run_ingest.compare(_copy(PAGES), _copy(PAGES))
    assert all(metrics[t]["recall"] == 1.0 and metrics[t]["precision"] == 1.0 for t in TYPES)
    assert deviations == []


def test_gold_ohne_ein_kennzeichen_senkt_die_precision_um_genau_einen_fund():
    gold = _copy(PAGES)
    gold[1]["device"].discard("-K2")
    metrics, deviations = run_ingest.compare(gold, _copy(PAGES))
    assert metrics["device"]["precision"] == pytest.approx(1 / 2)
    assert metrics["device"]["recall"] == 1.0 and metrics["device"]["fp"] == 1
    assert deviations == [{"seite": 1, "fehlend": {}, "fremd": {"device": ["-K2"]}}]


def test_erfundenes_kennzeichen_im_gold_senkt_den_recall_um_genau_einen_treffer():
    gold = _copy(PAGES)
    gold[1]["terminal"].add("-X1:9")
    metrics, deviations = run_ingest.compare(gold, _copy(PAGES))
    assert metrics["terminal"]["recall"] == pytest.approx(2 / 3)
    assert metrics["terminal"]["precision"] == 1.0 and metrics["terminal"]["fn"] == 1
    assert deviations == [{"seite": 1, "fehlend": {"terminal": ["-X1:9"]}, "fremd": {}}]


def test_funde_auf_seiten_ohne_gold_zaehlen_als_fremd():
    found = _copy(PAGES)
    found[3] = {"device": {"-Q9"}}
    metrics, deviations = run_ingest.compare(_copy(PAGES), found)
    assert metrics["device"]["fp"] == 1 and metrics["device"]["precision"] == pytest.approx(2 / 3)
    assert deviations == [{"seite": 3, "fehlend": {}, "fremd": {"device": ["-Q9"]}}]


def test_gate_meldet_jeden_typ_unter_der_schwelle_und_typen_ohne_gold():
    metrics = {
        "device": {"recall": 0.9, "precision": 1.0},
        "terminal": {"recall": 1.0, "precision": 0.96},
        "plc_address": {"recall": None, "precision": None},
    }
    failures = run_ingest.gate_failures(metrics, 0.95, ["device", "terminal", "plc_address"])
    assert failures == ["device: Recall 0.90 < 0.95", "plc_address: kein Gold fuer diesen Typ"]
    assert run_ingest.gate_failures(metrics, 0.9, ["device", "terminal"]) == []


def test_schwelle_je_typ_ueberschreibt_die_gemeinsame():
    """Issue #66: Klemmen auf dem Scan bleiben unter 0,95; ihr Gate liegt bei 0,75, die anderen Typen bei 0,95."""
    metrics = {
        "device": {"recall": 0.99, "precision": 1.0},
        "terminal": {"recall": 0.77, "precision": 1.0},
    }
    types = ["device", "terminal"]
    assert run_ingest.gate_failures(metrics, 0.95, types) == ["terminal: Recall 0.77 < 0.95"]
    assert run_ingest.gate_failures(metrics, 0.95, types, {"terminal": 0.75}) == []
    assert run_ingest.gate_failures(metrics, 0.95, types, {"terminal": 0.8}) == [
        "terminal: Recall 0.77 < 0.80"
    ]
    assert run_ingest.parse_minimums(["terminal=0.75", "device=0.9"]) == {
        "terminal": 0.75,
        "device": 0.9,
    }
    with pytest.raises(ValueError, match="geraet"):
        run_ingest.parse_minimums(["geraet=0.5"])


def test_by_page_gruppiert_nach_seite_und_typ_und_verliert_seitenlose_funde_nicht():
    Row = namedtuple("Row", "tag tag_type page")
    rows = [
        Row("-K1", "device", 1),
        Row("-X1", "terminal", 1),
        Row("-K1", "device", 1),
        Row("-K2", "device", None),
    ]
    assert run_ingest.by_page(rows) == {
        1: {"device": {"-K1"}, "terminal": {"-X1"}},
        0: {"device": {"-K2"}},
    }


def test_load_gold_lehnt_unbekannte_typen_ab(tmp_path):
    path = tmp_path / "kaputt.json"
    path.write_text(
        json.dumps(
            {"dokument": "x.pdf", "doc_type": "schematic", "seiten": {"1": {"geraet": ["-K1"]}}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="geraet"):
        run_ingest.load_gold(path)


def test_cli_schreibt_json_und_markdown_und_scheitert_unter_der_schwelle(tmp_path):
    gold = tmp_path / "mini.json"
    gold.write_text(
        json.dumps(
            {
                "dokument": "examples/x.pdf",
                "doc_type": "schematic",
                "seiten": {"1": {"device": ["-K1", "-K2"]}},
            }
        ),
        encoding="utf-8",
    )
    seen = []

    def fake_measure(doc: Path, doc_type: str):
        seen.append((doc, doc_type))
        return {1: {"device": {"-K1"}}}, 1, 2.0

    args = ["--gold", str(gold), "--types", "device", "--out", str(tmp_path)]
    assert run_ingest.main([*args, "--min", "0.95"], measure_fn=fake_measure) == 1
    assert seen == [
        (ROOT / "examples" / "x.pdf", "schematic")
    ]  # Dokument aus dem Gold, relativ zum Repo
    result = json.loads(next(tmp_path.glob("ingest_mini_*.json")).read_text(encoding="utf-8"))
    summary = result["summary"]
    assert summary["metriken"]["device"]["recall"] == 0.5
    assert summary["gate"] == {
        "min": 0.95,
        "min_je_typ": {},
        "typen": ["device"],
        "ok": False,
        "verfehlt": ["device: Recall 0.50 < 0.95"],
    }
    assert result["results"] == [{"seite": 1, "fehlend": {"device": ["-K2"]}, "fremd": {}}]
    markdown = next(tmp_path.glob("ingest_mini_*.md")).read_text(encoding="utf-8")
    assert "| device | 2 | 1 | 1 | 0.50 | 1.00 |" in markdown and "Seite 1" in markdown
    assert run_ingest.main([*args, "--min", "0.5"], measure_fn=fake_measure) == 0


def test_cli_ocr_misst_das_durchsuchbare_pdf_und_schreibt_die_ocr_kennzahlen(tmp_path):
    """Issue #65: --ocr erzeugt vor der Messung die unsichtbare Textebene und misst diese Fassung."""
    gold = tmp_path / "mini.json"
    gold.write_text(
        json.dumps(
            {"dokument": "x.pdf", "doc_type": "schematic", "seiten": {"1": {"device": ["-K1"]}}}
        ),
        encoding="utf-8",
    )
    scan = tmp_path / "x_scan.pdf"
    measured = []

    def fake_ocr(doc: Path, out_dir: Path):
        return out_dir / f"{doc.stem}_ocr.pdf", {"seiten": [1], "sekunden": 3.0, "konfidenz": 0.95}

    def fake_measure(doc: Path, doc_type: str):
        measured.append(doc.name)
        return {1: {"device": {"-K1"}}}, 1, 1.0

    args = [
        "--gold",
        str(gold),
        "--doc",
        str(scan),
        "--ocr",
        "--label",
        "scan-ocr",
        "--out",
        str(tmp_path),
    ]
    assert run_ingest.main(args, measure_fn=fake_measure, ocr_fn=fake_ocr) == 0
    assert measured == ["x_scan_ocr.pdf"]
    summary = json.loads(
        next(tmp_path.glob("ingest_mini_scan-ocr_*.json")).read_text(encoding="utf-8")
    )["summary"]
    assert summary["ocr"] == {"seiten": [1], "sekunden": 3.0, "konfidenz": 0.95}
    assert summary["dokument"].endswith(
        "x_scan.pdf"
    )  # gemessen wird die OCR-Fassung, genannt das Original
    markdown = next(tmp_path.glob("ingest_mini_scan-ocr_*.md")).read_text(encoding="utf-8")
    assert "OCR: 1 Seiten, 3.0 s, Konfidenz 0.95" in markdown


def test_cli_label_trennt_laeufe_verschiedener_fassungen_desselben_plans(tmp_path):
    """Issue #64: Scan und Teil-Scan werden gegen dasselbe Gold gemessen und brauchen eigene Dateinamen."""
    gold = tmp_path / "mini.json"
    gold.write_text(
        json.dumps(
            {"dokument": "x.pdf", "doc_type": "schematic", "seiten": {"1": {"device": ["-K1"]}}}
        ),
        encoding="utf-8",
    )
    args = [
        "--gold",
        str(gold),
        "--doc",
        str(tmp_path / "x_scan.pdf"),
        "--label",
        "scan",
        "--out",
        str(tmp_path),
    ]
    assert run_ingest.main(args, measure_fn=lambda *_: ({}, 1, 1.0)) == 0
    result = json.loads(next(tmp_path.glob("ingest_mini_scan_*.json")).read_text(encoding="utf-8"))
    assert result["summary"]["label"] == "scan"
    assert (
        next(tmp_path.glob("ingest_mini_scan_*.md"))
        .read_text(encoding="utf-8")
        .startswith("# Ingest-Benchmark mini (scan)")
    )


def test_cli_lehnt_unbekannte_typen_im_gate_ab(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        run_ingest.main(
            ["--gold", str(GOLD), "--types", "geraet"], measure_fn=lambda *_: ({}, 0, 0.0)
        )
    assert exit_info.value.code == 2


@pytest.fixture(scope="module")
def make_gold():
    pytest.importorskip(
        "reportlab"
    )  # nur im Extra "examples"; der Backend-Job der CI installiert es
    return _load("make_gold", EXAMPLE_DOCS)


@pytest.mark.parametrize("name", ["fb01", "ur01", "pm1_ar"])
def test_gold_datei_passt_zum_generator(make_gold, name):
    path = ROOT / "eval" / "ingest_gold" / f"{name}.json"
    assert path.exists(), "python scripts/example_docs/make_gold.py --write"
    # read_text normalisiert die Zeilenenden (core.autocrlf)
    assert path.read_text(encoding="utf-8") == make_gold.render(name)


@pytest.mark.parametrize("name", ["fb01", "ur01", "pm1_ar"])
def test_jedes_gold_der_generatoren_steht_im_ingest_gate(name):
    workflow = (ROOT / ".github" / "workflows" / "eval.yml").read_text(encoding="utf-8")
    assert re.search(rf"run_ingest\.py --gold eval/ingest_gold/{name}\.json --min 0\.95 ", workflow)


@pytest.mark.parametrize("name", ["ur01", "pm1_ar"])
def test_testdoku_gold_nennt_jedes_betriebsmittel_und_jede_seite_des_plans(make_gold, name):
    """Issue #68: UR-01 und PM1-AR im Ingest-Gate, Gold beim Zeichnen mitgeschrieben wie bei FB-01."""
    import pypdfium2 as pdfium

    gold = run_ingest.load_gold(ROOT / "eval" / "ingest_gold" / f"{name}.json")
    tags = {
        tag
        for by_type in gold["seiten"].values()
        for kind in ("device", "terminal")
        for tag in by_type.get(kind, ())
    }
    devices = make_gold.testdoku_machine(name).devices
    assert [device.bmk for device in devices if device.bmk not in tags] == []
    pdf = pdfium.PdfDocument(str(ROOT / gold["dokument"]))
    try:
        assert sorted(gold["seiten"]) == list(range(1, len(pdf) + 1))
    finally:
        pdf.close()


def test_jedes_betriebsmittel_der_stueckliste_steht_im_gold(make_gold):
    import data  # scripts/example_docs/data.py, ueber make_gold im Pfad

    gold = run_ingest.load_gold(GOLD)
    tags = {
        tag
        for by_type in gold["seiten"].values()
        for kind in ("device", "terminal")
        for tag in by_type.get(kind, ())
    }
    assert [bmk for bmk, *_ in data.DEVICES if bmk not in tags] == []
    assert sorted(gold["seiten"]) == [page for page, _ in data.PAGES]


def test_gold_zaehlt_je_gezeichneter_zeichenkette_nicht_je_seitentext(make_gold):
    """Auf Blatt 3 stehen "/6.5" und "1/2" nebeneinander; pdfium liest daraus "/6.51"."""
    cross_refs = run_ingest.load_gold(GOLD)["seiten"][3]["cross_ref"]
    assert "/6.5" in cross_refs and "/6.51" not in cross_refs
