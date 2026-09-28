"""IoU-Eval der Schaltschrank-Erkennung: POST /api/cabinets/{id}/detect gegen die gelabelten Boxen.

Aufruf:  python eval/run_cabinet.py [--api http://localhost:8010] [--labels examples/foerderband/07_Schaltschrank_Hotspots_FB-01.json]
                                    [--machine "Foerderband FB-01"] [--min-iou 0.5] [--min-share 0.8]

Kostet einen Vision-Aufruf (Claude). Laedt das Schaltschrankbild der Maschine, laesst erkennen und misst je
gelabeltem Bauteil die beste Ueberdeckung (IoU) mit einem erkannten Rahmen gleichen Kennzeichens; ohne
Kennzeichen-Treffer zaehlt der beste Rahmen ueberhaupt, aber nur halb. Gate: Anteil der Labels mit
IoU >= --min-iou muss >= --min-share sein (contract.md: 0,5 bei 80 %). Bestaetigte Hotspots bleiben erhalten,
die Erkennung ersetzt nur unbestaetigte Vorschlaege. Ergebnis: eval/results/cabinet_<zeitstempel>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit('httpx fehlt: cd backend && pip install -e ".[dev]"')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = HERE / "results"
DEFAULT_LABELS = ROOT / "examples" / "foerderband" / "07_Schaltschrank_Hotspots_FB-01.json"


def iou(a: dict, b: dict) -> float:
    ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1, bx2, by2 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union > 0 else 0.0


def _norm(tag: str) -> str:
    return (tag or "").replace(" ", "").upper().lstrip("-")


def match(labels: list[dict], detected: list[dict]) -> list[dict]:
    """Je Label: bestes IoU mit gleichem Kennzeichen, sonst bestes IoU ueberhaupt (halb gewertet)."""
    rows = []
    for label in labels:
        same = [d for d in detected if _norm(d.get("tag", "")) == _norm(label["tag"])]
        if same:
            best = max(same, key=lambda d: iou(label, d))
            rows.append({"tag": label["tag"], "iou": round(iou(label, best), 3), "tag_ok": True, "detected_tag": best.get("tag", "")})
        elif detected:
            best = max(detected, key=lambda d: iou(label, d))
            rows.append({"tag": label["tag"], "iou": round(iou(label, best) / 2, 3), "tag_ok": False, "detected_tag": best.get("tag", "")})
        else:
            rows.append({"tag": label["tag"], "iou": 0.0, "tag_ok": False, "detected_tag": ""})
    return rows


def summarize(rows: list[dict], min_iou: float) -> dict:
    n = len(rows) or 1
    hits = sum(1 for r in rows if r["iou"] >= min_iou)
    return {
        "labels": len(rows),
        "treffer": hits,
        "anteil": round(hits / n, 3),
        "iou_mittel": round(sum(r["iou"] for r in rows) / n, 3),
        "kennzeichen_ok": round(sum(1 for r in rows if r["tag_ok"]) / n, 3),
    }


def _auth_headers() -> dict[str, str]:
    key = os.environ.get("STROMLAUF_API_KEY", "").strip()
    return {"X-API-Key": key} if key else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--machine", default="Foerderband FB-01")
    parser.add_argument("--min-iou", type=float, default=0.5)
    parser.add_argument("--min-share", type=float, default=0.8)
    args = parser.parse_args()

    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    with httpx.Client(base_url=args.api, timeout=300, headers=_auth_headers()) as client:
        machines = client.get("/api/machines").raise_for_status().json()
        machine = next((m for m in machines if m["name"] == args.machine), None)
        if machine is None:
            sys.exit(f"Maschine {args.machine!r} fehlt im Backend (scripts/load_example.py).")
        detail = client.get(f"/api/machines/{machine['id']}").raise_for_status().json()
        if not detail["cabinets"]:
            sys.exit("Maschine hat kein Schaltschrankbild.")
        cabinet_id = detail["cabinets"][0]["id"]
        # Vorschlaege der Erkennung stehen unbestaetigt neben den bestaetigten Labels
        result = client.post(f"/api/cabinets/{cabinet_id}/detect").raise_for_status().json()
        detected = [h for h in result["hotspots"] if h.get("origin") == "vision" and not h.get("confirmed")]

    rows = match(labels, detected)
    summary = summarize(rows, args.min_iou)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"cabinet_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows, "detected": detected}, indent=1, ensure_ascii=False), encoding="utf-8")
    for r in rows:
        print(f"  {'OK ' if r['iou'] >= args.min_iou else 'NOK'} {r['tag']:<8} IoU {r['iou']:.2f} {'' if r['tag_ok'] else '(Kennzeichen anders: ' + (r['detected_tag'] or '-') + ')'}")
    print(f"{summary['treffer']}/{summary['labels']} Labels mit IoU >= {args.min_iou} ({summary['anteil']:.0%}), IoU-Mittel {summary['iou_mittel']:.2f} -> {out}")
    if summary["anteil"] < args.min_share:
        print(f"Unter Schwelle: {summary['anteil']:.0%} < {args.min_share:.0%}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
