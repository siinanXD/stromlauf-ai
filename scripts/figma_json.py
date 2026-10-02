"""JSON fuer die Figma-Vorlagen aus echten Stromlauf-AI-Daten (Plugin "Stromlauf Vorlagen fuellen").

Aufruf:
  python scripts/figma_json.py --vorlage stoerfall-antwort --maschine "Foerderband FB-01"
      --conversation <chat-id> --out antwort.json
  python scripts/figma_json.py --offline examples/foerderband --vorlage signalweg
      --maschine "Foerderband FB-01" --tag -F2 --out signalweg.json

Vorlagen (Schemas unter design/figma/schemas/). Neu sind nur die Felder der obersten Ebene, alles darunter hat
die Form der API-Typen aus frontend/src/lib/api.ts:
  stoerfall-antwort  {vorlage, version, maschine, frage, zeit, fault_hits, antwort, meta, signal}
                     --meldung (Fehlerlisten-Treffer), --antwort TEXT oder --conversation ID, optional --tag
  signalweg          {vorlage, version, maschine, signal}                      --tag
  stoerfaelle        {vorlage, version, maschine, ort, conversations}

Kein Weg ruft ein Modell auf: der Antworttext kommt aus --antwort oder aus der letzten gespeicherten Antwort
eines Chats (--conversation). --zeit (ISO-Zeitpunkt, Standard jetzt bzw. der letzte Stand des Chats) liefert
"zeit" (HH:MM, lokal) und im Offline-Weg updated_at des Stoerfalls.

API-Weg (Standard): nur die oeffentliche HTTP-API eines laufenden Backends. --api, sonst STROMLAUF_API_URL, sonst
http://localhost:8010; den Schluessel liest das Skript aus STROMLAUF_API_KEY und schickt ihn als X-API-Key.
  - Maschine (Name oder ID), Ort: GET /api/machines
  - fault_hits: GET /api/machines/{id}/fault-hits?q=<Meldung>
  - signal: GET /api/signal-path?tag=&source_id=&view=main; 404 ergibt null
  - --conversation: letzte Antwort samt meta aus GET /api/conversations/{id}/messages, frage = Frage davor
  - --antwort: meta per POST /api/answers/validate-citations (referenced_tags, citations_valid), GET
    /api/machines/{id}/map (part_kinds) und GET /api/machines/{id}/tags/{tag} (plan_spots). Blatt und Spalte
    liest das Backend nur fuer gespeicherte Antworten; hier bleiben sheet und column null.
  - conversations: GET /api/conversations?machine_id=

Offline-Weg (--offline <Beispielordner>): dasselbe JSON ohne Backend, Datenbank und Modell, ueber die
Backend-Funktionen direkt (wie eval/run_ingest.py):
  - Kennzeichen-Index je Datei des Ordners: pipeline.document_pieces -> split_pieces -> tag_rows (Docling wie
    beim Upload, die erste PDF dauert etwa 15 s)
  - signal: app.api.signal._graph (Klemmenplan, Stueckliste, Symboltabelle, AWL und die Leitungen aus dem Plan:
    plan_wires.plan_edges, signal_graph.add_plan_edges), dann signal_view.main_view
  - fault_hits: Fehlerliste aus scripts/load_example.py (FB-01) mit der Trefferlogik von app.werk.faults
    (fault_matches/FaultQuery) und best_hits wie der Endpunkt. experience und incidents kennt nur die
    Datenbank, sie bleiben leer.
  - meta: answer_meta.tags_in_answer, part_kinds, first_plan_rows und plan_spot (Blatt aus dem Schriftfeld,
    Spalte aus tag_columns, Blatttitel aus page_titles), citations.check_citations
  - conversations: nur der Stoerfall, den --meldung anlegt (Titel wie POST /api/chat), offen
  Ohne Datenbank gibt es keine IDs: Maschine, Quelle, Dokumente, Fehler und Stoerfall heissen "offline-<hash>".
  Halle und Fehlerliste kennt der Offline-Weg nur fuer die Maschine aus scripts/load_example.py.

Am Ende prueft das Skript das JSON gegen das Schema: mit jsonschema, wenn es installiert ist, sonst mit einer
eingebauten Pruefung (Pflichtfelder, Typen, Werte). Exit 1 bei Verstoss; dann wird nichts geschrieben.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "design" / "figma" / "schemas"
# app aus diesem Checkout laden, nicht aus dem, in dem zuletzt `pip install -e` lief
sys.path.insert(0, str(ROOT / "backend"))

VERSION = 1
VORLAGEN = ("stoerfall-antwort", "signalweg", "stoerfaelle")
NO_CITATIONS = {"valid": 0, "checked": 0, "total": 0}
TITLE_MAX = 80  # Stoerfall-Titel wie POST /api/chat
# Dateien, die der Offline-Weg wie einen Upload liest; Bilder (OCR) und JSON laedt load_example.py nicht hoch
OFFLINE_SUFFIXES = set(".pdf .xlsx .xlsm .csv .txt .awl .scl .sdf .md .docx".split())


def offline_id(*parts: str) -> str:
    """Feste Ersatz-ID ohne Datenbank, je Inhalt gleich."""
    return "offline-" + hashlib.sha256("/".join(parts).encode("utf-8")).hexdigest()[:12]


def parse_time(text: str | None) -> datetime:
    """ISO-Zeitpunkt; ohne Zeitzone gilt die lokale, ohne Angabe jetzt."""
    if not text:
        return datetime.now().astimezone()
    moment = datetime.fromisoformat(text)
    return moment if moment.tzinfo else moment.astimezone()


def clock(moment: datetime) -> str:
    return moment.astimezone().strftime("%H:%M")


def iso_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def incident_title(message: str) -> str:
    title = " ".join(message.split())
    return title[:TITLE_MAX] + ("…" if len(title) > TITLE_MAX else "")


def place(machine: dict) -> str:
    """Halle und Linie, z. B. "Verarbeitung · PM1"."""
    return " · ".join(part for part in (machine.get("hall_name"), machine.get("line")) if part)


def template_meta(meta: dict | None) -> dict:
    """Die vier Felder von AnswerMeta, die die Vorlage zeigt; fehlende (alte Antworten) leer."""
    meta = meta or {}
    return {
        "referenced_tags": list(meta.get("referenced_tags") or []),
        "part_kinds": dict(meta.get("part_kinds") or {}),
        "plan_spots": list(meta.get("plan_spots") or []),
        "citations_valid": meta.get("citations_valid") or dict(NO_CITATIONS),
    }


def pick_machine(machines: list[dict], wanted: str) -> dict:
    """Maschine nach ID, Namen oder Namen ohne Gross/Klein; genau eine, sonst Abbruch."""
    for match in (
        lambda m: m["id"] == wanted,
        lambda m: m["name"] == wanted,
        lambda m: m["name"].casefold() == wanted.casefold(),
    ):
        found = [m for m in machines if match(m)]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise SystemExit(f"Maschine '{wanted}' ist mehrdeutig, bitte die ID angeben")
    raise SystemExit(f"Maschine '{wanted}' nicht gefunden")


# --- API-Weg ------------------------------------------------------------------------------------


class ApiSource:
    """Daten ueber die oeffentliche HTTP-API eines laufenden Backends."""

    def __init__(self, base_url: str) -> None:
        import httpx

        key = os.environ.get("STROMLAUF_API_KEY", "").strip()
        self._errors = httpx.HTTPError
        self.client = httpx.Client(
            base_url=base_url, headers={"X-API-Key": key} if key else {}, timeout=120
        )

    def _send(self, method: str, path: str, **kwargs):
        try:
            return self.client.request(method, path, **kwargs)
        except self._errors as exc:
            raise SystemExit(
                f"Backend unter {self.client.base_url} nicht erreichbar ({exc.__class__.__name__})"
            ) from exc

    @staticmethod
    def _json(response, label: str):
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = response.text[:200]
            raise SystemExit(f"{label}: HTTP {response.status_code} {detail}")
        return response.json()

    def get(self, path: str, **params):
        return self._json(self._send("GET", path, params=params or None), f"GET {path}")

    def post(self, path: str, body: dict):
        return self._json(self._send("POST", path, json=body), f"POST {path}")

    def machine(self, wanted: str) -> dict:
        return pick_machine(self.get("/api/machines"), wanted)

    def fault_hits(self, machine: dict, meldung: str) -> dict:
        return self.get(f"/api/machines/{machine['id']}/fault-hits", q=meldung)

    def signal(self, machine: dict, tag: str) -> dict | None:
        if not machine.get("source_id"):
            return None
        params = {"tag": tag, "source_id": machine["source_id"], "view": "main"}
        response = self._send("GET", "/api/signal-path", params=params)
        if response.status_code == 404:
            return None
        return self._json(response, "GET /api/signal-path")

    def conversations(self, machine: dict, meldung: str | None, moment: datetime) -> list[dict]:
        if not machine.get("source_id"):
            return []  # ohne Wissensquelle kein Chat und damit kein Stoerfall
        return self.get("/api/conversations", machine_id=machine["id"])

    def saved_answer(self, machine: dict, conversation_id: str) -> dict:
        messages = self.get(
            f"/api/conversations/{conversation_id}/messages", machine_id=machine["id"]
        )
        last = max((i for i, m in enumerate(messages) if m["role"] == "assistant"), default=None)
        if last is None:
            raise SystemExit(f"Chat {conversation_id} hat noch keine Antwort")
        users = [m["content"] for m in messages[:last] if m["role"] == "user"]
        updated = next(
            (
                c["updated_at"]
                for c in self.conversations(machine, None, datetime.now())
                if c["id"] == conversation_id
            ),
            None,
        )
        return {
            "frage": users[-1] if users else "",
            "meldung": users[0] if users else "",
            "antwort": messages[last]["content"],
            "meta": messages[last].get("meta") or {},
            "updated_at": updated,
        }

    def answer_meta(self, machine: dict, answer: str) -> dict:
        """meta fuer einen freien Antworttext aus den Endpunkten, die es dafuer gibt (ohne Modell)."""
        from app.api.answer_meta import PlanRow, first_plan_rows

        source_ids = [machine["source_id"]] if machine.get("source_id") else []
        checked = self.post(
            "/api/answers/validate-citations", {"answer": answer, "source_ids": source_ids}
        )
        tags = checked["referenced_tags"]
        kinds: dict[str, str] = {}
        rows: list = []
        if tags:
            model = self.get(f"/api/machines/{machine['id']}/map")
            kinds = {
                part["tag"]: part.get("kind", "")
                for zone in model.get("zones", [])
                for part in zone.get("parts", [])
            }
            for tag in tags:
                lookup = self.get(f"/api/machines/{machine['id']}/tags/{quote(tag, safe='')}")
                for hit in lookup["hits"]:
                    if hit.get("doc_type") != "schematic" or not hit.get("page"):
                        continue
                    # storage_path kennt die API nicht; first_plan_rows braucht davon nur die Endung
                    name = hit["filename"]
                    section = hit.get("section") or ""
                    rows.append(PlanRow(tag, hit["page"], section, hit["document_id"], name, name))
        spots = [
            {
                "tag": row.tag,
                "document_id": row.document_id,
                "filename": row.filename,
                "page": row.page,
                "sheet": None,
                "title": row.section,
                "column": None,
            }
            for row in first_plan_rows(tags, rows)
        ]
        return {
            "referenced_tags": tags,
            "part_kinds": {tag: kinds.get(tag, "") for tag in tags},
            "plan_spots": spots,
            "citations_valid": checked["citations_valid"],
        }


# --- Offline-Weg --------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_example():
    """scripts/load_example.py: Maschine, Halle und Fehlerliste der Beispielanlage FB-01."""
    spec = importlib.util.spec_from_file_location(
        "load_example", ROOT / "scripts" / "load_example.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class IndexedDoc:
    """Ein Dokument des Beispielordners, gelesen wie beim Upload."""

    path: Path
    doc_type: str
    pieces: list
    rows: list
    page_count: int | None

    @property
    def id(self) -> str:
        return offline_id("document", self.path.name)


class OfflineSource:
    """Dieselben Daten ohne Backend: Dateien des Beispielordners, Fehlerliste aus scripts/load_example.py."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.source_id = offline_id("source", folder.name)
        self._files: list[tuple[Path, str]] | None = None
        self._index: list[IndexedDoc] | None = None
        self._graph = None

    def files(self) -> list[tuple[Path, str]]:
        """(Pfad, Dokumenttyp) je Datei, Typ wie beim Upload mit "auto" erkannt."""
        if self._files is None:
            from app.ingestion.pipeline import detect_doc_type

            self._files = [
                (path, str(detect_doc_type(path.name, "auto", path)))
                for path in sorted(self.folder.iterdir())
                if path.is_file()
                and path.suffix.lower() in OFFLINE_SUFFIXES
                and not path.name.lower().startswith("readme")
            ]
        return self._files

    def index(self) -> list[IndexedDoc]:
        """Kennzeichen-Index wie nach dem Upload: dieselben Funktionen wie ingest_document."""
        if self._index is None:
            from app.ingestion.pipeline import document_pieces, split_pieces, tag_rows

            self._index = []
            for path, doc_type in self.files():
                print(f"lese {path.name} ({doc_type})", file=sys.stderr)
                read = document_pieces(path, doc_type)
                pieces = split_pieces(read.pieces)
                self._index.append(
                    IndexedDoc(path, doc_type, pieces, tag_rows(pieces), read.page_count)
                )
        return self._index

    def machine(self, wanted: str) -> dict:
        example = load_example()
        machine = {
            "id": offline_id("machine", wanted),
            "name": wanted,
            "hall_name": "",
            "line": "",
            "source_id": self.source_id,
            "faults": [],
        }
        if wanted.casefold() != example.MACHINE_NAME.casefold():
            print(
                f"offline: keine Halle und Fehlerliste fuer '{wanted}' "
                f"(bekannt: {example.MACHINE_NAME} aus scripts/load_example.py)",
                file=sys.stderr,
            )
            return machine
        return {
            **machine,
            "id": offline_id("machine", example.MACHINE_NAME),
            "name": example.MACHINE_NAME,
            "hall_name": example.HALL_NAME,
            "faults": example.FAULTS,
        }

    def fault_hits(self, machine: dict, meldung: str) -> dict:
        from app.api.plant import MAX_FAULT_QUERY, best_hits
        from app.werk.faults import FaultQuery

        query = FaultQuery(meldung[:MAX_FAULT_QUERY])
        hits = {"faults": [], "experience": [], "incidents": []}
        if query.empty:
            return hits
        scored = []
        # Reihenfolge vor dem Sortieren wie die Abfrage des Endpunkts: nach Code
        for fault in sorted(machine["faults"], key=lambda f: f["code"]):
            score = query.score(fault)
            if score:
                out = {key: fault[key] for key in ("code", "symptom", "cause", "fix", "doc_ref")}
                out |= {
                    "tags": list(fault["tags"]),
                    "id": offline_id("fault", machine["name"], fault["code"]),
                    "machine_id": machine["id"],
                }
                scored.append((score, out))
        return {**hits, "faults": best_hits(scored)}

    def graph(self):
        """Signalweg-Graph wie app.api.signal.graph_for_source, nur ohne Datenbank."""
        if self._graph is None:
            from app.api.signal import _graph, _graph_input, _is_plan, _model_stamp

            files = tuple(
                sorted(
                    (doc_type, str(path), path.stat().st_mtime)
                    for path, doc_type in self.files()
                    if _graph_input(doc_type, str(path))
                )
            )
            plans = any(_is_plan(doc_type, path) for doc_type, path, _ in files)
            self._graph = _graph(files, _model_stamp() if plans else 0)
        return self._graph

    def signal(self, machine: dict, tag: str) -> dict | None:
        from app.ingestion.signal_view import main_view

        graph = self.graph()
        view = main_view(graph, tag) if graph.nodes else None
        if view is None:
            return None
        plan = next(
            (p for p, d in self.files() if d == "schematic" and p.suffix.lower() == ".pdf"), None
        )
        view["schematic"] = (
            {"document_id": offline_id("document", plan.name), "filename": plan.name}
            if plan
            else None
        )
        return view

    def conversations(self, machine: dict, meldung: str | None, moment: datetime) -> list[dict]:
        if not meldung:
            return []
        return [
            {
                "id": offline_id("conversation", machine["name"], meldung),
                "title": incident_title(meldung),
                "source_ids": [machine["source_id"]],
                "updated_at": iso_utc(moment),
                "outcome": "open",
                "finding": "",
            }
        ]

    def saved_answer(self, machine: dict, conversation_id: str) -> dict:
        raise SystemExit("--conversation braucht ein laufendes Backend (ohne --offline)")

    def answer_meta(self, machine: dict, answer: str) -> dict:
        """meta wie build_meta im Backend, aus dem Index des Ordners statt aus der Datenbank."""
        from app.api.answer_meta import (
            PlanRow,
            first_plan_rows,
            part_kinds,
            plan_spot,
            tags_in_answer,
        )
        from app.citations import DocIndex, check_citations, summary
        from app.models import TagType

        docs = self.index()
        devices = {row.tag for doc in docs for row in doc.rows if row.tag_type == TagType.DEVICE}
        tags = tags_in_answer(answer, devices)
        rows = [
            PlanRow(row.tag, row.page, row.section, doc.id, doc.path.name, str(doc.path))
            for doc in docs  # nach Dateinamen sortiert wie plan_rows
            if doc.doc_type == "schematic"
            for row in sorted(doc.rows, key=lambda r: r.page or 0)
            if row.tag in tags and row.tag_type == TagType.DEVICE and row.page is not None
        ]
        index = [
            DocIndex(
                filename=doc.path.name,
                is_pdf=doc.path.suffix.lower() == ".pdf",
                path=doc.path,
                pages=frozenset(p.page for p in doc.pieces if p.page is not None),
                page_count=doc.page_count,
                tags=frozenset(row.tag for row in doc.rows),
                sections=tuple(dict.fromkeys(p.section for p in doc.pieces if p.section)),
            )
            for doc in docs
        ]
        return {
            "referenced_tags": tags,
            "part_kinds": part_kinds(tags, {self.source_id: devices}),
            "plan_spots": [plan_spot(row) for row in first_plan_rows(tags, rows)],
            "citations_valid": summary(check_citations(answer, index, None)),
        }


