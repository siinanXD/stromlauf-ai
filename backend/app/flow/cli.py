"""CLI: extract-flow <dokument> [--awl datei] [--extra datei ...] [--machine name] [--out datei] [--force]

Erzeugt das Ablauf-JSON nach schemas/machine_flow.json. Gleiche Dateien und gleiche Prompt-Version
kommen aus dem Cache (backend/data/flow_cache) ohne Modellaufruf. Logs als JSON-Zeilen auf stderr.
"""

import argparse
import logging
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="extract-flow", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("document", type=Path, help="Funktionsbeschreibung/Handbuch (PDF, MD, TXT) oder I/O-Liste")
    parser.add_argument("--awl", type=Path, help="SPS-Programm (AWL)")
    parser.add_argument("--extra", type=Path, action="append", default=[], help="weitere Dateien: Symboltabelle, Stueckliste, Klemmenplan")
    parser.add_argument("--machine", help="Maschinenname (sonst aus dem Dokument)")
    parser.add_argument("--out", type=Path, help="Zieldatei (sonst stdout)")
    parser.add_argument("--force", action="store_true", help="Cache ignorieren und neu extrahieren")
    parser.add_argument("--quiet", action="store_true", help="keine JSON-Logs")
    args = parser.parse_args(argv)

    from app.flow.extract import extract_flow, to_json
    from app.flow.tracing import configure_json_logging

    configure_json_logging(logging.WARNING if args.quiet else logging.INFO)
    paths = [args.document] + ([args.awl] if args.awl else []) + list(args.extra)
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"Datei fehlt: {', '.join(map(str, missing))}", file=sys.stderr)
        return 2
    try:
        flow = extract_flow(paths, machine=args.machine, force=args.force)
    except Exception as exc:  # CLI: Fehler als eine Zeile, Exit 1
        print(f"Extraktion fehlgeschlagen: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    text = to_json(flow)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        meta = flow.meta
        print(
            f"{args.out}: {len(flow.io_points)} I/O, {len(flow.steps)} Schritte, "
            f"{'Cache' if meta.cached else f'{meta.total.cost_usd:.4f} USD, {meta.total.latency_ms / 1000:.1f} s'}, "
            f"Trace {meta.trace_id}",
            file=sys.stderr,
        )
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
