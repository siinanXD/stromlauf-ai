"""Aufteilung der Index-Zeilen fuer das Modell (app/api/machine_map.py::split_rows), Issue #39; Blatt der Planseite
aus dem Schriftfeld (Issue #67)."""

import os
import shutil
from pathlib import Path

import pytest

from app.api.machine_map import pdf_sheets, split_rows

SCHRIFTFELD = Path(__file__).resolve().parents[2] / "examples" / "schriftfeld"
DB = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)
WS = "ws-machine-map-sheets-test"


def test_split_rows_trennt_stuecklistenzeilen_von_planfundstellen():
    rows = [
        ("-K1", "| -K1 | Schuetz | +ST1 |", "bom", None, "", "stueckliste.xlsx"),
        ("9K1", "9K1 A1 A2", "schematic", 9, "V1 Gate Control Circuit", "plan.pdf"),
        ("9K1", "6 ... 9K1 Contactor", "schematic", 41, "Nomenclature", "plan.pdf"),
        ("4Q1", "4Q1 80A", "schematic", 4, "Mains Power Supply", "plan.pdf"),
        ("-M1", "-M1 U1 V1 W1", "schematic", None, "", "plan.pdf"),
    ]
    sheets = {("plan.pdf", 4): 2, ("plan.pdf", 9): 7}
    bom_rows, index_hits, known = split_rows(rows, lambda path, page: sheets.get((path, page)))
    assert bom_rows == [("-K1", "| -K1 | Schuetz | +ST1 |"), ("9K1", "6 ... 9K1 Contactor")]
    assert index_hits == [
        ("4Q1", 4, "Mains Power Supply", 2),
        ("9K1", 9, "V1 Gate Control Circuit", 7),
        ("-M1", None, "", None),
    ]
    assert known == {"-K1", "9K1", "4Q1", "-M1"}


def test_blatt_einer_planseite_kommt_nur_aus_dem_gelesenen_schriftfeld():
    sheet_of = pdf_sheets()
    plan = str(SCHRIFTFELD / "blatt_von.pdf")
    assert [sheet_of(plan, page) for page in (1, 2, 3, 7)] == [None, None, 1, 5]
    assert (
        sheet_of(str(SCHRIFTFELD / "ohne_blattnummer.pdf"), 3) is None
    )  # Seite = Blatt nur angenommen
    assert sheet_of(str(SCHRIFTFELD / "fehlt.pdf"), 3) is None
    assert sheet_of("stueckliste.xlsx", 3) is None and sheet_of(plan, None) is None


def _in_workspace(action):
    from app.db import session_scope
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            return action(session)
    finally:
        reset_workspace(token)


def _wipe(session) -> None:
    from sqlalchemy import select

    from app.models import Hall, KnowledgeSource

    for model in (Hall, KnowledgeSource):
        for row in session.scalars(select(model)).all():
            session.delete(row)


@DB
def test_modell_benennt_zonen_nach_dem_blatt_hinter_dem_deckblatt(tmp_path):
    from app.api.machine_map import machine_map
    from app.db import session_scope
    from app.models import (
        Document,
        Hall,
        KnowledgeSource,
        Machine,
        TagOccurrence,
        TagType,
        Workspace,
    )

    upload = tmp_path / "blatt_von.pdf"
    shutil.copyfile(SCHRIFTFELD / "blatt_von.pdf", upload)
    with session_scope() as session:
        session.merge(Workspace(id=WS, name=WS))
    _in_workspace(_wipe)

    def create(session) -> str:
        source = KnowledgeSource(name="Blatt-Zonen-Test")
        hall = Hall(name="Halle Blatt-Zonen")
        session.add_all([source, hall])
        session.flush()
        machine = Machine(hall_id=hall.id, name="Muster-Band MB-02", source_id=source.id)
        document = Document(
            source_id=source.id,
            filename=upload.name,
            storage_path=str(upload),
            doc_type="schematic",
        )
        session.add_all([machine, document])
        session.flush()
        for tag, page, section in (
            ("-Q1", 3, "Einspeisung 400 V"),
            ("-K1", 5, "Motorsteuerung Band"),
        ):
            session.add(
                TagOccurrence(
                    document_id=document.id,
                    source_id=source.id,
                    tag=tag,
                    tag_type=TagType.DEVICE,
                    page=page,
                    section=section,
                    context=f"{tag} {section}",
                )
            )
        return machine.id

    try:
        machine_id = _in_workspace(create)
        result = _in_workspace(lambda session: machine_map(machine_id, session))
        assert [(zone["code"], zone["name"]) for zone in result["zones"]] == [
            ("Blatt 1", "Einspeisung 400 V"),
            ("Blatt 3", "Motorsteuerung Band"),
        ]
    finally:
        _in_workspace(_wipe)
