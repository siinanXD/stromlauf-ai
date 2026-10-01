"""Systemprompt v3: echte Umlaute, Antwortformat passend zu den Bloecken, Signalweg-Werkzeug, unsichere Herkunft."""

import re

from app.agent.prompts import PROMPT_VERSION, SYSTEM_PROMPT, system_prompt_for
from app.agent.tools import TOOLS

# Umschreibungen, die im Prompt v2 standen; v3 schreibt sie mit Umlaut bzw. ß
TRANSCRIBED = (
    "fuer",
    "ueber",
    "pruefen",
    "koennen",
    "moeglich",
    "ausschliesslich",
    "gehoert",
    "schaetzen",
    "hoechstens",
    "aenderungen",
    "zusammenhaengen",
    "stuecklisten",
    "klemmenplaene",
    "stromlaufplaene",
    "passwoerter",
)


def test_version_steigt_mit_dem_neuen_prompt():
    assert PROMPT_VERSION == 3


def test_prompt_schreibt_echte_umlaute():
    assert "Prüfen" in SYSTEM_PROMPT and "für" in SYSTEM_PROMPT
    words = set(re.findall(r"\w+", SYSTEM_PROMPT.lower()))
    assert not words & set(TRANSCRIBED)


def test_ueberschriften_bleiben_die_vier_bloecke():
    headings = re.findall(r"^## (\w+)", SYSTEM_PROMPT, re.M)
    assert headings == ["Kurzantwort", "Prüfen", "Details", "Sicherheit"]


def test_jedes_werkzeug_steht_im_prompt():
    for name in [t.name for t in TOOLS]:
        assert name in SYSTEM_PROMPT, name


def test_signalweg_kommt_aus_dem_werkzeug_und_unsicheres_wird_benannt():
    assert "signal_path" in SYSTEM_PROMPT
    assert "unsicher" in SYSTEM_PROMPT and "Lage im Plan" in SYSTEM_PROMPT


def test_details_wiederholen_nicht_was_die_oberflaeche_zeigt():
    assert "nicht als Tabelle" in SYSTEM_PROMPT or "keine Tabelle" in SYSTEM_PROMPT


def test_maschinenkontext_steht_am_ende_damit_der_anfang_cachebar_bleibt():
    text = system_prompt_for({"machine": {"id": "m1", "name": "FB-01", "hall": "Halle 1"}})
    assert text.startswith(SYSTEM_PROMPT) and text.rstrip().endswith("Kennzeichen.")
