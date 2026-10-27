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
    assert PROMPT_VERSION == 5


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


def test_gelerntes_steht_als_kontext_nach_der_maschine():
    machine = {
        "id": "m1",
        "name": "FB-01",
        "hall": "H1",
        "wissen": ["Der Antrieb ist -M1.", "-F2 schützt -M1."],
    }
    text = system_prompt_for({"machine": machine})
    # Der feste Systemprompt erwähnt <kontext> selbst; geprüft wird nur der angehängte Teil.
    angehaengt = text[len(SYSTEM_PROMPT) :]
    assert angehaengt.index("Dieser Chat gehört zur Maschine") < angehaengt.index("<kontext>")
    assert "Bisher über diese Maschine gelernt" in text
    assert "- Der Antrieb ist -M1.\n- -F2 schützt -M1.\n</kontext>" in text
    leer = {"id": "m1", "name": "FB-01", "hall": "", "wissen": []}
    assert "<kontext>" not in system_prompt_for({"machine": leer})[len(SYSTEM_PROMPT) :]
