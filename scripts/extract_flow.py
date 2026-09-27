"""Aufruf ohne Installation: python scripts/extract_flow.py <dokument> [--awl datei] ... (siehe app/flow/cli.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.flow.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
