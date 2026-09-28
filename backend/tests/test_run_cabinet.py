"""IoU-Rechnung und Zuordnung von eval/run_cabinet.py, ohne Backend."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))

from run_cabinet import iou, match, summarize  # noqa: E402


def test_iou_grundfaelle():
    a = {"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5}
    assert iou(a, a) == 1.0
    assert iou(a, {"x": 0.5, "y": 0.5, "w": 0.5, "h": 0.5}) == 0.0
    assert abs(iou(a, {"x": 0.25, "y": 0.0, "w": 0.5, "h": 0.5}) - 1 / 3) < 1e-9


def test_zuordnung_bevorzugt_gleiches_kennzeichen_und_halbiert_sonst():
    labels = [{"tag": "-K1", "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}, {"tag": "-F2", "x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1}]
    detected = [
        {"tag": "K1", "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1},
        {"tag": "-Q9", "x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1},
    ]
    rows = match(labels, detected)
    assert rows[0] == {"tag": "-K1", "iou": 1.0, "tag_ok": True, "detected_tag": "K1"}
    assert rows[1] == {"tag": "-F2", "iou": 0.5, "tag_ok": False, "detected_tag": "-Q9"}
    summary = summarize(rows, 0.5)
    assert summary == {"labels": 2, "treffer": 2, "anteil": 1.0, "iou_mittel": 0.75, "kennzeichen_ok": 0.5}
    assert match(labels, [])[0]["iou"] == 0.0