# --- Vorlagen -----------------------------------------------------------------------------------


def first_signal(source, machine: dict, tags: list[str]) -> dict | None:
    """Hauptweg des ersten Kennzeichens, das einen hat (wie meta.signal_start)."""
    for tag in dict.fromkeys(tag for tag in tags if tag):
        found = source.signal(machine, tag)
        if found is not None:
            return found
    return None


def build_answer(args: argparse.Namespace, source, machine: dict, head: dict) -> dict:
    if args.conversation:
        saved = source.saved_answer(machine, args.conversation)
        antwort, meta, frage = saved["antwort"], saved["meta"], saved["frage"]
        meldung = args.meldung or saved["meldung"]
        moment = parse_time(args.zeit or saved["updated_at"])
    elif args.antwort:
        if not args.meldung:
            raise SystemExit("--meldung fehlt: sie ist die Frage und sucht in der Fehlerliste")
        antwort, meldung, frage = args.antwort, args.meldung, args.meldung
        meta = source.answer_meta(machine, antwort)
        moment = parse_time(args.zeit)
    else:
        raise SystemExit(
            "--antwort TEXT oder --conversation ID angeben (es wird kein Modell gefragt)"
        )
    shown = template_meta(meta)
    tags = [args.tag] if args.tag else [meta.get("signal_start"), *shown["referenced_tags"]]
    return {
        **head,
        "frage": frage,
        "zeit": clock(moment),
        "fault_hits": source.fault_hits(machine, meldung),
        "antwort": antwort,
        "meta": shown,
        "signal": first_signal(source, machine, tags),
    }


