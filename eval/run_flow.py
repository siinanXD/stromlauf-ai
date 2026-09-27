"""Ablauf-Extraktion gegen Gold messen: Recall/Precision der I/O-Liste, Schrittanzahl, Belege.

Aufruf:  python eval/run_flow.py --gold testdata/festo/gold.flow.json --pred <flow.json>
                                 [--min-recall 0.9] [--min-precision 0.9] [--out eval/results/flow_<zeit>.json]

Kein Modellaufruf: --pred ist ein vorhandenes Extraktions-JSON (scripts/extract_flow.py). Exit-Code 1,
wenn eine Schwelle unterschritten wird oder die Schrittanzahl ausserhalb der Toleranz liegt.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app.flow.evaluate import compare, is_template  # noqa: E402
from app.flow.schema import MachineFlow  # noqa: E402

RESULTS = HERE / "results"


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f} %"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gold", type=Path, default=HERE.parent / "testdata" / "festo" / "gold.flow.json")
    parser.add_argument("--pred", type=Path, required=True, help="Extraktions-JSON")
    parser.add_argument("--min-recall", type=float, default=None)
    parser.add_argument("--min-precision", type=float, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    gold = MachineFlow.model_validate_json(args.gold.read_text(encoding="utf-8"))
    pred = MachineFlow.model_validate_json(args.pred.read_text(encoding="utf-8"))
    if is_template(gold):
        print(f"{args.gold}: noch die Vorlage (summary beginnt mit VORLAGE). Erst ausfuellen, siehe testdata/festo/README.md")
        return 2

    result = compare(gold, pred)
    io, steps, evidence, meta = result["io"], result["steps"], result["evidence"], result["meta"]
    print(f"Gold: {args.gold.name}   Extraktion: {args.pred.name}   Prompt {meta['prompt_version']}   Modelle {meta['models']}")
    print(f"I/O   Recall {_pct(io['recall'])} ({io['matched']}/{io['gold']})   Precision {_pct(io['precision'])} ({io['matched']}/{io['pred']})")
    for name, value in io["fields"].items():
        print(f"      {name:<10} {_pct(value)}")
    if io["missing"]:
        print(f"      fehlt: {', '.join(io['missing'])}")
    if io["extra"]:
        print(f"      zu viel: {', '.join(io['extra'])}")
    print(f"Schritte  Gold {steps['gold']}   Extraktion {steps['pred']}   Delta {steps['delta']:+d}   {'ok' if steps['count_ok'] else 'AUSSERHALB TOLERANZ'}   Namen {_pct(steps['names_recall'])}")
    print(f"Belege    {evidence['objects']} Objekte, {_pct(evidence['assumption_share'])} Annahmen, mittlere Sicherheit {evidence['mean_confidence']}")
    if evidence["unresolved_refs"]:
        print(f"          Verweise ohne I/O: {', '.join(evidence['unresolved_refs'])}")
    print(f"Kosten    {meta['cost_usd']:.4f} USD, {meta['latency_ms'] / 1000:.1f} s{' (Cache)' if meta['cached'] else ''}, Trace {meta['trace_id']}")

    RESULTS.mkdir(exist_ok=True)
    out = args.out or RESULTS / f"flow_{datetime.now():%Y-%m-%d_%H%M%S}.json"
    out.write_text(json.dumps({"gold": str(args.gold), "pred": str(args.pred), **result}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Ergebnis: {out}")

    failed = []
    if args.min_recall is not None and (io["recall"] or 0) < args.min_recall:
        failed.append(f"Recall {_pct(io['recall'])} < {_pct(args.min_recall)}")
    if args.min_precision is not None and (io["precision"] or 0) < args.min_precision:
        failed.append(f"Precision {_pct(io['precision'])} < {_pct(args.min_precision)}")
    if not steps["count_ok"]:
        failed.append("Schrittanzahl ausserhalb der Toleranz")
    if failed:
        print("NICHT BESTANDEN: " + "; ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
