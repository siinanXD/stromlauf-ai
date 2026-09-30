"""Fremd-Testdaten per Skript (Issue #68): Manifest mit URL, SHA-256, Lizenz und Zielpfad, HTTP gemockt."""

import hashlib
import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "fetch_testdata", ROOT / "scripts" / "fetch_testdata.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch_testdata = _load()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


PDF = b"%PDF-1.4 QElectroTech-Beispiel"
# awlsim-Projekt wie auf GitHub, hier mit CRLF: Der XML-Parser vereinheitlicht die Zeilenenden
AWLPRO = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n<awlsim_project format_version="1">\r\n'
    b'\t<language_awl>\r\n\t\t<source enabled="1" name="Main" type="0"><![CDATA[\r\n'
    b"ORGANIZATION_BLOCK OB 1\r\nBEGIN\r\n\tU E 0.0\r\nEND_ORGANIZATION_BLOCK\r\n]]></source>\r\n"
    b"\t</language_awl>\r\n\t<symbols>\r\n"
    b'\t\t<source enabled="1" name="symbol table" type="1"><![CDATA[\r\n"S1","I 0.0","BOOL",""\r\n'
    b"]]></source>\r\n\t</symbols>\r\n</awlsim_project>\r\n"
)
AWL = (
    b"// ===== Quelle: Main =====\nORGANIZATION_BLOCK OB 1\nBEGIN\n\tU E 0.0\nEND_ORGANIZATION_BLOCK\n\n"
    b'// ===== Quelle: symbol table =====\n"S1","I 0.0","BOOL",""'
)
URL_PDF = "https://example.org/qet/industrial.pdf"
URL_AWLPRO = "https://example.org/awlsim/EXAMPLE.awlpro"
ENTRIES = [
    {"ziel": "qelectrotech/industrial.pdf", "url": URL_PDF, "sha256": _sha(PDF), "lizenz": "GPL"},
    {
        "ziel": "awl/EXAMPLE.awl",
        "url": URL_AWLPRO,
        "auspacken": "awlpro",
        "sha256": _sha(AWL),
        "lizenz": "GPL-2.0-or-later",
    },
]


@pytest.fixture
def http(monkeypatch):
    """Gemocktes HTTP: urlopen liefert die Bytes je URL und zaehlt die Aufrufe."""
    served = {URL_PDF: PDF, URL_AWLPRO: AWLPRO}
    calls: list[str] = []

    def urlopen(request, timeout=None):
        url = getattr(request, "full_url", request)
        calls.append(url)
        if url not in served:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return io.BytesIO(served[url])

    monkeypatch.setattr(fetch_testdata.urllib.request, "urlopen", urlopen)
    return served, calls


def _run(tmp_path: Path, entries: list[dict] = ENTRIES) -> int:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"dateien": entries}), encoding="utf-8")
    return fetch_testdata.main(["--manifest", str(manifest), "--ziel", str(tmp_path / "testdata")])


def test_erster_lauf_laedt_und_prueft_der_zweite_laedt_nichts(tmp_path, http, capsys):
    _, calls = http
    assert _run(tmp_path) == 0
    target = tmp_path / "testdata"
    assert (target / "qelectrotech" / "industrial.pdf").read_bytes() == PDF
    # awlsim-Projekt ausgepackt: alle Quellen in Dokumentreihenfolge, LF statt CRLF
    assert (target / "awl" / "EXAMPLE.awl").read_bytes() == AWL
    assert calls == [URL_PDF, URL_AWLPRO]
    assert "2 geladen" in capsys.readouterr().out

    assert _run(tmp_path) == 0
    assert calls == [URL_PDF, URL_AWLPRO]  # zweiter Lauf: Pruefsummen stimmen, kein Download
    assert "2 vorhanden" in capsys.readouterr().out


def test_manipulierte_datei_ergibt_exit_1_und_bleibt_unveraendert(tmp_path, http, capsys):
    _, calls = http
    assert _run(tmp_path) == 0
    pdf = tmp_path / "testdata" / "qelectrotech" / "industrial.pdf"
    pdf.write_bytes(PDF + b" manipuliert")
    capsys.readouterr()

    assert _run(tmp_path) == 1
    assert pdf.read_bytes() == PDF + b" manipuliert"  # nichts ueberschrieben, der Owner entscheidet
    assert calls == [URL_PDF, URL_AWLPRO]
    out = capsys.readouterr().out
    assert "qelectrotech/industrial.pdf" in out and "Pruefsumme weicht ab" in out


