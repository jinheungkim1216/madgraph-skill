#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.7"
# dependencies = []
# ///
"""Generate Feynman diagrams as PDFs from an MG process.

Two modes:

  --script <path.mg5>   Run MG with a diagrams-only script (import / generate /
                        output — no launch needed), then convert every
                        matrix*.ps under the resulting SubProcesses/P*/ into PDFs.
                        Uses the `output <dir>` line to determine work_dir.

  --work-dir <path>     Skip MG; convert existing matrix*.ps files under
                        <work_dir>/SubProcesses/P*/ into PDFs. Use when the
                        process was already `output`-ed by a previous run.

PDFs are collected into a single folder `<work_dir>/diagrams/`, named
`<subprocess>__<matrix_name>.pdf` (e.g. `P1_gg_ttx__matrix3.pdf`). Originals
in `SubProcesses/P*/matrix*.ps` are left untouched.

Requires `ps2pdf` (ghostscript) or `gs` on PATH for conversion.
Output: compact JSON summary with per-subprocess PDF paths.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

SLOT_PATTERN = re.compile(r"<[A-Z_][A-Z0-9_]*>")
OUTPUT_PATTERN = re.compile(r"^\s*output\s+(?:madevent\s+)?(\S+)\s*$", re.MULTILINE)
ERROR_PATTERN = re.compile(r"(ERROR|FATAL|Traceback|Abort|command not recognized)", re.IGNORECASE)
MAX_ERROR_TAIL = 10
MAX_CONV_ERRORS_REPORTED = 10


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
        if value.startswith(('"', "'")):
            q = value[0]
            end = value.find(q, 1)
            if end >= 0:
                value = value[1:end]
        elif "#" in value:
            value = value.split("#", 1)[0].rstrip()
        if key and key not in os.environ:
            os.environ[key] = value
    return str(target.resolve())


def resolve_mg_root(cli_arg):
    """Return (Path|None, searched: list[str])."""
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


def extract_output_dir(script_text):
    matches = OUTPUT_PATTERN.findall(script_text)
    if not matches:
        return None
    return Path(matches[-1]).expanduser()


def run_mg(mg5_aMC, script, log_path, timeout):
    """Stream MG stdout/stderr to log_path. Return (returncode, errors_tail, line_count)."""
    errors_tail = []
    line_count = 0
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with log_path.open("w", buffering=1) as log:
        proc = subprocess.Popen(
            [str(mg5_aMC), str(script)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=os.environ,
        )
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                log.write(line)
                line_count += 1
                if ERROR_PATTERN.search(line):
                    errors_tail.append(line.rstrip())
                    if len(errors_tail) > MAX_ERROR_TAIL:
                        errors_tail.pop(0)
                if timeout is not None and (time.monotonic() - start) > timeout:
                    proc.send_signal(signal.SIGTERM)
                    time.sleep(5)
                    if proc.poll() is None:
                        proc.kill()
                    break
        except KeyboardInterrupt:
            proc.send_signal(signal.SIGTERM)
            raise
        proc.wait()
    return proc.returncode, errors_tail, line_count


def find_subprocess_ps(work_dir):
    """Return [(p_dir, [ps_files_sorted]), ...] for every SubProcesses/P*/ with matrix*.ps."""
    sp = work_dir / "SubProcesses"
    if not sp.is_dir():
        return []
    results = []
    for p_dir in sorted(sp.iterdir()):
        if not p_dir.is_dir() or not p_dir.name.startswith("P"):
            continue
        ps_files = sorted(p_dir.glob("matrix*.ps"))
        if ps_files:
            results.append((p_dir, ps_files))
    return results


def convert_ps_to_pdf(ps, out_pdf):
    """Convert .ps to out_pdf. Return (pdf_path_or_None, error_or_None). Prefers ps2pdf, falls back to gs."""
    for cmd in (
        ["ps2pdf", str(ps), str(out_pdf)],
        ["gs", "-dNOPAUSE", "-dBATCH", "-dQUIET",
         "-sDEVICE=pdfwrite", f"-sOutputFile={out_pdf}", str(ps)],
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            continue
        if r.returncode == 0 and out_pdf.is_file():
            return out_pdf, None
        err_tail = (r.stderr or r.stdout).strip().splitlines()[-1:] if (r.stderr or r.stdout) else ["exit code %d" % r.returncode]
        return None, err_tail[0][:200]
    return None, "neither ps2pdf nor gs on PATH — install ghostscript"


def emit(data):
    print(json.dumps(data, indent=2))


def main():
    p = argparse.ArgumentParser(description="Generate Feynman-diagram PDFs from MG output.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--script", help="Path to .mg5 script with generate+output (no launch needed)")
    g.add_argument("--work-dir", help="Existing MG output dir (skip MG, just convert existing PS files)")
    p.add_argument("--mg-root", help="Explicit MG root (overrides $MG5_HOME etc.)")
    p.add_argument("--timeout", type=int, default=None, help="Seconds before killing MG (script mode only)")
    args = p.parse_args()

    env_file_loaded = load_env_file()
    mg_info: dict = {}

    if args.script:
        script = Path(args.script).resolve()
        if not script.is_file():
            emit({"status": "error", "reason": f"script not found: {script}"})
            return 2
        text = script.read_text()
        slots = SLOT_PATTERN.findall(text)
        if slots:
            emit({"status": "error", "reason": "unsubstituted placeholders in script",
                  "slots": sorted(set(slots))})
            return 2
        work_dir = extract_output_dir(text)
        if work_dir is None:
            emit({"status": "error", "reason": "script has no `output <dir>` line"})
            return 2
        work_dir = work_dir.resolve()

        mg_root, searched = resolve_mg_root(args.mg_root)
        if mg_root is None:
            remedies = [
                "Install MG (if missing): see skills/madgraph/references/install.md",
                "If already installed: export MG5_HOME=/abs/path/to/MG5_aMC_v3_5_xx",
                "Or pass --mg-root /abs/path to make_diagrams.py explicitly",
            ]
            if env_file_loaded is None:
                remedies.append("Or create ./.env with: MG5_HOME=/abs/path")
            emit({
                "status": "error",
                "reason": "MG not found",
                "env_file_loaded": env_file_loaded,
                "searched": searched,
                "remedies": remedies,
            })
            return 2

        work_dir.mkdir(parents=True, exist_ok=True)
        log_path = work_dir / "mg_diagrams.log"
        mg_rc, mg_errors_tail, mg_line_count = run_mg(
            mg_root / "bin" / "mg5_aMC", script, log_path, args.timeout,
        )
        if mg_rc != 0 or not (work_dir / "SubProcesses").is_dir():
            emit({
                "status": "error",
                "reason": "MG run failed or produced no SubProcesses/",
                "work_dir": str(work_dir),
                "mg_returncode": mg_rc,
                "log_path": str(log_path),
                "log_size_lines": mg_line_count,
                "errors_tail": mg_errors_tail,
            })
            return 1
        mg_info = {
            "log_path": str(log_path),
            "log_size_lines": mg_line_count,
            "mg_returncode": mg_rc,
            "errors_tail": mg_errors_tail,
        }
    else:
        work_dir = Path(args.work_dir).resolve()
        if not (work_dir / "SubProcesses").is_dir():
            emit({"status": "error",
                  "reason": f"no SubProcesses/ under {work_dir} — did you `output` there?"})
            return 2

    # Find all matrix*.ps and convert
    t0 = time.monotonic()
    per_subproc = find_subprocess_ps(work_dir)
    if not per_subproc:
        emit({
            "status": "error",
            "reason": "no matrix*.ps files found under SubProcesses/P*/",
            "work_dir": str(work_dir),
            **mg_info,
        })
        return 1

    diagrams_dir = work_dir / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)

    subprocesses = []
    converted = failed = 0
    conv_errors = []
    for p_dir, ps_files in per_subproc:
        diagrams = []
        for ps in ps_files:
            out_pdf = diagrams_dir / f"{p_dir.name}__{ps.stem}.pdf"
            pdf, err = convert_ps_to_pdf(ps, out_pdf)
            if pdf is not None:
                diagrams.append({"ps": ps.name, "pdf": pdf.name})
                converted += 1
            else:
                failed += 1
                if len(conv_errors) < MAX_CONV_ERRORS_REPORTED:
                    conv_errors.append({"ps": str(ps), "error": err})
        subprocesses.append({
            "name": p_dir.name,
            "source_dir": str(p_dir),
            "ps_count": len(ps_files),
            "pdf_count": len(diagrams),
            "diagrams": diagrams,
        })
    duration = round(time.monotonic() - t0, 1)

    status = "ok" if failed == 0 else "partial"
    summary = {
        "status": status,
        "work_dir": str(work_dir),
        "diagrams_dir": str(diagrams_dir),
        "subprocess_count": len(per_subproc),
        "ps_total": converted + failed,
        "pdf_total": converted,
        "failed_count": failed,
        "conversion_duration_s": duration,
        "subprocesses": subprocesses,
        **mg_info,
    }
    if conv_errors:
        summary["conversion_errors"] = conv_errors
    emit(summary)
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
