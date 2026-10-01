"""Lehrerlauf des Planlesers (eval/plan_teacher.py, Spur D): nur oeffentliche Beispielplaene ans Modell, ohne --yes
nur die Schaetzung, mit --yes der Vergleich Wahrheit / Regeln / Modell, --from-result ohne Modell. Das Modell ist ein
Fake an der Stelle von make_chat_model; Gold im Format von Spur A (oberster Schluessel `wires`)."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from plan_model_fake import LIMIT_TOKENS, FakeModel, edge

from app.ingestion import plan_model
from app.ingestion.plan_edges import PlanEdge

ROOT = Path(__file__).resolve().parents[2]
FB01 = ROOT / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"


def _load():
    spec = importlib.util.spec_from_file_location("plan_teacher", ROOT / "eval" / "plan_teacher.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plan_teacher = _load()


class _Forbidden:
    """Zaehlt jeden Versuch, ein Modell zu bauen oder Kennzeichen zu lesen; beides darf nicht passieren."""

    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("darf nicht aufgerufen werden")


@pytest.fixture
def forbidden(monkeypatch):
    guard = _Forbidden()
    monkeypatch.setattr(plan_model, "make_chat_model", guard)
    return guard


PUBLIC_ONLY = "Nur oeffentliche Beispielplaene (examples/, testdata/qelectrotech/) duerfen an ein bezahltes Modell."


@pytest.mark.parametrize(
    "path",
    [
        "testdata/private/kunde.pdf",
        "testdata/irgendwas.pdf",
        "C:/kunde/examples/plan.pdf",  # examples/ ausserhalb des Repos
        "examples/../testdata/private/kunde.pdf",
        "examples/foerderband/02_Stueckliste_FB-01.xlsx",  # kein PDF
    ],
)
def test_nur_oeffentliche_beispielplaene_gehen_an_ein_modell(path, forbidden, capsys):
    exit_code = plan_teacher.main(
        ["--model", "openai:gpt-5-mini", "--doc", path, "--yes"],
        tags_fn=forbidden,
        rules_fn=forbidden,
    )
    assert exit_code == 2 and forbidden.calls == 0
    err = capsys.readouterr().err
    assert err.startswith(f"{PUBLIC_ONLY} Abgelehnt: ")
    assert Path(path).name in err


def test_erlaubnisliste_kennt_examples_und_qelectrotech_des_repos(monkeypatch, tmp_path):
    assert plan_teacher.is_public(FB01)
    assert plan_teacher.is_public(ROOT / "testdata" / "qelectrotech" / "plan.pdf")
    assert not plan_teacher.is_public(ROOT / "testdata" / "kunde.pdf")
    assert not plan_teacher.is_public(tmp_path / "examples" / "plan.pdf")
    # in einer Arbeitskopie unter .claude/worktrees/ liegt testdata/ nur im Haupt-Checkout
    main = tmp_path / "repo"
    monkeypatch.setattr(plan_teacher, "ROOT", main / ".claude" / "worktrees" / "spur")
    assert plan_teacher.repo_roots() == [main / ".claude" / "worktrees" / "spur", main]
    assert plan_teacher.is_public(main / "testdata" / "qelectrotech" / "plan.pdf")
    assert not plan_teacher.is_public(main / "testdata" / "private" / "kunde.pdf")


@pytest.mark.parametrize(
    ("base_url", "exit_code"),
    [
        ("http://localhost:11434/v1", 0),
        ("http://127.0.0.1:11434/v1", 0),
        ("http://[::1]:11434/v1", 0),
        ("https://modelle.example.com/v1", 2),
        ("http://localhost.example.com/v1", 2),
    ],
)
def test_nur_ein_lokaler_endpunkt_hebt_die_erlaubnisliste_auf(
    base_url, exit_code, forbidden, tmp_path, capsys
):
    plan = tmp_path / "kunde.pdf"
    shutil.copyfile(FB01, plan)  # nicht oeffentlich: liegt ausserhalb von examples/
    argv = ["--model", "openai:qwen3.5:4b", "--base-url", base_url, "--doc", str(plan)]
    assert plan_teacher.main(argv, tags_fn=forbidden, rules_fn=forbidden) == exit_code
    assert forbidden.calls == 0  # ohne --yes nur die Schaetzung


def test_gold_unter_testdata_private_wird_nicht_geoeffnet(forbidden, capsys):
    gold = "testdata/private/kunde.gold.json"  # gibt es nicht: Oeffnen wuerde scheitern
    exit_code = plan_teacher.main(
        ["--model", "openai:gpt-5-mini", "--gold", gold, "--yes"], tags_fn=forbidden
    )
    assert exit_code == 2 and forbidden.calls == 0
    assert "Gold unter testdata/private/ wird nicht gelesen" in capsys.readouterr().err


def test_plan_aus_dem_gold_muss_oeffentlich_sein(forbidden, tmp_path, capsys):
    gold = tmp_path / "plan.gold.json"
    gold.write_text(
        json.dumps({"dokument": "testdata/private/kunde.pdf", "seiten": {}}), encoding="utf-8"
    )
    exit_code = plan_teacher.main(
        ["--model", "openai:gpt-5-mini", "--gold", str(gold), "--yes"], tags_fn=forbidden
    )
    assert exit_code == 2 and forbidden.calls == 0
    assert capsys.readouterr().err.startswith(f"{PUBLIC_ONLY} Abgelehnt: kunde.pdf")


def test_ohne_yes_nur_seiten_modell_und_ehrliche_schaetzung(forbidden, tmp_path, capsys):
    exit_code = plan_teacher.main(
        ["--model", "openai:gpt-5-mini", "--doc", str(FB01), "--out", str(tmp_path)],
        tags_fn=forbidden,
        rules_fn=forbidden,
    )
    out = capsys.readouterr().out
    assert exit_code == 0 and forbidden.calls == 0
    assert "Anbieter: openai, Modell: openai:gpt-5-mini" in out
    assert "01_Stromlaufplan_FB-01.pdf: 7 Seiten" in out
    # Reasoning-Modell: 3000 rein, 4000 raus je Seite -> 7 x 0,00875 USD (gemessen waren 0,0523 USD)
    assert "Seiten: 7, geschaetzt bis zu 0.06125 USD" in out
    assert "3000 Token rein, 4000 raus je Seite, Reasoning-Modell mit Effort low" in out
    assert "Kein Modellaufruf" in out
    assert list(tmp_path.iterdir()) == []


def test_collapse_legt_anschluesse_ins_geraet_wie_das_gold():
    assert plan_teacher.collapse("-K1:A1") == "-K1" and plan_teacher.collapse("-S1:13") == "-S1"
    assert plan_teacher.collapse("-X3:1") == "-X3:1" and plan_teacher.collapse("E0.0") == "E0.0"
    assert plan_teacher.pair("-X4:U", "-K1:A1") == ("-K1", "-X4:U")
    assert plan_teacher.pair("-K3:13", "-K3:14") is None  # innerhalb eines Geraets
    gold = {"wires": {"3": [["-K1:A1", "-X4:U"], ["-X4:U", "-K1"]], "5": [["-X3:1", "E0.0"]]}}
    assert plan_teacher.gold_wires(gold) == {3: {("-K1", "-X4:U")}, 5: {("-X3:1", "E0.0")}}
    assert plan_teacher.gold_wires({"seiten": {}}) is None


def _gold(tmp_path, document="egal.pdf"):
    """Gold wie von Spur A: `wires` je Seite, Anschluesse teils noch mit Nummer."""
    gold = tmp_path / "gold.json"
    data = {
        "dokument": document,
        "doc_type": "schematic",
        "seiten": {"3": {"device": ["-K1"]}},
        "wires": {"3": [["-K1:A1", "-X4:U"], ["-K1", "-X4:V"]], "4": [["-S1:13", "-X3:1"]]},
    }
    gold.write_text(json.dumps(data), encoding="utf-8")
    return gold


def _rules(path):
    # Seite 3: -K1 - -X4:V richtig; Seite 4: -S1 - -X3:1 richtig, -S1 - -X3:2 falsch
    return [
        PlanEdge("-X4:V", "-K1:A2", 3, "leitung", False),
        PlanEdge("-S1:13", "-X3:1", 4, "leitung", True),
        PlanEdge("-S1", "-X3:2", 4, "lage", False),
    ]


def test_mit_yes_vergleicht_wahrheit_regeln_und_modell(monkeypatch, tmp_path, capsys):
    doc = FB01
    gold = _gold(tmp_path)
    fake = FakeModel(
        {
            3: {
                "edges": [
                    edge("-K1", "-X4:U", reason="Leitung zur Klemme U"),
                    edge("-X4:V", "-X4:U"),
                    edge("-K1", "-Q9"),
                ]
            }
        },
        length_pages={4},
    )
    built = {}
    monkeypatch.setattr(
        plan_model, "make_chat_model", lambda name, **kwargs: built.update(kwargs) or fake
    )
    tags = {3: {"-K1", "-X4:U", "-X4:V"}, 4: {"-S1", "-X3:1"}}
    argv = ["--model", "openai:gpt-5-mini", "--doc", str(doc), "--gold", str(gold), "--yes"]
    exit_code = plan_teacher.main(
        [*argv, "--out", str(tmp_path)], tags_fn=lambda path, doc_type: tags, rules_fn=_rules
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert built["reasoning_effort"] == "low"
    (result_file,) = tmp_path.glob("plan_teacher_*.json")
    result = json.loads(result_file.read_text(encoding="utf-8"))
    summary, rows = result["summary"], result["results"]
    assert sorted(fake.calls) == [3, 4]
    assert summary["gruppen"] == {
        "Modell richtig, Regeln fehlen": 1,  # -K1 - -X4:U (Gold: -K1:A1 - -X4:U)
        "Regeln falsch": 1,  # -S1 - -X3:2
        "Modell falsch": 1,  # -X4:U - -X4:V
    }
    assert summary["verworfen"] == 1 and summary["kanten"] == 2
    (document,) = summary["je_dokument"]
    assert document["modell_gegen_wahrheit"] == {
        "tp": 1,
        "fp": 1,
        "fn": 2,
        "precision": 0.5,
        "recall": 0.3333,
    }
    assert document["regeln_gegen_wahrheit"]["precision"] == 0.6667
    assert document["regeln_gegen_wahrheit"]["recall"] == 0.6667
    # Seite 4 am Laengenlimit: gescheitert mit Grund, Lauf geht weiter, ihre Tokens kosten mit
    fb01 = "examples/foerderband/01_Stromlaufplan_FB-01.pdf"
    assert summary["seiten_fehler"] == [[fb01, 4, "Laengenlimit"]]
    assert summary["seiten_laengenlimit"] == 1
    tokens_in, tokens_out = 3100 + LIMIT_TOKENS[0], 450 + LIMIT_TOKENS[1]
    assert summary["tokens"] == {"rein": tokens_in, "raus": tokens_out}
    assert summary["kosten_usd"] == pytest.approx((tokens_in * 0.25 + tokens_out * 2.0) / 1e6)
    assert summary["format"] == 2 and summary["ausgabe_token_je_seite"] == 4000
    assert summary["reasoning_effort"] == "low"
    assert summary["seiten"] == 7 and summary["seiten_gelesen"] == 2
    page3 = next(row for row in rows if row["seite"] == 3)
    assert page3["vergleich"]["modell_richtig_regeln_fehlen"] == [["-K1", "-X4:U"]]
    assert page3["vergleich"]["modell_falsch"] == [["-X4:U", "-X4:V"]]
    assert {
        "source": "-K1",
        "target": "-X4:U",
        "directed": False,
        "reason": "Leitung zur Klemme U",
    } in page3["kanten"]
    assert page3["verworfen"][0]["target"] == "-Q9"
    assert "Laengenlimit" in out and "Modell P 0.5 R 0.3333" in out


def _saved_result(tmp_path, doc, gold, error):
    """Ergebnis wie aus dem ersten bezahlten Lauf (Format 1): Fehlertext roh, ohne `format`."""
    rows = [
        {
            "dokument": doc.as_posix(),
            "seite": 3,
            "kennzeichen": 3,
            "kanten": [
                {"source": "-K1", "target": "-X4:U", "directed": False, "reason": "Linie"},
                {"source": "-X4:V", "target": "-X4:U", "directed": False, "reason": "Linie"},
            ],
            "verworfen": [],
            "fehler": None,
            "tokens": [3100, 450],
            "vergleich": {},
        },
        {
            "dokument": doc.as_posix(),
            "seite": 4,
            "kennzeichen": 2,
            "kanten": [],
            "verworfen": [],
            "fehler": error,
            "tokens": None,
            "vergleich": {},
        },
    ]
    summary = {
        "modell": "openai:gpt-5-mini",
        "lokal": False,
        "prompt_version": "1",
        "dokumente": [doc.as_posix()],
        "gold": [gold.as_posix()],
        "seiten": 7,
        "schaetzung_usd": 0.03325,
        "kosten_usd": 0.0523,
        "tokens": {"rein": 21000, "raus": 22800},
    }
    path = tmp_path / "plan_teacher_2026-10-01_12-00-00.json"
    path.write_text(json.dumps({"summary": summary, "results": rows}), encoding="utf-8")
    return path


def test_from_result_rechnet_ohne_modell_neu(forbidden, tmp_path, capsys):
    doc = tmp_path / "plan.pdf"
    shutil.copyfile(FB01, doc)
    gold = _gold(tmp_path)
    error = (
        "LengthFinishReasonError: Could not parse response content as the length limit was "
        "reached - CompletionUsage(completion_tokens=8000, prompt_tokens=3200)"
    )
    saved = _saved_result(tmp_path, doc, gold, error)
    out_dir = tmp_path / "neu"
    out_dir.mkdir()
    exit_code = plan_teacher.main(
        ["--from-result", str(saved), "--out", str(out_dir)], tags_fn=forbidden, rules_fn=_rules
    )
    out = capsys.readouterr().out
    assert exit_code == 0 and forbidden.calls == 0
    assert "ohne Modellaufruf" in out
    (result_file,) = out_dir.glob("plan_teacher_*.json")
    result = json.loads(result_file.read_text(encoding="utf-8"))
    summary, rows = result["summary"], result["results"]
    assert summary["gruppen"] == {
        "Modell richtig, Regeln fehlen": 1,
        "Regeln falsch": 1,
        "Modell falsch": 1,
    }
    assert summary["seiten_fehler"] == [[doc.as_posix(), 4, "Laengenlimit"]]
    assert summary["kosten_usd"] == 0.0523 and summary["modell"] == "openai:gpt-5-mini"
    assert summary["neu_gerechnet_aus"].endswith("plan_teacher_2026-10-01_12-00-00.json")
    (document,) = summary["je_dokument"]
    assert (document["modell_gegen_wahrheit"]["precision"], document["kanten"]) == (0.5, 2)
    assert rows[1]["fehler"] == "Laengenlimit"
    assert rows[0]["vergleich"]["modell_falsch"] == [["-X4:U", "-X4:V"]]
    # das Original bleibt unveraendert
    assert json.loads(saved.read_text(encoding="utf-8"))["results"][1]["fehler"] == error


def test_from_result_nimmt_ein_anderes_gold_und_prueft_die_anzahl(forbidden, tmp_path, capsys):
    doc = tmp_path / "plan.pdf"
    shutil.copyfile(FB01, doc)
    saved = _saved_result(tmp_path, doc, tmp_path / "weg.json", None)
    gold = _gold(tmp_path)
    exit_code = plan_teacher.main(
        ["--from-result", str(saved), "--gold", str(gold), "--out", str(tmp_path)],
        rules_fn=lambda path: None,
    )
    assert exit_code == 0
    assert "Leitungsleser in diesem Stand nicht vorhanden" in capsys.readouterr().out
    two = ["--from-result", str(saved), "--gold", str(gold), "--gold", str(gold)]
    assert plan_teacher.main(two) == 1
    assert "eine je Dokument" in capsys.readouterr().err
    assert forbidden.calls == 0


def test_from_result_ohne_kanten_je_seite_ist_nicht_auswertbar(forbidden, tmp_path, capsys):
    saved = tmp_path / "plan_teacher_alt.json"
    saved.write_text(json.dumps({"summary": {}, "results": [{"seite": 3}]}), encoding="utf-8")
    assert plan_teacher.main(["--from-result", str(saved)]) == 1
    assert "nicht auswertbar" in capsys.readouterr().err


def test_ohne_wires_im_gold_und_ohne_leitungsleser_bleiben_die_gruppen_leer(
    monkeypatch, tmp_path, capsys
):
    gold = tmp_path / "gold.json"
    gold.write_text(
        json.dumps({"dokument": str(FB01), "seiten": {"3": {"device": ["-K1"]}}}), encoding="utf-8"
    )
    monkeypatch.setattr(
        plan_model,
        "make_chat_model",
        lambda name, **kwargs: FakeModel({3: {"edges": [edge("-K1", "-X4:U")]}}),
    )
    argv = ["--model", "openai:gpt-5-mini", "--doc", str(FB01), "--gold", str(gold), "--yes"]
    exit_code = plan_teacher.main(
        [*argv, "--out", str(tmp_path)],
        tags_fn=lambda path, doc_type: {3: {"-K1", "-X4:U"}},
        rules_fn=lambda path: None,
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Gold ohne `wires`" in out and "Leitungsleser in diesem Stand nicht vorhanden" in out
    (result_file,) = tmp_path.glob("plan_teacher_*.json")
    summary = json.loads(result_file.read_text(encoding="utf-8"))["summary"]
    assert set(summary["gruppen"].values()) == {None}
    assert summary["kanten"] == 1 and summary["modell_gegen_wahrheit"] is None


def test_doc_und_gold_muessen_paarweise_kommen(forbidden):
    with pytest.raises(SystemExit):
        plan_teacher.main(
            ["--model", "x", "--doc", str(FB01), "--doc", str(FB01), "--gold", "g.json"]
        )
    with pytest.raises(SystemExit):
        plan_teacher.main(["--doc", "a.pdf"])  # ohne --model und ohne --from-result
    assert forbidden.calls == 0
