"""meta-Event: referenzierte Bauteile und Belege aus Antworttext und Fundstellen (ohne Modellaufruf)."""

from types import SimpleNamespace

from app.api.answer_meta import hotspot_evidence, page_evidence, tags_in_answer


def test_nur_bekannte_betriebsmittel_in_reihenfolge_und_einmal():
    text = "Prüfe zuerst -K1 (Schütz), dann -F2. -K1 zieht nicht, wenn -S3 offen ist; -K99 gibt es nicht. Klemme -X1:5 ist keine Zone."
    assert tags_in_answer(text, {"-K1", "-F2", "-S3", "-X1"}) == ["-K1", "-F2", "-S3"]
    assert tags_in_answer("keine Kennzeichen", {"-K1"}) == []


def test_seitenbelege_nur_pdf_seiten_begrenzt():
    refs = [
        {"document_id": "d1", "filename": "plan.pdf", "doc_type": "schematic", "page": 3},
        {"document_id": "d2", "filename": "liste.xlsx", "doc_type": "bom", "page": None},
        {"document_id": "d1", "filename": "plan.pdf", "doc_type": "schematic", "page": 5},
        {"document_id": "d3", "filename": "hb.pdf", "doc_type": "manual", "page": 12},
        {"document_id": "d3", "filename": "hb.pdf", "doc_type": "manual", "page": 13},
        {"document_id": "d3", "filename": "hb.pdf", "doc_type": "manual", "page": 14},
    ]
    evidence = page_evidence(refs)
    assert [e["page"] for e in evidence] == [3, 5, 12, 13]
    assert evidence[0] == {"kind": "page", "document_id": "d1", "filename": "plan.pdf", "doc_type": "schematic", "page": 3, "label": "plan.pdf S. 3"}


def test_hotspots_der_maschine_zu_den_bauteilen():
    hotspot = SimpleNamespace(id="h1", tag="-K1", label="Hauptschütz", x=0.1, y=0.2, w=0.05, h=0.08, confirmed=True)
    other = SimpleNamespace(id="h2", tag="-M1", label="", x=0, y=0, w=0.1, h=0.1, confirmed=False)
    cabinet = SimpleNamespace(id="c1", title="Schaltschrank", hotspots=[hotspot, other])
    machine = SimpleNamespace(cabinets=[cabinet])
    evidence = hotspot_evidence(machine, ["-k1"])
    assert evidence == [
        {
            "kind": "cabinet", "cabinet_id": "c1", "cabinet_title": "Schaltschrank", "hotspot_id": "h1", "tag": "-K1",
            "label": "Hauptschütz", "box": {"x": 0.1, "y": 0.2, "w": 0.05, "h": 0.08}, "confirmed": True,
        }
    ]
    assert hotspot_evidence(None, ["-K1"]) == [] and hotspot_evidence(machine, []) == []
