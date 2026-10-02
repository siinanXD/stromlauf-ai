"""Stoerfall-Felder und Verlauf in Stuecken (Spur B1), ohne Datenbank: message_page und ConversationPatch.
Die Rundlaeufe ueber die API stehen in test_stoerfall_db.py."""

import pytest
from pydantic import ValidationError

from app.api.chat import message_page
from app.schemas import ConversationOut, ConversationPatch, MessageOut


def _history(count: int) -> list[MessageOut]:
    return [
        MessageOut(role="user" if i % 2 == 0 else "assistant", content=f"m{i}")
        for i in range(count)
    ]


def _page(count: int, limit: int | None, before: int | None) -> list[tuple[int, str]]:
    return [(m.index, m.content) for m in message_page(_history(count), limit, before)]


def test_ohne_parameter_kommt_der_ganze_verlauf_mit_index():
    assert _page(4, None, None) == [(0, "m0"), (1, "m1"), (2, "m2"), (3, "m3")]
    assert _page(0, None, None) == []


def test_limit_ohne_before_liefert_die_letzten():
    assert _page(6, 2, None) == [(4, "m4"), (5, "m5")]
    assert _page(3, 30, None) == [(0, "m0"), (1, "m1"), (2, "m2")]


def test_before_ist_exklusiv_und_zeitlich_geordnet():
    assert _page(6, 2, 4) == [(2, "m2"), (3, "m3")]
    assert _page(6, None, 2) == [(0, "m0"), (1, "m1")]
    assert _page(6, 5, 1) == [(0, "m0")]
    assert _page(6, 2, 0) == []
    assert _page(6, 2, 99) == [(4, "m4"), (5, "m5")]  # hinter dem Ende: wie ohne before


def test_patch_prueft_outcome_und_laenge_des_befunds():
    assert ConversationPatch(outcome="resolved", finding="Luefter gereinigt").model_dump(
        exclude_unset=True
    ) == {"outcome": "resolved", "finding": "Luefter gereinigt"}
    assert ConversationPatch(outcome="open").model_dump(exclude_unset=True) == {"outcome": "open"}
    assert ConversationPatch(finding="x" * 2000).finding == "x" * 2000
    with pytest.raises(ValidationError):
        ConversationPatch(outcome="unresolved")  # ein Stoerfall ist offen oder erledigt, nichts dazwischen
    with pytest.raises(ValidationError):
        ConversationPatch(finding="x" * 2001)


def test_konversation_ohne_neue_felder_ist_offen_und_ohne_befund():
    out = ConversationOut(id="c1", title="t", source_ids=[], updated_at="2026-10-01T10:00:00Z")
    assert (out.outcome, out.finding) == ("open", "")
