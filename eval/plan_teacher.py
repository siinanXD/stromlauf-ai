"""Lehrerlauf fuer den Planleser (Spec 4.3): ein Modell liest oeffentliche Plaene, der Vergleich zeigt, wo Regeln fehlen.

Aufruf:  python eval/plan_teacher.py --model openai:gpt-5-mini --gold eval/ingest_gold/fb01.json [--doc PFAD]
                                     [--gold ... [--doc ...]] [--base-url URL] [--yes] [--out eval/results]
         python eval/plan_teacher.py --from-result eval/results/plan_teacher_<datum>.json [--gold ...]

Ohne --yes nennt das Skript nur Modell, Anbieter, Seiten und die geschaetzten USD und ruft kein Modell auf. Mit --yes
kostet der Lauf Geld (ausser bei lokalem Endpunkt); er laeuft nie in der CI. --from-result rechnet Vergleich und
Zusammenfassung aus einem gespeicherten Lauf neu, ohne Modell.

An ein Modell gehen nur oeffentliche Beispielplaene: PDFs unter examples/ und testdata/qelectrotech/ des Repos
(Spec "Datenschutz"). Alles andere lehnt das Skript mit Exit 2 ab, bevor es das Dokument liest; ein Gold unter
testdata/private/ wird gar nicht erst geoeffnet. Nur ein lokaler Endpunkt (--base-url auf localhost, 127.0.0.1 oder
::1) hebt das auf, denn dann verlaesst keine Seite den Rechner.

Je Dokument:
- Kennzeichen je Seite aus derselben Lesekette wie der Upload (pipeline.document_pieces -> split_pieces -> tag_rows),
- Modellkanten ueber app/ingestion/plan_model.py (gleicher Prompt, gleiche Pruefung wie im Produkt),
- Wahrheit: die gezeichneten Leitungen im Gold, oberster Schluessel `wires` = {"<seite>": [[a, b], ...]}
  (scripts/example_docs/make_gold.py),
- Regeln: die Kanten des Leitungslesers (`plan_wires.plan_edges`), soweit es ihn in diesem Stand gibt.
Verglichen werden ungerichtete Paare, Anschluesse gehen in ihrem Geraet auf ("-K1:A1" -> "-K1", wie
eval/run_plan_graph.py); Klemmen und Adressen bleiben. Je Seite drei Gruppen: "Modell richtig, Regeln fehlen"
(Kandidat fuer eine neue Regel), "Regeln falsch" (Fehler in einer Regel), "Modell falsch" (wird ignoriert); je
Dokument Precision und Recall von Modell und Regeln gegen die Wahrheit. Eine Seite am Laengenlimit des Modells zaehlt
als gescheitert mit Grund "Laengenlimit". Ergebnis: eval/results/plan_teacher_<datum>.json.
"""

import argparse
import json
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "backend"))

import evallib  # noqa: E402

FORMAT = 2  # 1: erster Lauf (Fehlertext roh); 2: Grund "Laengenlimit", Effort und Ausgabe-Annahme im Ergebnis
# Erlaubnisliste statt Sperrliste: Ein neues Firmendokument muss niemand erst eintragen
PUBLIC_DIRS = ("examples", "testdata/qelectrotech")
PUBLIC_ONLY = "Nur oeffentliche Beispielplaene (examples/, testdata/qelectrotech/) duerfen an ein bezahltes Modell."
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
LENGTH_LIMIT = "Laengenlimit"  # wie app.ingestion.plan_model.LENGTH_LIMIT
GROUPS = ("modell_richtig_regeln_fehlen", "regeln_falsch", "modell_falsch")
GROUP_LABELS = {
    "modell_richtig_regeln_fehlen": "Modell richtig, Regeln fehlen",
    "regeln_falsch": "Regeln falsch",
    "modell_falsch": "Modell falsch",
}

Pair = tuple[str, str]
Pages = dict[int, set[Pair]]
TagsFn = Callable[[Path, str], dict[int, set[str]]]
RulesFn = Callable[[Path], list | None]


