"""Modell-Fake fuer den Planleser: steht dort, wo make_chat_model ein LangChain-Chatmodell liefert.

Kein Netz, kein Schluessel. Kennt nur, was plan_model nutzt: with_structured_output(...).invoke(messages, config).
Meldet Tokens wie ein echter Anbieter ueber die Callbacks der Konfiguration (ledger.UsageCollector) und gibt die
Antwort im Format von include_raw=True zurueck.

Laengenlimit wie beim echten Anbieter: `length_pages` wirft den Fehler des OpenAI-SDK (openai.LengthFinishReasonError
mit der Antwort samt Tokens, ohne Callback), `cut_pages` liefert eine am Limit abgeschnittene Antwort ohne JSON.
"""

import json
import re

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from openai import LengthFinishReasonError
from openai.types.chat import ChatCompletion
from openai.types.completion_usage import CompletionUsage

MODEL_ID = "gpt-5-mini-2026-03-01"  # datierte ID wie vom Anbieter gemeldet
LIMIT_TOKENS = (3200, 8000)  # Seite am Limit: alle 8000 Ausgabe-Token fuers Nachdenken verbraucht


def length_error() -> LengthFinishReasonError:
    usage = CompletionUsage(
        prompt_tokens=LIMIT_TOKENS[0],
        completion_tokens=LIMIT_TOKENS[1],
        total_tokens=sum(LIMIT_TOKENS),
    )
    completion = ChatCompletion.model_construct(
        id="fake", model=MODEL_ID, choices=[], created=0, object="chat.completion", usage=usage
    )
    return LengthFinishReasonError(completion=completion)


class FakeModel:
    def __init__(
        self,
        answers=None,
        tokens=(3100, 450),
        fail_pages=(),
        parsed=True,
        report_usage=True,
        length_pages=(),
        cut_pages=(),
    ):
        self.length_pages = set(length_pages)
        self.cut_pages = set(cut_pages)
        self.answers = answers or {}  # Seite -> {"edges": [...]}
        self.tokens = tokens
        self.fail_pages = set(fail_pages)
        self.parsed = parsed  # False: strukturierte Ausgabe scheitert, JSON steht nur im Rohtext
        self.report_usage = report_usage
        self.calls: list[int] = []
        self.structured: tuple | None = None
        self.prompts: dict[int, str] = {}

    def with_structured_output(self, schema, **kwargs):
        self.structured = (schema, kwargs)
        return self

    def invoke(self, messages, config=None):
        text = messages[-1].content[-1]["text"]
        page = int(re.search(r"Seite (\d+)", text).group(1))
        self.calls.append(page)
        self.prompts[page] = text
        if page in self.fail_pages:
            raise RuntimeError("Anbieter nicht erreichbar")
        if page in self.length_pages:
            raise length_error()
        answer = self.answers.get(page, {"edges": []})
        usage = None
        if self.report_usage:
            usage = {
                "input_tokens": self.tokens[0],
                "output_tokens": self.tokens[1],
                "total_tokens": sum(self.tokens),
            }
        raw = AIMessage(
            content=f"Antwort: {json.dumps(answer)}",
            usage_metadata=usage,
            response_metadata={
                "model_name": MODEL_ID,
                "finish_reason": "length" if page in self.cut_pages else "stop",
            },
        )
        if page in self.cut_pages:
            raw.content = '{"edges": [{"from": "-K1", "to'
        for callback in (config or {}).get("callbacks", []):
            callback.on_llm_end(LLMResult(generations=[[ChatGeneration(message=raw)]]))
        if self.parsed and page not in self.cut_pages:
            return {"raw": raw, "parsed": answer, "parsing_error": None}
        return {"raw": raw, "parsed": None, "parsing_error": ValueError("kein Schema")}


def edge(source, target, pins=(None, None), directed=False, reason="Leitung gezeichnet"):
    return {
        "from": source,
        "to": target,
        "pins": {"from": pins[0], "to": pins[1]},
        "directed": directed,
        "reason": reason,
    }