def build(args: argparse.Namespace, source) -> dict:
    machine = source.machine(args.maschine)
    head = {"vorlage": args.vorlage, "version": VERSION, "maschine": machine["name"]}
    if args.vorlage == "signalweg":
        if not args.tag:
            raise SystemExit("--tag fehlt, z. B. --tag -F2")
        signal = source.signal(machine, args.tag)
        if signal is None:
            raise SystemExit(f"{args.tag} kommt im Signalweg von {machine['name']} nicht vor")
        return {**head, "signal": signal}
    if args.vorlage == "stoerfaelle":
        conversations = source.conversations(machine, args.meldung, parse_time(args.zeit))
        return {**head, "ort": place(machine), "conversations": conversations}
    return build_answer(args, source, machine, head)


# --- Schema-Pruefung ----------------------------------------------------------------------------


def load_schemas() -> dict[str, dict]:
    """Alle Schemas nach $id (relativ, gleich dem Dateinamen)."""
    schemas = [json.loads(p.read_text(encoding="utf-8")) for p in SCHEMAS.glob("*.schema.json")]
    return {schema["$id"]: schema for schema in schemas}


_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _check(value, schema: dict, schemas: dict, base: str, where: str) -> list[str]:
    """Eingebaute Pruefung fuer die Teile von JSON Schema, die diese Schemas nutzen."""
    at = where.lstrip("/") or "(oben)"
    if "$ref" in schema:
        target, _, pointer = schema["$ref"].partition("#")
        node = schemas[target or base]
        for part in filter(None, pointer.split("/")):
            node = node[part]
        return _check(value, node, schemas, target or base, where)
    if "anyOf" in schema:
        if any(not _check(value, option, schemas, base, where) for option in schema["anyOf"]):
            return []
        return [f"{at}: passt zu keiner erlaubten Form"]
    kinds = schema.get("type")
    kinds = [kinds] if isinstance(kinds, str) else kinds or []
    if kinds and not any(_TYPES[kind](value) for kind in kinds):
        return [f"{at}: erwartet {' oder '.join(kinds)}"]
    errors = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{at}: erwartet {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{at}: {value!r} ist keiner von {schema['enum']}")
    if isinstance(value, dict):
        errors += [
            f"{at}: Feld {key} fehlt" for key in schema.get("required", []) if key not in value
        ]
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                errors += _check(item, properties[key], schemas, base, f"{where}/{key}")
            elif extra is False:
                errors.append(f"{at}: Feld {key} ist nicht vorgesehen")
            elif isinstance(extra, dict):
                errors += _check(item, extra, schemas, base, f"{where}/{key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            errors += _check(item, schema["items"], schemas, base, f"{where}/{index}")
    return errors


def validate(data: dict, use_jsonschema: bool | None = None) -> list[str]:
    """Verstoesse gegen das Schema der Vorlage; leer = gueltig.

    use_jsonschema: None = jsonschema, wenn installiert, sonst die eingebaute Pruefung; False = immer die
    eingebaute (Tests)."""
    schemas = load_schemas()
    name = f"{data.get('vorlage')}.schema.json"
    if name not in schemas:
        return [f"vorlage: unbekannt ({data.get('vorlage')!r}), erlaubt: {', '.join(VORLAGEN)}"]
    if use_jsonschema is not False:
        try:
            import jsonschema
            from referencing import Registry, Resource
        except ImportError:
            pass
        else:
            registry = Registry().with_resources(
                (key, Resource.from_contents(schema)) for key, schema in schemas.items()
            )
            validator = jsonschema.Draft202012Validator(schemas[name], registry=registry)
            # best_match steigt in anyOf ab: "signal/edges/0/via/0: 'foto' is not one of ..." statt des ganzen Objekts
            errors = [jsonschema.exceptions.best_match([e]) for e in validator.iter_errors(data)]
            return [
                f"{'/'.join(map(str, error.absolute_path)) or '(oben)'}: {error.message[:300]}"
                for error in errors
            ]
    return _check(data, schemas[name], schemas, name, "")


# --- Aufruf -------------------------------------------------------------------------------------


TEXT_OPTIONS = ("--tag", "--meldung", "--antwort")


def _glue_values(argv: list[str]) -> list[str]:
    """ "--tag -F2" -> "--tag=-F2": Kennzeichen und Meldungen beginnen oft mit einem Minus, argparse hielte den
    Wert sonst fuer eine Option."""
    glued: list[str] = []
    items = iter(argv)
    for item in items:
        glued.append(f"{item}={next(items, '')}" if item in TEXT_OPTIONS else item)
    return glued


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    argv = _glue_values(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--vorlage", required=True, choices=VORLAGEN)
    parser.add_argument("--maschine", required=True, help="Name oder ID der Maschine")
    parser.add_argument(
        "--api",
        default=os.environ.get("STROMLAUF_API_URL") or "http://localhost:8010",
        help="Backend-URL (Standard: STROMLAUF_API_URL, sonst http://localhost:8010)",
    )
    parser.add_argument(
        "--offline", type=Path, metavar="ORDNER", help="ohne Backend aus einem Beispielordner"
    )
    parser.add_argument("--meldung", help="Meldung vom Bedienpanel oder Symptom")
    parser.add_argument("--tag", help="Kennzeichen fuer den Signalweg, z. B. -F2")
    answer = parser.add_mutually_exclusive_group()
    answer.add_argument("--antwort", help="Antworttext (es wird kein Modell gefragt)")
    answer.add_argument("--conversation", help="Chat-ID: dessen letzte gespeicherte Antwort")
    parser.add_argument("--zeit", help="ISO-Zeitpunkt, z. B. 2026-10-01T09:41:00+02:00")
    parser.add_argument("--out", type=Path, help="Zieldatei; ohne Angabe nach stdout")
    return parser.parse_args(argv)


def offline_folder(path: Path) -> Path:
    for candidate in (path, ROOT / path):
        if candidate.is_dir():
            return candidate.resolve()
    raise SystemExit(f"Beispielordner {path} nicht gefunden")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = OfflineSource(offline_folder(args.offline)) if args.offline else ApiSource(args.api)
    data = build(args, source)
    errors = validate(data)
    if errors:
        print("Schema verletzt, nichts geschrieben:", *errors, sep="\n  ", file=sys.stderr)
        return 1
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"geschrieben: {args.out}", file=sys.stderr)
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
