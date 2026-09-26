"""Erzeugt die Testdokumentation: python scripts/testdoku/build.py [ur01|pm1_ar|all] [examples]

Braucht reportlab und openpyxl (`pip install -e "backend[examples]"`). Kein KI-Aufruf.
"""

import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from render_pdf import render  # noqa: E402
from render_rest import render_all, terminal_rows  # noqa: E402

SETS = {"ur01": "umroller", "pm1_ar": "aufrollung"}


def build(name: str, root: Path) -> Path:
    machine = importlib.import_module(f"machines.{name}").MACHINE
    out = root / SETS[name]
    out.mkdir(parents=True, exist_ok=True)
    refs = render(machine, out / f"01_Stromlaufplan_{machine.code}.pdf", terminal_rows)
    render_all(machine, refs, out)
    missing = [d.bmk for d in machine.devices if not refs.has(d.bmk)]
    if missing:
        raise SystemExit(f"{machine.code}: ohne Blattverweis im Plan: {missing}")
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    root = Path(sys.argv[2] if len(sys.argv) > 2 else "examples").resolve()
    for name in SETS if which == "all" else [which]:
        print("erzeugt:", build(name, root))