def repo_roots() -> list[Path]:
    """Dieses Repo und, fuer eine Arbeitskopie unter .claude/worktrees/, der Haupt-Checkout: testdata/ ist ignoriert
    und liegt nur dort."""
    roots = [ROOT]
    if ROOT.parent.name == "worktrees" and ROOT.parent.parent.name == ".claude":
        roots.append(ROOT.parent.parent.parent)
    return roots


def is_public(path: Path) -> bool:
    """Oeffentlicher Beispielplan: ein PDF unter examples/ oder testdata/qelectrotech/ des Repos (nach Aufloesen von
    "..", Verknuepfungen und relativen Pfaden)."""
    path = Path(path).resolve()
    if path.suffix.lower() != ".pdf":
        return False
    return any(
        path.is_relative_to((root / folder).resolve())
        for root in repo_roots()
        for folder in PUBLIC_DIRS
    )


def in_private_dir(path: Path) -> bool:
    """Unter testdata/private/ (auch in einer anderen Arbeitskopie)."""
    for parts in (Path(path).parts, Path(path).resolve().parts):
        lowered = [part.lower() for part in parts]
        if any(
            a == "testdata" and b == "private" for a, b in zip(lowered, lowered[1:], strict=False)
        ):
            return True
    return False


def is_local(base_url: str) -> bool:
    """Endpunkt auf diesem Rechner: Nur dann darf auch ein nicht oeffentlicher Plan ans Modell."""
    return bool(base_url) and urlparse(base_url).hostname in LOCAL_HOSTS


def refuse_docs(docs: Iterable[Path], base_url: str) -> bool:
    """Meldet und verweigert Plaene ausserhalb der Erlaubnisliste; True heisst Abbruch."""
    if is_local(base_url):
        return False
    refused = [Path(doc) for doc in docs if not is_public(Path(doc))]
    if refused:
        print(f"{PUBLIC_ONLY} Abgelehnt: {', '.join(p.name for p in refused)}", file=sys.stderr)
    return bool(refused)


def refuse_golds(golds: Iterable[Path], base_url: str) -> bool:
    """Ein Gold unter testdata/private/ gehoert zu einem Firmendokument: nicht oeffnen."""
    if is_local(base_url):
        return False
    refused = [Path(gold) for gold in golds if in_private_dir(gold)]
    if refused:
        print(
            f"{PUBLIC_ONLY} Gold unter testdata/private/ wird nicht gelesen. "
            f"Abgelehnt: {', '.join(p.name for p in refused)}",
            file=sys.stderr,
        )
    return bool(refused)


def page_count(doc: Path) -> int:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(doc))
    try:
        return len(pdf)
    finally:
        pdf.close()


def index_tags(doc: Path, doc_type: str) -> dict[int, set[str]]:
    """Kennzeichen je Seite wie im Index des Uploads, ohne Datenbank (wie eval/run_ingest.py)."""
    from app.ingestion.pipeline import document_pieces, split_pieces, tag_rows
    from app.ingestion.plan_model import PAGE_TAG_TYPES

    tags: dict[int, set[str]] = {}
    for row in tag_rows(split_pieces(document_pieces(doc, doc_type).pieces)):
        if row.page is not None and str(row.tag_type) in PAGE_TAG_TYPES:
            tags.setdefault(row.page, set()).add(row.tag)
    return tags


def rule_edges(doc: Path) -> list | None:
    """Kanten des Leitungslesers; None, solange es ihn in diesem Stand nicht gibt."""
    try:
        from app.ingestion.plan_wires import plan_edges
    except ImportError:
        return None
    return plan_edges(doc)


def collapse(node: str) -> str:
    """Anschluss -> Geraet ("-K1:A1" -> "-K1"), wie das Gold; Klemmen ("-X3:1") und Adressen bleiben."""
    if node.startswith("-") and ":" in node and not node.startswith("-X"):
        return node.split(":", 1)[0]
    return node


def pair(source: str, target: str) -> Pair | None:
    """Ungerichtetes Paar nach dem Zusammenlegen; None, wenn beide Enden dasselbe Geraet sind."""
    a, b = collapse(source), collapse(target)
    return None if a == b else (min(a, b), max(a, b))


