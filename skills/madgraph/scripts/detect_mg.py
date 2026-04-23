#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.7"
# dependencies = []
# ///
"""Detect MadGraph install — locate binary, report version + toolchain + extensions.

Resolution order (first hit wins):
  0. ./.env file is loaded first (does NOT override already-set shell env vars)
  1. --mg-root <path>              (strict: fails loudly if invalid)
  2. $MG5_HOME
  3. `which mg5_aMC`
  4. glob ./MG5_aMC*/bin/mg5_aMC   (CWD — project-local installs)
  5. glob ~/MG5_aMC*/bin/mg5_aMC, /opt/MG5_aMC*/bin/mg5_aMC

Output: compact JSON (valid YAML). Never runs MG, never floods the terminal.
On "not_found", output includes a `searched` list showing every strategy
tried, plus `remedies` with copy-pasteable commands.
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


def load_env_file(path=None):
    """Load KEY=VALUE lines from ./.env (or given path). Shell env wins —
    never overwrites an existing variable. Returns absolute loaded path, or None."""
    target = Path(path) if path else Path.cwd() / ".env"
    if not target.is_file():
        return None
    for raw in target.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
    return str(target.resolve())


def resolve_mg_root(cli_arg):
    """Return (Path|None, searched: list[str]).
    --mg-root is strict — an invalid explicit path fails, does NOT fall through."""
    searched = []

    if cli_arg:
        p = Path(cli_arg)
        if (p / "bin" / "mg5_aMC").is_file():
            searched.append(f"--mg-root {cli_arg}: OK")
            return p.resolve(), searched
        searched.append(f"--mg-root {cli_arg}: bin/mg5_aMC not found (strict)")
        return None, searched
    searched.append("--mg-root: (not provided)")

    env = os.environ.get("MG5_HOME")
    if env:
        p = Path(env)
        if (p / "bin" / "mg5_aMC").is_file():
            searched.append(f"$MG5_HOME={env}: OK")
            return p.resolve(), searched
        searched.append(f"$MG5_HOME={env}: bin/mg5_aMC not found")
    else:
        searched.append("$MG5_HOME: (unset)")

    which = shutil.which("mg5_aMC")
    if which:
        p = Path(which).resolve().parent.parent
        if (p / "bin" / "mg5_aMC").is_file():
            searched.append(f"PATH: {which} -> OK")
            return p.resolve(), searched
        searched.append(f"PATH: {which} -> parent layout mismatch")
    else:
        searched.append("PATH: mg5_aMC not on $PATH")

    for label, pattern in (
        ("CWD glob", str(Path.cwd() / "MG5_aMC*/bin/mg5_aMC")),
        ("~ glob", str(Path.home() / "MG5_aMC*/bin/mg5_aMC")),
        ("/opt glob", "/opt/MG5_aMC*/bin/mg5_aMC"),
    ):
        hits = glob.glob(pattern)
        if hits:
            p = Path(hits[0]).parent.parent
            searched.append(f"{label} {pattern}: {hits[0]}")
            return p.resolve(), searched
        searched.append(f"{label} {pattern}: no match")

    return None, searched


def not_found_remedies(env_file_loaded):
    remedies = [
        "Install MG (if missing): see skills/madgraph/references/install.md",
        "If already installed, set the env var: export MG5_HOME=/abs/path/to/MG5_aMC_v3_5_xx",
        "Or pass --mg-root explicitly: scripts/detect_mg.py --mg-root /abs/path",
    ]
    if env_file_loaded is None:
        remedies.append("Or create ./.env in your project with: MG5_HOME=/abs/path")
    return remedies


def read_version(mg_root: Path):
    vfile = mg_root / "VERSION"
    if not vfile.is_file():
        return None
    for line in vfile.read_text().splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip()
    return None


def check_cmd(cmd, version_flag="--version"):
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


def check_python_module(module):
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


def extension_status(mg_root):
    hep = mg_root / "HEPTools"
    return {
        "pythia8": "installed" if (hep / "pythia8").is_dir() else "missing",
        "lhapdf6": "installed" if (hep / "lhapdf6").is_dir() else "missing",
        "delphes": "installed" if (hep / "Delphes").is_dir() or (hep / "delphes").is_dir() else "missing",
        "madanalysis5": "installed" if (hep / "madanalysis5").is_dir() else "missing",
    }


def main():
    p = argparse.ArgumentParser(description="Detect MadGraph install.")
    p.add_argument("--mg-root", help="Explicit path to MG root (overrides $MG5_HOME etc.)")
    args = p.parse_args()

    env_file_loaded = load_env_file()
    mg_root, searched = resolve_mg_root(args.mg_root)

    if mg_root is None:
        print(json.dumps({
            "status": "not_found",
            "env_file_loaded": env_file_loaded,
            "searched": searched,
            "remedies": not_found_remedies(env_file_loaded),
        }, indent=2))
        return 1

    python_six = check_python_module("six")
    result: dict[str, Any] = {
        "status": "ok",
        "mg_root": str(mg_root),
        "mg5_aMC": str(mg_root / "bin" / "mg5_aMC"),
        "version": read_version(mg_root),
        "env_file_loaded": env_file_loaded,
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
