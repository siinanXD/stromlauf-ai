"""scripts/load_folder.py: welche Dateien eines Ordners als Wissensquelle geladen werden."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "load_folder", ROOT / "scripts" / "load_folder.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readme_des_ordners_ist_doku_und_keine_kundendatei(tmp_path: Path):
    for name in (
        "README.md",
        "readme.MD",
        "Betriebsanleitung.md",
        "plan.pdf",
        "notizen.txt",
        "bild.svg",
        "Readme.txt",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "unterordner").mkdir()
    load_folder = _load()
    assert [p.name for p in load_folder.candidate_files(tmp_path)] == [
        "Betriebsanleitung.md",
        "notizen.txt",
        "plan.pdf",
    ]