def by_page(items: Iterable[tuple[int, str, str]]) -> Pages:
    pages: Pages = {}
    for page, source, target in items:
        if (found := pair(source, target)) is not None:
            pages.setdefault(int(page), set()).add(found)
    return pages


def gold_wires(gold: dict | None) -> Pages | None:
    """Gezeichnete Leitungen je Seite aus `wires`; None, wenn das Gold keine fuehrt."""
    if not gold or "wires" not in gold:
        return None
    return by_page(
        (page, wire[0], wire[1]) for page, wires in gold["wires"].items() for wire in wires
    )


def failure(text: str | None) -> str | None:
    """Grund einer gescheiterten Seite; der Fehler des OpenAI-SDK am Limit heisst Laengenlimit (auch in Format 1)."""
    if not text:
        return None
    if text == LENGTH_LIMIT or "LengthFinishReasonError" in text or "length limit" in text:
        return LENGTH_LIMIT
    return text


def compare_page(truth: set[Pair] | None, rules: set[Pair] | None, model: set[Pair]) -> dict:
    """Die drei Gruppen einer Seite; None, wo Wahrheit oder Regeln fehlen."""
    if truth is None:
        return {"modell_richtig": None, **{group: None for group in GROUPS}}
    return {
        "modell_richtig": sorted(model & truth),
        "modell_richtig_regeln_fehlen": None if rules is None else sorted((model & truth) - rules),
        "regeln_falsch": None if rules is None else sorted(rules - truth),
        "modell_falsch": sorted(model - truth),
    }


def _ratio(hits: int, total: int) -> float | None:
    return None if total == 0 else round(hits / total, 4)


def scores(found: set, truth: set) -> dict:
    tp = len(found & truth)
    return {
        "tp": tp,
        "fp": len(found - truth),
        "fn": len(truth - found),
        "precision": _ratio(tp, len(found)),
        "recall": _ratio(tp, len(truth)),
    }


def _flat(pages: Pages | None) -> set:
    return {(page, *found) for page, pairs in (pages or {}).items() for found in pairs}


def compare_document(model: Pages, truth: Pages | None, rules: Pages | None) -> tuple[dict, dict]:
    """Gruppen je Seite und die Zahlen des Dokuments (Precision/Recall gegen die Wahrheit, Gruppen gezaehlt)."""
    pages = sorted(set(model) | set(truth or {}) | set(rules or {}))
    per_page = {
        page: compare_page(
            None if truth is None else truth.get(page, set()),
            None if rules is None else rules.get(page, set()),
            model.get(page, set()),
        )
        for page in pages
    }
    counts = {
        group: None
        if truth is None or (rules is None and group != "modell_falsch")
        else sum(len(groups[group]) for groups in per_page.values())
        for group in GROUPS
    }
    summary = {
        "wahrheit": truth is not None,
        "regeln": rules is not None,
        "gruppen": counts,
        "modell_gegen_wahrheit": None if truth is None else scores(_flat(model), _flat(truth)),
        "regeln_gegen_wahrheit": None
        if truth is None or rules is None
        else scores(_flat(rules), _flat(truth)),
    }
    return per_page, summary


def resolve_jobs(docs: list[Path], golds: list[Path]) -> list[tuple[Path, Path | None]]:
    """Paare (Dokument, Gold): ohne --doc nimmt das Skript das Dokument aus dem Gold."""
    if docs and golds and len(docs) != len(golds):
        raise ValueError("--doc und --gold muessen gleich oft vorkommen (paarweise)")
    if docs:
        return list(zip(docs, golds or [None] * len(docs), strict=True))
    return [
        (ROOT / json.loads(gold.read_text(encoding="utf-8"))["dokument"], gold) for gold in golds
    ]