def test_falscher_download_wird_nicht_abgelegt(tmp_path, http, capsys):
    served, _ = http
    served[URL_PDF] = b"%PDF-1.4 andere Fassung"
    assert _run(tmp_path) == 1
    target = tmp_path / "testdata"
    files = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    assert files == ["awl/EXAMPLE.awl"]  # keine halbe Datei, kein .part
    assert "Download mit falscher Pruefsumme" in capsys.readouterr().out


def test_fehlgeschlagener_download_ergibt_exit_1(tmp_path, http, capsys):
    served, _ = http
    del served[URL_PDF]
    assert _run(tmp_path) == 1
    assert not (tmp_path / "testdata" / "qelectrotech").exists()
    assert "404" in capsys.readouterr().out


def test_eintrag_ohne_url_wird_nur_geprueft(tmp_path, http, capsys):
    """Festo: Download-Quelle nennt der Owner (Issue #68). Bis dahin von Hand ablegen, das Skript prueft nur."""
    handbook = b"%PDF-1.4 Festo"
    manual = {
        "ziel": "festo/Handbuch.pdf",
        "url": None,
        "quelle": "TODO Owner",
        "sha256": _sha(handbook),
        "lizenz": "Festo Didactic, nur lokal",
    }
    _, calls = http
    assert _run(tmp_path, [manual]) == 0
    assert calls == [] and "1 ohne Quelle" in capsys.readouterr().out

    path = tmp_path / "testdata" / "festo" / "Handbuch.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(handbook)
    assert _run(tmp_path, [manual]) == 0
    assert "1 vorhanden" in capsys.readouterr().out

    path.write_bytes(b"%PDF-1.4 andere")
    assert _run(tmp_path, [manual]) == 1


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"url": "http://example.org/x.pdf"}, "https"),
        ({"ziel": "../x.pdf"}, "ziel"),
        ({"ziel": "/etc/x.pdf"}, "ziel"),
        ({"sha256": "abc"}, "sha256"),
        ({"lizenz": ""}, "lizenz"),
        ({"auspacken": "zip"}, "auspacken"),
    ],
)
def test_manifest_lehnt_ungueltige_eintraege_ab(tmp_path, change, message):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"dateien": [{**ENTRIES[0], **change}]}), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        fetch_testdata.load_manifest(manifest)


def test_manifest_lehnt_doppelte_ziele_ab(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"dateien": [ENTRIES[0], ENTRIES[0]]}), encoding="utf-8")
    with pytest.raises(ValueError, match="doppelt"):
        fetch_testdata.load_manifest(manifest)


def test_manifest_im_repo_nennt_quelle_und_lizenz_je_datei():
    entries = fetch_testdata.load_manifest(fetch_testdata.MANIFEST)
    folders: dict[str, list] = {}
    for entry in entries:
        folders.setdefault(entry.ziel.split("/")[0], []).append(entry)
    assert sorted(folders) == ["awl", "festo", "qelectrotech"]
    assert all(
        e.url.startswith("https://download.qelectrotech.org/qet/schemas_pdf/")
        for e in folders["qelectrotech"]
    )
    # awlsim mit festem Git-Tag, nicht master: dieselben Bytes auf jedem Klon
    assert len(folders["awl"]) == 11
    assert all(
        e.url.startswith("https://raw.githubusercontent.com/mbuesch/awlsim/awlsim-0.77.1/")
        for e in folders["awl"]
    )
    assert all(e.url is None and "TODO Owner" in e.quelle for e in folders["festo"])


@pytest.mark.skipif(
    not (ROOT / "testdata" / "awl").exists(), reason="Fremd-Testdaten liegen nur lokal (testdata/)"
)
def test_manifest_passt_zu_den_lokalen_testdaten():
    entries = fetch_testdata.load_manifest(fetch_testdata.MANIFEST)
    local = {e.ziel: ROOT / "testdata" / e.ziel for e in entries}
    present = [e for e in entries if local[e.ziel].exists()]
    assert present
    assert [e.ziel for e in present if _sha(local[e.ziel].read_bytes()) != e.sha256] == []
