#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.7"
# dependencies = []
# ///
"""Detect MadGraph install — locate binary, report version + toolchain + extensions.

Resolution order (first hit wins):
  1. --mg-root <path>
  2. $MG5_HOME
  3. `which mg5_aMC`
  4. glob ./MG5_aMC*/bin/mg5_aMC  (current working dir — project-local installs)
  5. glob ~/MG5_aMC*/bin/mg5_aMC, /opt/MG5_aMC*/bin/mg5_aMC

Output: compact JSON (valid YAML) to stdout. Never runs MG, never floods the terminal.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def resolve_mg_root(cli_arg: str | None) -> Path | None:
    candidates: list[Path] = []
    if cli_arg:
        candidates.append(Path(cli_arg))
    env = os.environ.get("MG5_HOME")
    if env:
        candidates.append(Path(env))
    which = shutil.which("mg5_aMC")
    if which:
        candidates.append(Path(which).resolve().parent.parent)
    for pattern in (
        str(Path.cwd() / "MG5_aMC*/bin/mg5_aMC"),
        str(Path.home() / "MG5_aMC*/bin/mg5_aMC"),
        "/opt/MG5_aMC*/bin/mg5_aMC",
    ):
        for hit in glob.glob(pattern):
            candidates.append(Path(hit).parent.parent)
    for c in candidates:
        if (c / "bin" / "mg5_aMC").is_file():
            return c.resolve()
    return None


def read_version(mg_root: Path) -> str | None:
    vfile = mg_root / "VERSION"
    if not vfile.is_file():
        return None
    for line in vfile.read_text().splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip()
    return None


def check_cmd(cmd: str, version_flag: str = "--version") -> dict[str, str | None]:
    path = shutil.which(cmd)
    if not path:
        return {"path": None, "version": None}
    try:
        out = subprocess.run(
            [cmd, version_flag],
            capture_output=True, text=True, timeout=5,
        )
        text = out.stdout or out.stderr
        first = text.splitlines()[0].strip() if text else None
    except Exception:
        first = None
    return {"path": path, "version": first}


def check_python_module(module: str) -> dict[str, str | None]:
    """Check whether a module is importable from the system python3 (the one MG will use)."""
    python3 = shutil.which("python3")
    if not python3:
        return {"available": "unknown", "version": None, "reason": "python3 not on PATH"}
    try:
        out = subprocess.run(
            [python3, "-c", f"import {module}; print(getattr({module}, '__version__', 'unknown'))"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return {"available": "yes", "version": out.stdout.strip()}
        return {"available": "no", "version": None, "reason": out.stderr.strip().splitlines()[-1] if out.stderr else "import failed"}
    except Exception as e:
        return {"available": "unknown", "version": None, "reason": str(e)}


def extension_status(mg_root: Path) -> dict[str, str]:
    hep = mg_root / "HEPTools"
    return {
        "pythia8": "installed" if (hep / "pythia8").is_dir() else "missing",
        "lhapdf6": "installed" if (hep / "lhapdf6").is_dir() else "missing",
        "delphes": "installed" if (hep / "Delphes").is_dir() or (hep / "delphes").is_dir() else "missing",
        "madanalysis5": "installed" if (hep / "madanalysis5").is_dir() else "missing",
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Detect MadGraph install.")
    p.add_argument("--mg-root", help="Explicit path to MG root (overrides $MG5_HOME etc.)")
    args = p.parse_args()

    mg_root = resolve_mg_root(args.mg_root)
    if mg_root is None:
        print(json.dumps({
            "status": "not_found",
            "note": "MG not resolved via --mg-root, $MG5_HOME, $PATH, or standard globs. See references/install.md.",
        }, indent=2))
        return 1

    python_six = check_python_module("six")
    result: dict[str, Any] = {
        "status": "ok",
        "mg_root": str(mg_root),
        "mg5_aMC": str(mg_root / "bin" / "mg5_aMC"),
        "version": read_version(mg_root),
        "python": check_cmd("python3"),
        "python_six": python_six,
        "gfortran": check_cmd("gfortran", "--version"),
        "extensions": extension_status(mg_root),
    }
    if python_six.get("available") == "no":
        result["warnings"] = [
            "Python module 'six' missing — MG will refuse to start. Install with `python3 -m pip install --user six`.",
        ]
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