def _relative(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _edge_row(edge, reasons: dict) -> dict:
    return {
        "source": edge.source,
        "target": edge.target,
        "directed": edge.directed,
        "reason": reasons.get((edge.source, edge.target), ""),
    }


def read_document(
    model, model_name: str, doc: Path, doc_type: str, tags_fn: TagsFn, workers: int
) -> tuple[list[dict], object]:
    """Ein Dokument per Modell lesen: Zeilen je Seite (ohne Vergleich) und die gemeldeten Tokens."""
    from app.ingestion import plan_model

    tags = tags_fn(doc, doc_type)
    reads = plan_model.read_pages(model, doc, tags, model_name=model_name, workers=workers)
    rows = [
        {
            "dokument": _relative(doc),
            "seite": read.page,
            "kennzeichen": len(tags.get(read.page, ())),
            "kanten": [_edge_row(edge, read.reasons) for edge in read.kept],
            "verworfen": [_edge_row(edge, read.reasons) for edge in read.dropped],
            "fehler": read.error,
            "tokens": None
            if read.usage is None
            else [read.usage.input_tokens, read.usage.output_tokens],
        }
        for read in reads
    ]
    return rows, plan_model.total_usage(reads)


def evaluate(
    rows: list[dict], jobs: list[tuple[Path, Path | None]], rules_fn: RulesFn
) -> tuple[list[dict], dict]:
    """Vergleich Wahrheit / Regeln / Modell je Seite und Dokument aus den Zeilen eines Laufs, ohne Modell.

    Schreibt `vergleich` und den Grund in `fehler` in die Zeilen und liefert die Felder der Zusammenfassung."""
    documents = []
    totals = {"model": set(), "rules": set(), "truth": set()}
    groups: dict[str, int | None] = dict.fromkeys(GROUPS, 0)
    for doc, gold_path in jobs:
        name = _relative(doc)
        doc_rows = [row for row in rows if row["dokument"] == name]
        gold = json.loads(gold_path.read_text(encoding="utf-8")) if gold_path else None
        truth = gold_wires(gold)
        found = rules_fn(doc) if Path(doc).exists() else None
        rules = None if found is None else by_page((e.page, e.source, e.target) for e in found)
        model = by_page(
            (row["seite"], edge["source"], edge["target"])
            for row in doc_rows
            for edge in row["kanten"]
        )
        per_page, summary = compare_document(model, truth, rules)
        for row in doc_rows:
            row["fehler"] = failure(row.get("fehler"))
            row["vergleich"] = per_page.get(
                row["seite"],
                compare_page(
                    None if truth is None else set(), None if rules is None else set(), set()
                ),
            )
        for group, count in summary["gruppen"].items():
            groups[group] = (
                None if count is None or groups[group] is None else groups[group] + count
            )
        for key, pages in (("model", model), ("rules", rules), ("truth", truth)):
            totals[key] |= {(name, *item) for item in _flat(pages)}
        documents.append(
            {
                "dokument": name,
                "gold": _relative(gold_path) if gold_path else None,
                "kanten": len(_flat(model)),
                **summary,
            }
        )
    has_truth = bool(documents) and all(d["wahrheit"] for d in documents)
    has_rules = bool(documents) and all(d["regeln"] for d in documents)
    failed = [[row["dokument"], row["seite"], row["fehler"]] for row in rows if row["fehler"]]
    return rows, {
        "kanten": len(totals["model"]),
        "verworfen": sum(len(row.get("verworfen") or []) for row in rows),
        "seiten_gelesen": len(rows),
        "seiten_fehler": failed,
        "seiten_laengenlimit": sum(1 for *_, reason in failed if reason == LENGTH_LIMIT),
        "wahrheit": has_truth,
        "regeln": has_rules,
        "gruppen": {GROUP_LABELS[g]: n if has_truth else None for g, n in groups.items()},
        "modell_gegen_wahrheit": scores(totals["model"], totals["truth"]) if has_truth else None,
        "regeln_gegen_wahrheit": scores(totals["rules"], totals["truth"])
        if has_truth and has_rules
        else None,
        "je_dokument": documents,
    }


def report(summary: dict, out: Path) -> None:
    cost = summary.get("kosten_usd")
    print(
        f"Kanten: {summary['kanten']}, verworfen: {summary['verworfen']}, "
        f"Kosten: {'-' if cost is None else f'{cost:.4f}'} USD"
    )
    failed = summary["seiten_fehler"]
    if failed:
        print(
            f"Seiten gescheitert: {', '.join(f'{doc} S. {page} ({why})' for doc, page, why in failed)}"
        )
    for label, count in summary["gruppen"].items():
        print(f"  {label}: {'-' if count is None else count}")
    for document in summary["je_dokument"]:
        model, rules = document["modell_gegen_wahrheit"], document["regeln_gegen_wahrheit"]
        line = f"  {document['dokument']}: {document['kanten']} Kanten"
        if model:
            line += f", Modell P {model['precision']} R {model['recall']}"
        if rules:
            line += f", Regeln P {rules['precision']} R {rules['recall']}"
        print(line)
    if not summary["wahrheit"]:
        print("Gold ohne `wires`: kein Vergleich gegen die Wahrheit.")
    if not summary["regeln"]:
        print("Leitungsleser in diesem Stand nicht vorhanden: Gruppen mit Regeln bleiben leer.")
    print(f"Ergebnis: {out}")


def from_result(path: Path, golds: list[Path], out_dir: Path, rules_fn: RulesFn) -> int:
    """Vergleich und Zusammenfassung eines gespeicherten Laufs neu rechnen, ohne Modellaufruf."""
    if not path.exists():
        print(f"Datei fehlt: {path}", file=sys.stderr)
        return 1
    saved = json.loads(path.read_text(encoding="utf-8"))
    summary, rows = saved.get("summary", {}), saved.get("results", [])
    missing = [row for row in rows if not {"dokument", "seite", "kanten"} <= set(row)]
    names = (
        []
        if missing
        else summary.get("dokumente") or list(dict.fromkeys(r["dokument"] for r in rows))
    )
    if missing or not names:
        print("Ergebnis ohne Kanten je Seite: nicht auswertbar.", file=sys.stderr)
        return 1
    saved_golds = summary.get("gold") or [None] * len(names)
    if golds and len(golds) != len(names):
        print(
            f"--gold braucht {len(names)} Angaben (eine je Dokument im Ergebnis)", file=sys.stderr
        )
        return 1
    gold_paths = golds or [ROOT / gold if gold else None for gold in saved_golds]
    jobs = [(ROOT / name, gold) for name, gold in zip(names, gold_paths, strict=True)]
    absent = [gold for _, gold in jobs if gold and not gold.exists()]
    if absent:
        print(f"Gold fehlt: {', '.join(str(g) for g in absent)}", file=sys.stderr)
        return 1
    rows, fields = evaluate(rows, jobs, rules_fn)
    keep = ("modell", "lokal", "prompt_version", "seiten", "schaetzung_usd", "kosten_usd", "tokens")
    result = {
        **{key: summary.get(key) for key in keep},
        **{
            key: summary[key]
            for key in ("reasoning_effort", "ausgabe_token_je_seite")
            if key in summary
        },
        "format": FORMAT,
        "neu_gerechnet_aus": _relative(path),
        **fields,
    }
    out = evallib.save_result(out_dir / f"plan_teacher_{evallib.run_id()}.json", result, rows)
    print(f"Neu gerechnet aus {path.name}, ohne Modellaufruf (Modell: {result['modell']})")
    report(result, out)
    return 0


def main(
    argv: list[str] | None = None, tags_fn: TagsFn = index_tags, rules_fn: RulesFn = rule_edges
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", help="z. B. openai:gpt-5-mini")
    parser.add_argument(
        "--doc", type=Path, action="append", default=[], help="Stromlaufplan-PDF (mehrfach)"
    )
    parser.add_argument(
        "--gold", type=Path, action="append", default=[], help="Gold mit `wires` (mehrfach)"
    )
    parser.add_argument(
        "--base-url", default="", help="OpenAI-kompatibler Endpunkt, etwa Ollama (kostenlos)"
    )
    parser.add_argument("--yes", action="store_true", help="Modell wirklich aufrufen (kostet Geld)")
    parser.add_argument(
        "--from-result",
        type=Path,
        help="gespeicherten Lauf (eval/results/plan_teacher_*.json) ohne Modell neu auswerten",
    )
    parser.add_argument("--workers", type=int, default=4, help="Seiten gleichzeitig")
    parser.add_argument("--out", type=Path, default=RESULTS, help="Ordner fuer das Ergebnis")
    args = parser.parse_args(argv)

    if args.from_result:  # schickt nichts an ein Modell und liest nur, was der Lauf schon hatte
        if args.doc or args.yes:
            parser.error("--from-result rechnet nur neu: ohne --doc und ohne --yes")
        return from_result(args.from_result, args.gold, args.out, rules_fn)
    if not args.model:
        parser.error("--model angeben (oder --from-result)")
    if not args.doc and not args.gold:
        parser.error("--doc oder --gold angeben")
    # Erlaubnisliste vor jedem Lesen eines Plans, auch vor dem Oeffnen des Golds
    if refuse_docs(args.doc, args.base_url) or refuse_golds(args.gold, args.base_url):
        return 2
    try:
        jobs = resolve_jobs(args.doc, args.gold)
    except ValueError as exc:
        parser.error(str(exc))
    if refuse_docs([doc for doc, _ in jobs], args.base_url):  # Plan, den erst das Gold nennt
        return 2
    missing = [doc for doc, _ in jobs if not doc.exists()]
    if missing:
        print(f"Datei fehlt: {', '.join(str(p) for p in missing)}", file=sys.stderr)
        return 1

    from app.ingestion import plan_model
    from app.llm import is_reasoning_model

    counts = [(doc, page_count(doc)) for doc, _ in jobs]
    pages = sum(count for _, count in counts)
    estimate = 0.0 if args.base_url else plan_model.estimate_usd(args.model, pages)
    output = plan_model.output_tokens_per_page(args.model)
    effort = plan_model.REASONING_EFFORT if is_reasoning_model(args.model) else None
    provider = "lokaler Endpunkt" if args.base_url else args.model.split(":", 1)[0]
    print(f"Lehrerlauf Planleser, Prompt-Version {plan_model.PROMPT_VERSION}")
    print(f"Anbieter: {provider}, Modell: {args.model}")
    for doc, count in counts:
        print(f"  {_relative(doc)}: {count} Seiten")
    thinking = f", Reasoning-Modell mit Effort {effort}" if effort else ""
    print(
        f"Seiten: {pages}, geschaetzt bis zu {estimate:.5f} USD "
        f"({plan_model.INPUT_TOKENS_PER_PAGE} Token rein, {output} raus je Seite{thinking}; "
        f"hoechstens {plan_model.MAX_TOKENS} raus je Seite; "
        f"Seiten mit weniger als {plan_model.MIN_PAGE_TAGS} Kennzeichen gehen nicht ans Modell)"
    )
    if not args.yes:
        print("Kein Modellaufruf. Starten mit --yes, erst nach Freigabe der Kosten.")
        return 0

    from app.llm import MissingKeyError

    try:
        model = plan_model.make_model(args.model, args.base_url)
    except (MissingKeyError, ValueError) as exc:
        print(f"Modell nicht nutzbar: {exc}", file=sys.stderr)
        return 1

    rows: list[dict] = []
    usage = None
    for doc, gold_path in jobs:
        gold = json.loads(gold_path.read_text(encoding="utf-8")) if gold_path else {}
        doc_rows, doc_usage = read_document(
            model, args.model, doc, gold.get("doc_type", "schematic"), tags_fn, args.workers
        )
        rows += doc_rows
        if doc_usage is not None:
            usage = doc_usage if usage is None else usage + doc_usage
    rows, fields = evaluate(rows, jobs, rules_fn)
    summary = {
        "format": FORMAT,
        "modell": args.model,
        "lokal": bool(args.base_url),
        "prompt_version": plan_model.PROMPT_VERSION,
        "reasoning_effort": effort,
        "ausgabe_token_je_seite": output,
        "max_tokens": plan_model.MAX_TOKENS,
        "dokumente": [_relative(doc) for doc, _ in jobs],
        "gold": [_relative(gold) if gold else None for _, gold in jobs],
        "seiten": pages,
        "schaetzung_usd": estimate,
        "kosten_usd": plan_model.run_cost_usd(usage, args.base_url),
        "tokens": None
        if usage is None
        else {"rein": usage.input_tokens, "raus": usage.output_tokens},
        **fields,
    }
    out = evallib.save_result(args.out / f"plan_teacher_{evallib.run_id()}.json", summary, rows)
    report(summary, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
