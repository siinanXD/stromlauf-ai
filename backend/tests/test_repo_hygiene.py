"""Oeffentliches Repository (Issue #51): Lizenz, Manifeste, Doku ohne "privat", Secret-Scan im CI, keine Fremddaten."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_lizenz_liegt_im_root_und_in_beiden_manifesten():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License") and "Sinan Kahraman" in text and "2026" in text
    assert re.search(
        r'^license = "MIT"$',
        (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    )
    assert (
        json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))["license"]
        == "MIT"
    )
    assert "MIT" in (ROOT / "examples" / "foerderband" / "README.md").read_text(encoding="utf-8")


def test_doku_behauptet_kein_privates_repo_und_keine_ci_von_hand():
    for name in ("README.md", "AGENTS.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "(privat" not in text and "privates Repo" not in text, name
        assert "nur per Hand" not in text and "nur von Hand startbar" not in text, name


def test_secret_scan_prueft_die_ganze_historie_mit_fester_version():
    """gitleaks-action prueft bei PR und Push nur die neuen Commits. Die CI ruft gitleaks darum selbst auf, mit
    fester Version und Pruefsumme, ueber alle Commits bis zum geprueften Stand (nicht die Branches anderer PRs)."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "fetch-depth: 0" in ci and "gitleaks/gitleaks-action" not in ci
    assert re.search(r"GITLEAKS_VERSION: \d+\.\d+\.\d+", ci)
    assert re.search(r"GITLEAKS_SHA256: [0-9a-f]{64}", ci) and "sha256sum --check" in ci
    assert '--log-opts="--full-history HEAD"' in ci


def test_gitleaks_nimmt_nur_die_festen_testwerte_der_tests_aus():
    config = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
    assert "useDefault = true" in config and "paths" not in config and "commits" not in config
    allowed = re.findall(r"regexes = \['''(.+?)'''\]", config)
    assert allowed == ["secret-0123456789"]
    secrets = [
        value
        for path in (ROOT / "backend" / "tests").glob("test_*.py")
        for value in re.findall(r'^SECRET = "([^"]+)"', path.read_text(encoding="utf-8"), re.M)
    ]
    assert len(secrets) >= 5 and all(allowed[0] in value for value in secrets), secrets


def test_gitleaksignore_enthaelt_nur_den_bekannten_fehlalarm():
    """Ein leeres JWT_SECRET= in .env.example: generic-api-key nimmt die naechste Zeile (JWT_TTL_HOURS=12) als Wert.
    Jede weitere Ausnahme muss hier bewusst dazukommen."""
    lines = (ROOT / ".gitleaksignore").read_text(encoding="utf-8").splitlines()
    ignored = [line for line in lines if line.strip() and not line.startswith("#")]
    assert ignored == ["b6535c5438b523d6b65e695b00bb325cd8c8f729:.env.example:generic-api-key:52"]


def test_keine_fremdlizenzierten_testdaten_im_repo():
    tracked = subprocess.run(
        ["git", "ls-files", "testdata"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    assert tracked.strip() == ""


def test_firmendokumente_unter_testdata_private_sind_ignoriert():
    """Issue #68: Ablage fuer echte Firmendokumente und ihre Gold-Vorlagen; nichts davon darf ins oeffentliche Repo."""
    for path in ("testdata/private/x.pdf", "testdata/private/x.gold.json"):
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0, path
