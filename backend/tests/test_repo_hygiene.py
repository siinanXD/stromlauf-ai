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
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "gitleaks/gitleaks-action" in ci and "fetch-depth: 0" in ci


def test_keine_fremdlizenzierten_testdaten_im_repo():
    tracked = subprocess.run(
        ["git", "ls-files", "testdata"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    assert tracked.strip() == ""
