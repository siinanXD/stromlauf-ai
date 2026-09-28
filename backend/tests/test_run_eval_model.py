"""eval/run_eval.py --model: der Agentenlauf kann je Lauf ein anderes Modell (Provider) anfordern."""

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "eval" / "run_eval.py"
sys.path.insert(0, str(SCRIPT.parent))
_spec = importlib.util.spec_from_file_location("run_eval", SCRIPT)
run_eval = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = run_eval
_spec.loader.exec_module(run_eval)


def test_chat_body_ohne_modell_laesst_das_backend_entscheiden():
    body = run_eval.chat_body("Frage?", ["s1"], ["eval:x"], None)
    assert body == {"message": "Frage?", "source_ids": ["s1"], "trace_tags": ["eval:x"]}


def test_chat_body_mit_modell_schickt_es_mit_und_taggt_den_lauf():
    body = run_eval.chat_body("Frage?", ["s1"], ["eval:x"], "openai:gpt-5-mini")
    assert body["model"] == "openai:gpt-5-mini"
    assert "model:openai:gpt-5-mini" in body["trace_tags"]
