"""CI-Laufzeit: CPU-Torch in jedem Job, Docker-Abhaengigkeiten vor dem Code, Eval-Gates parallel (Messung
2026-09-30)."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
EVAL_YML = ROOT / ".github" / "workflows" / "eval.yml"
TORCH_INSTALLS = (".github/workflows/ci.yml", ".github/workflows/eval.yml", "backend/Dockerfile")
# Quellen des Retrieval-Gates; FB-01 laedt scripts/acceptance.py --load, die anderen scripts/load_folder.py --name
GATE_SOURCES = {
    "Foerderband FB-01",
    "Injection-Test",
    "Scan FB-01",
    "Umroller UR-01",
    "Aufrollung PM1-AR",
}


def _eval_jobs() -> dict:
    return yaml.safe_load(EVAL_YML.read_text(encoding="utf-8"))["jobs"]


def _loaded_sources(steps: list[dict], group: str) -> set[str]:
    """Quellen, die die Steps einer Matrix-Gruppe laden (Steps ohne Bedingung laufen in jeder Gruppe)."""
    loaded = set()
    for step in steps:
        condition = step.get("if", "")
        if condition and f"matrix.gruppe == '{group}'" not in condition:
            continue
        run = step.get("run", "")
        loaded |= set(re.findall(r'--name "([^"]+)"', run))
        if "scripts/acceptance.py" in run and "--load" in run:
            loaded.add("Foerderband FB-01")
    return loaded


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


def test_retrieval_gate_prueft_jede_quelle_in_genau_einer_parallelen_gruppe():
    """Die Ingestion der Quellen (Embeddings auf der CPU) kostet rund 11 Minuten, deshalb laufen die Gruppen parallel.
    Keine Quelle darf dabei aus dem Gate fallen, und jede Gruppe laedt, was sie abfragt."""
    retrieval = _eval_jobs()["retrieval"]
    groups = {
        entry["gruppe"]: entry["quellen"].split(",")
        for entry in retrieval["strategy"]["matrix"]["include"]
    }
    asked = [source for sources in groups.values() for source in sources]
    assert len(groups) >= 3 and len(asked) == len(set(asked)) and set(asked) == GATE_SOURCES
    for group, sources in groups.items():
        assert set(sources) <= _loaded_sources(retrieval["steps"], group), group
    gate = next(s["run"] for s in retrieval["steps"] if "eval/run_retrieval.py" in s.get("run", ""))
    assert '--only "${{ matrix.quellen }}" --min 0.9 --min-sources 0.9' in gate


def test_retrieval_gate_nimmt_die_vektoren_unveraenderter_abschnitte_aus_dem_cache():
    """Der Cache ist nach Inhalt adressiert (app/embeddings.py, CachedEmbeddings). Aendern sich Embedding-Code,
    Abhaengigkeiten oder Modelle, darf trotzdem kein alter Stand zurueckkommen: Davon haengt der Teil des Schluessels
    ab, ueber den ein aelterer Cache wiederhergestellt wird."""
    retrieval = _eval_jobs()["retrieval"]
    cache_dir = retrieval["env"]["EMBEDDING_CACHE_DIR"]
    (cache,) = [
        step["with"]
        for step in retrieval["steps"]
        if step.get("uses", "").startswith("actions/cache@") and step["with"]["path"] == cache_dir
    ]
    key, restore = cache["key"], cache["restore-keys"]
    assert key.startswith(restore) and key != restore and "matrix.gruppe" in restore
    for part in ("backend/app/embeddings.py", "backend/pyproject.toml", "env.MODELLCACHE_VERSION"):
        assert part in restore, part
    hf_keys = [
        step["with"]["key"]
        for job in _eval_jobs().values()
        for step in job["steps"]
        if step.get("with", {}).get("path") == "/home/runner/.cache/huggingface"
    ]
    assert hf_keys and all("env.MODELLCACHE_VERSION" in hf_key for hf_key in hf_keys)


def test_ingest_gate_laeuft_ohne_datenbank_neben_dem_retrieval_gate():
    """Lesegenauigkeit braucht weder DB noch Backend; als eigener Job verlaengert sie keine Retrieval-Gruppe."""
    jobs = _eval_jobs()
    ingest = jobs["ingest"]
    assert "services" not in ingest and "needs" not in ingest and "needs" not in jobs["retrieval"]
    runs = "\n".join(step.get("run", "") for step in ingest["steps"])
    assert runs.count("eval/run_ingest.py") == 4  # FB-01, UR-01, PM1-AR, Voll-Scan mit OCR
    assert "eval/run_ingest.py" not in str(jobs["retrieval"])
