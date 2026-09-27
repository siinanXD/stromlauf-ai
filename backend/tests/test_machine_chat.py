"""Maschinen-Chat: Fehlerlisten-Suche werksweit, Systemprompt mit Maschinenkontext, Thread-Konfiguration."""

from app.agent.prompts import SYSTEM_PROMPT, system_prompt_for
from app.agent.tools import TOOLS, fault_matches, format_faults
from app.api.chat import _thread_config

ROWS = [
    {"machine": "Foerderband FB-01", "hall": "Halle 1", "code": "F03", "symptom": "Band steht, -H2 leuchtet",
     "cause": "Motorschutz -F2 ausgeloest", "fix": "-F2 pruefen, Motorstrom messen", "doc_ref": "Blatt /3.2", "tags": ["-F2", "-M1"]},
    {"machine": "L1-UR Umroller", "hall": "Verarbeitung", "code": "E12", "symptom": "Bahnriss",
     "cause": "Ultraschallsensor -B1 verschmutzt", "fix": "-B1 reinigen", "doc_ref": "", "tags": ["-B1"]},
]


def test_fault_matches_text_and_normalized_tags():
    assert fault_matches(ROWS[0], "band steht")
    assert fault_matches(ROWS[0], "motorschutz")
    assert fault_matches(ROWS[0], "f2")  # -F2 in tags, Schreibweise egal
    assert fault_matches(ROWS[0], "F03")
    assert not fault_matches(ROWS[0], "Bahnriss")
    assert fault_matches(ROWS[1], "")


def test_format_faults_is_plant_wide_and_marks_machine():
    text = format_faults(ROWS, "-B1")
    assert "werksweit" in text and "L1-UR Umroller (Verarbeitung)" in text and "Foerderband" not in text
    assert 'Kein Fehlereintrag passt zu "xyz"' in format_faults(ROWS, "xyz")


def test_search_faults_is_registered_tool():
    assert "search_faults" in [t.name for t in TOOLS]
    assert "search_faults" in SYSTEM_PROMPT


def test_system_prompt_adds_machine_context_only_with_machine():
    assert system_prompt_for(None) == SYSTEM_PROMPT
    assert system_prompt_for({"source_ids": ["s1"]}) == SYSTEM_PROMPT
    text = system_prompt_for({"machine": {"id": "m1", "name": "Foerderband FB-01", "hall": "Halle 1"}})
    assert text.startswith(SYSTEM_PROMPT)
    assert "Maschine Foerderband FB-01 in Halle 1" in text and "search_faults" in text


def test_thread_config_carries_machine():
    plain = _thread_config("c1", ["s1"])
    assert plain["configurable"] == {"thread_id": "c1", "source_ids": ["s1"]}
    scoped = _thread_config("c1", ["s1"], {"id": "m1", "name": "FB", "hall": ""})
    assert scoped["configurable"]["machine"]["name"] == "FB"
