"""Erzeugt den Beispielsatz Foerderband FB-01: python scripts/example_docs/build.py examples/foerderband"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
out = Path(sys.argv[1] if len(sys.argv) > 1 else "examples/foerderband").resolve()
out.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, str(HERE / "make_pdf.py"), str(out / "01_Stromlaufplan_FB-01.pdf")], check=True, cwd=HERE)
subprocess.run([sys.executable, str(HERE / "make_rest.py"), str(out)], check=True, cwd=HERE)
print(f"Beispielsatz erzeugt in {out}")
