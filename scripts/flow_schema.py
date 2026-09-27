"""Schreibt schemas/machine_flow.json aus backend/app/flow/schema.py oder prueft, ob es aktuell ist.

Aufruf:  python scripts/flow_schema.py --write   |   python scripts/flow_schema.py --check
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.flow.schema import json_schema  # noqa: E402

TARGET = REPO / "schemas" / "machine_flow.json"


def render() -> str:
    return json.dumps(json_schema(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    if "--write" in sys.argv:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(render(), encoding="utf-8")
        print(f"geschrieben: {TARGET.relative_to(REPO)}")
        return 0
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    if current == render():
        print("schemas/machine_flow.json ist aktuell")
        return 0
    print("schemas/machine_flow.json veraltet: python scripts/flow_schema.py --write")
    return 1


if __name__ == "__main__":
    sys.exit(main())
