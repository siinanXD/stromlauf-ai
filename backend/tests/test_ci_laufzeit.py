"""CI-Laufzeit: CPU-Torch in jedem Job, Docker-Abhaengigkeiten vor dem Code (Messung 2026-09-30)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TORCH_INSTALLS = (".github/workflows/ci.yml", ".github/workflows/eval.yml", "backend/Dockerfile")


def test_torch_und_torchvision_kommen_ueberall_gemeinsam_aus_dem_cpu_index():
    """torchvision von PyPI verlangt ein bestimmtes torch. Liegt im CPU-Index ein neueres, ersetzt pip das CPU-Torch
    durch CUDA-Torch: rund 3 GB NVIDIA-Pakete je Lauf, und die Tests laufen mit einer anderen Variante als Eval und
    Produktion."""
    for path in TORCH_INSTALLS:
        text = (ROOT / path).read_text(encoding="utf-8")
        installs = re.findall(r"pip install [^\n]*\btorch\b[^\n]*", text)
        assert installs, path
        for line in installs:
            assert "torchvision" in line and "download.pytorch.org/whl/cpu" in line, (path, line)


def test_dockerfile_installiert_die_abhaengigkeiten_vor_dem_code():
    """Sonst baut jede Aenderung unter backend/app den Layer mit Torch und Docling (rund 640 MB) neu."""
    lines = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8").splitlines()
    install = next(i for i, line in enumerate(lines) if 'pip install -e ".[' in line)
    copies = [i for i, line in enumerate(lines) if line.startswith("COPY ")]
    code = [i for i in copies if "pyproject.toml" not in lines[i]]
    assert code and all(i > install for i in code), [lines[i] for i in code]
