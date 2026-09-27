"""Alle Pruefungen lokal, wie sie die CI ausfuehren wuerde (kostenlos, ca. 1 Minute).

Aufruf:  python scripts/check.py [--backend | --frontend] [--install-hook]

  --backend        nur ruff + pytest
  --frontend       nur eslint + tsc + vitest
  --install-hook   schreibt .git/hooks/pre-push, der diesen Check vor jedem Push ausfuehrt

Bricht beim ersten Fehler ab und zeigt am Ende, was gruen war. Nutzt den Python-Interpreter,
mit dem das Skript gestartet wurde (unter Windows: backend/.venv/Scripts/python scripts/check.py).
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend"
NPM = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
NPX = shutil.which("npx.cmd") or shutil.which("npx") or "npx"

BACKEND_STEPS = [
    ("ruff", [sys.executable, "-m", "ruff", "check", "backend", "scripts", "eval"], REPO),
    ("pytest", [sys.executable, "-m", "pytest", "-q"], BACKEND),
]
FRONTEND_STEPS = [
    ("eslint", [NPM, "run", "lint", "--silent"], FRONTEND),
    ("next typegen", [NPX, "next", "typegen"], FRONTEND),
    ("tsc", [NPX, "tsc", "--noEmit"], FRONTEND),
    ("vitest", [NPM, "test", "--silent"], FRONTEND),
]

HOOK = """#!/bin/sh
# Von scripts/check.py --install-hook angelegt: Pruefungen vor jedem Push.
exec "{python}" "{script}"
"""


def run(name: str, command: list[str], cwd: Path) -> bool:
    started = time.monotonic()
    print(f"\n=== {name} ({cwd.relative_to(REPO) or '.'}) ===", flush=True)
    result = subprocess.run(command, cwd=cwd)
    seconds = time.monotonic() - started
    status = "ok" if result.returncode == 0 else f"FEHLER (Exit {result.returncode})"
    print(f"--- {name}: {status}, {seconds:.0f} s", flush=True)
    return result.returncode == 0


def install_hook() -> int:
    hooks = REPO / ".git" / "hooks"
    if not hooks.is_dir():
        print("Kein .git/hooks-Ordner gefunden; im Repo-Wurzelverzeichnis ausfuehren.")
        return 1
    target = hooks / "pre-push"
    target.write_text(HOOK.format(python=Path(sys.executable).as_posix(), script=Path(__file__).as_posix()))
    target.chmod(target.stat().st_mode | 0o111)
    print(f"Hook angelegt: {target}\nEntfernen: Datei loeschen oder git push --no-verify.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", action="store_true", help="nur Backend-Pruefungen")
    parser.add_argument("--frontend", action="store_true", help="nur Frontend-Pruefungen")
    parser.add_argument("--install-hook", action="store_true", help="pre-push-Hook anlegen")
    args = parser.parse_args()
    if args.install_hook:
        return install_hook()

    steps = []
    if args.backend or not args.frontend:
        steps += BACKEND_STEPS
    if args.frontend or not args.backend:
        if not (FRONTEND / "node_modules").is_dir():
            print("frontend/node_modules fehlt: cd frontend && npm install")
            return 1
        steps += FRONTEND_STEPS

    os.environ.setdefault("PYTHONUTF8", "1")
    passed: list[str] = []
    for name, command, cwd in steps:
        if not run(name, command, cwd):
            print(f"\nAbbruch bei {name}. Gruen bis dahin: {', '.join(passed) or 'nichts'}")
            return 1
        passed.append(name)
    print(f"\nAlles gruen: {', '.join(passed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
