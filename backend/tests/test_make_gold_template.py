"""Gold-Vorlage fuer eigene Dokumente (Issue #68): Vorlage aus dem Lesestand, Ablage nur an ignorierten Stellen."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, folder: Path):
    spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


make_gold_template = _load("make_gold_template", ROOT / "scripts")
run_ingest = _load("run_ingest", ROOT / "eval")

TYPES = ("device", "terminal", "plc_address", "cross_ref", "device_pin")
FOUND = {
    1: {"device": {"-K1", "-K2"}, "terminal": {"-X1:5"}, "device_pin": {"-K1:A1"}},
    10: {"plc_address": {"E0.0"}, "cross_ref": {"/3.4"}},
    2: {"device": {"-Q1"}},
    0: {"device": {"-F9"}},  # Fund ohne Seite (Nicht-PDF) bleibt erhalten
}


def _fake_measure(seen: list | None = None):
    def measure(doc: Path, doc_type: str):
        if seen is not None:
            seen.append((doc, doc_type))
        pages = {page: {k: set(v) for k, v in found.items()} for page, found in FOUND.items()}
        return pages, 10, 1.0

    return measure


def test_vorlage_misst_sich_unveraendert_mit_recall_und_precision_eins(tmp_path):
    doc, out = tmp_path / "anlage.pdf", tmp_path / "anlage.gold.json"
    doc.write_bytes(b"%PDF-1.4")
    args = ["--doc", str(doc), "--out", str(out), "--doc-type", "schematic"]
    assert make_gold_template.main(args, measure_fn=_fake_measure()) == 0

    results = tmp_path / "results"
    gate = ["--min", "1.0", "--types", ",".join(TYPES), "--out", str(results)]
    assert run_ingest.main(["--gold", str(out), *gate], measure_fn=_fake_measure()) == 0
    result = next(results.glob("ingest_anlage.gold_*.json")).read_text(encoding="utf-8")
    metrics = json.loads(result)["summary"]["metriken"]
    assert {kind: (m["recall"], m["precision"]) for kind, m in metrics.items()} == {
        kind: (1.0, 1.0) for kind in TYPES
    }


def test_vorlage_ist_als_vorlage_gekennzeichnet_und_nach_seiten_sortiert(tmp_path):
    doc, out = tmp_path / "anlage.pdf", tmp_path / "anlage.gold.json"
    doc.write_bytes(b"%PDF-1.4")
    args = ["--doc", str(doc), "--out", str(out), "--doc-type", "schematic"]
    make_gold_template.main(args, measure_fn=_fake_measure())
    gold = json.loads(out.read_text(encoding="utf-8"))
    assert list(gold["seiten"]) == ["0", "1", "2", "10"]
    assert gold["seiten"]["1"] == {
        "device": ["-K1", "-K2"],
        "device_pin": ["-K1:A1"],
        "terminal": ["-X1:5"],
    }
    assert gold["doc_type"] == "schematic" and gold["generator"] == "scripts/make_gold_template.py"
    assert "Vorlage" in gold["hinweis"] and "von Hand" in gold["hinweis"]


def test_dokumenttyp_wird_erkannt_wenn_er_fehlt(tmp_path):
    seen: list = []
    doc = ROOT / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
    out = tmp_path / "fb01.gold.json"
    args = ["--doc", str(doc), "--out", str(out)]  # ohne --doc-type
    assert make_gold_template.main(args, measure_fn=_fake_measure(seen)) == 0
    assert seen == [(doc, "schematic")]
    assert json.loads(out.read_text(encoding="utf-8"))["dokument"] == (
        "examples/foerderband/01_Stromlaufplan_FB-01.pdf"
    )


def test_vorlage_landet_nie_an_einer_stelle_die_git_committen_wuerde(tmp_path, capsys):
    """Firmendaten gehoeren nach testdata/private/ (ignoriert) oder ausserhalb des Repos, nie in eval/ingest_gold/."""
    assert make_gold_template.committable(ROOT / "eval" / "ingest_gold" / "vorlage_test.json")
    assert not make_gold_template.committable(ROOT / "testdata" / "private" / "anlage.gold.json")
    assert not make_gold_template.committable(tmp_path / "anlage.gold.json")

    doc, out = tmp_path / "anlage.pdf", ROOT / "eval" / "ingest_gold" / "vorlage_test.json"
    doc.write_bytes(b"%PDF-1.4")
    seen: list = []
    args = ["--doc", str(doc), "--out", str(out), "--doc-type", "schematic"]
    assert make_gold_template.main(args, measure_fn=_fake_measure(seen)) == 2
    assert not out.exists() and seen == []  # abgelehnt, bevor das Dokument gelesen wird
    assert "testdata/private/" in capsys.readouterr().err
