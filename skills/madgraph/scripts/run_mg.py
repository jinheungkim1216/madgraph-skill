#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.7"
# dependencies = []
# ///
"""Non-interactive MadGraph 5 driver.

Runs `$MG5_HOME/bin/mg5_aMC <script>` with all stdout/stderr redirected to a log file
on disk, and emits a compact JSON/YAML summary (status, xsec, err, nevents, run_dir,
script_archive, log_path, errors_tail, …) to stdout. Never floods the terminal with
MG output, even on failure.

Work dir is derived from the script itself — the path on the last `launch <dir>`
line. `output madevent <dir>` (if present) must use the same path. The log and
the archive live under that directory; no --work-dir CLI flag.

Slot guard: refuses to run scripts that still contain unsubstituted <PLACEHOLDERS>.
Archive: copies the script to <run_dir>/inputs/script.mg5 + writes run_manifest.yaml.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SLOT_PATTERN = re.compile(r"<[A-Z_][A-Z0-9_]*>")
LAUNCH_PATTERN = re.compile(r"^\s*launch\s+(\S+)\s*$", re.MULTILINE)
OUTPUT_PATTERN = re.compile(r"^\s*output\s+(?:madevent\s+)?(\S+)\s*$", re.MULTILINE)

# MG final-result line. Variants seen in 3.5.x:
#   "Cross-section :   5.073e+02 +- 0.8 pb"
#   "Cross-section :   5.073e+02 +/- 0.8 pb"
XSEC_PATTERN = re.compile(
    r"Cross-section\s*:\s*"
    r"([0-9]+\.?[0-9]*(?:[eE][+-]?[0-9]+)?)"
    r"\s*(?:\+-|\+/-|±)\s*"
    r"([0-9]+\.?[0-9]*(?:[eE][+-]?[0-9]+)?)"
    r"\s*(pb|fb|nb)?"
)
NEVENTS_PATTERN = re.compile(r"Stored\s+(\d+)\s+events")
RUN_DIR_PATTERN = re.compile(r"Events/(run_\d+)")
ERROR_PATTERN = re.compile(r"(ERROR|FATAL|Traceback|Abort|command not recognized)", re.IGNORECASE)
WARNING_PATTERN = re.compile(r"\bWARNING\b")

# Banner fallback — authoritative source for nevents / run_tag / seed.
BANNER_XSEC_PB = re.compile(r"Integrated weight\s*\(pb\)\s*:\s*([0-9.eE+\-]+)")
BANNER_XSEC_ERR_PB = re.compile(r"Integrated error\s*\(pb\)\s*:\s*([0-9.eE+\-]+)")
BANNER_NEVENTS = re.compile(r"Number of Events\s*:\s*(\d+)|(\d+)\s*=\s*nevents\b")
# Banner inlines run_card with filled-in template: "<value>  = <key> ! comment".
BANNER_SEED = re.compile(r"Seed\s*:\s*(\d+)|(\d+)\s*=\s*iseed\b")
BANNER_RUN_TAG = re.compile(r"run_tag\s*:\s*(\S+)|(\S+)\s*=\s*run_tag\b")

# NLO: xsec lives in Events/run_XX/summary.txt, not in banner.
NLO_SUMMARY_XSEC = re.compile(
    r"Total cross section:\s*"
    r"([0-9.eE+\-]+)\s*\+-\s*([0-9.eE+\-]+)\s*(pb|fb|nb)?",
    re.IGNORECASE,
)

MAX_ERROR_TAIL = 10


def resolve_mg_root(cli_arg: str | None) -> Path | None:
    import glob

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


def check_slots(script_text: str) -> list[str]:
    return SLOT_PATTERN.findall(script_text)


def extract_work_dir(script_text: str) -> tuple[Path | None, list[str]]:
    """Derive work dir from script. Returns (path, warnings)."""
    warnings: list[str] = []
    launch_paths = LAUNCH_PATTERN.findall(script_text)
    output_paths = OUTPUT_PATTERN.findall(script_text)
    if not launch_paths:
        return None, ["script has no `launch <dir>` line — nothing to run"]
    work_dir = Path(launch_paths[-1]).expanduser()
    if output_paths:
        out = Path(output_paths[-1]).expanduser()
        if out.resolve() != work_dir.resolve():
            warnings.append(
                f"script's `output {out}` differs from `launch {work_dir}` — using launch path"
            )
    return work_dir, warnings


def pick_latest_run_dir(work_dir: Path) -> Path | None:
    events = work_dir / "Events"
    if not events.is_dir():
        return None
    runs = sorted(
        (p for p in events.iterdir() if p.is_dir() and p.name.startswith("run_")),
        key=lambda p: p.stat().st_mtime,
    )
    return runs[-1] if runs else None


def snapshot_run_names(work_dir: Path) -> set[str]:
    """Return the set of run_* directory names currently under work_dir/Events/."""
    events = work_dir / "Events"
    if not events.is_dir():
        return set()
    return {p.name for p in events.iterdir() if p.is_dir() and p.name.startswith("run_")}


def list_new_runs(work_dir: Path, before: set[str]) -> list[Path]:
    """Return new run_XX directories created since `before` snapshot, sorted by name."""
    events = work_dir / "Events"
    if not events.is_dir():
        return []
    new_names = sorted(
        p.name for p in events.iterdir()
        if p.is_dir() and p.name.startswith("run_") and p.name not in before
    )
    return [events / name for name in new_names]


def parse_banner(run_dir: Path) -> dict:
    """Read *_banner.txt (LO xsec + run metadata). For NLO runs, xsec lives
    in Events/run_XX/summary.txt — override xsec/err from there when present."""
    out: dict = {}
    cands = sorted(run_dir.glob("*_banner.txt"))
    if cands:
        text = cands[-1].read_text()
        for pat, key, cast in (
            (BANNER_XSEC_PB, "xsec_pb", float),
            (BANNER_XSEC_ERR_PB, "xsec_err_pb", float),
            (BANNER_NEVENTS, "nevents", int),
            (BANNER_SEED, "seed", int),
            (BANNER_RUN_TAG, "run_tag", str),
        ):
            m = pat.search(text)
            if m:
                value = next((g for g in m.groups() if g is not None), None)
                if value is not None:
                    out[key] = cast(value)
    summary = run_dir / "summary.txt"
    if summary.is_file():
        m = NLO_SUMMARY_XSEC.search(summary.read_text())
        if m:
            unit = (m.group(3) or "pb").lower()
            factor = {"pb": 1.0, "fb": 1e-3, "nb": 1e3}.get(unit, 1.0)
            out["xsec_pb"] = float(m.group(1)) * factor
            out["xsec_err_pb"] = float(m.group(2)) * factor
            out["order"] = "NLO"
    return out


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_script(run_dir: Path, source_script: Path) -> Path:
    inputs = run_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    dest = inputs / "script.mg5"
    shutil.copy2(source_script, dest)
    return dest


def write_manifest(run_dir: Path, manifest: dict) -> Path:
    path = run_dir / "inputs" / "run_manifest.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def run(
    mg5_aMC: Path,
    script: Path,
    log_path: Path,
    timeout: int | None,
) -> tuple[int, list[str], int, dict, int]:
    """Return (returncode, errors_tail, line_count, parsed_results, warnings_count)."""
    errors_tail: list[str] = []
    warnings_count = 0
    line_count = 0
    parsed: dict = {}

    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()

    with log_path.open("w", buffering=1) as log:
        proc = subprocess.Popen(
            [str(mg5_aMC), str(script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=os.environ,
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
                if WARNING_PATTERN.search(line):
                    warnings_count += 1
                m_xsec = XSEC_PATTERN.search(line)
                if m_xsec:
                    unit = m_xsec.group(3) or "pb"
                    parsed["xsec_pb"] = _to_pb(float(m_xsec.group(1)), unit)
                    parsed["xsec_err_pb"] = _to_pb(float(m_xsec.group(2)), unit)
                m_nev = NEVENTS_PATTERN.search(line)
                if m_nev:
                    parsed["nevents"] = int(m_nev.group(1))
                m_run = RUN_DIR_PATTERN.search(line)
                if m_run:
                    parsed["run_tag"] = m_run.group(1)
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

    return proc.returncode, errors_tail, line_count, parsed, warnings_count


def _to_pb(value: float, unit: str) -> float:
    factor = {"pb": 1.0, "fb": 1e-3, "nb": 1e3}.get(unit.lower(), 1.0)
    return value * factor


def emit(data: dict) -> None:
    print(json.dumps(data, indent=2))


def main() -> int:
    p = argparse.ArgumentParser(description="Non-interactive MadGraph driver.")
    p.add_argument("--script", required=True, help="Path to .mg5 script")
    p.add_argument("--timeout", type=int, default=None, help="Max seconds before killing MG")
    p.add_argument("--mg-root", help="Explicit MG root (overrides $MG5_HOME etc.)")
    args = p.parse_args()

    script = Path(args.script).resolve()

    if not script.is_file():
        emit({"status": "error", "reason": f"script not found: {script}"})
        return 2

    script_text = script.read_text()
    slots = check_slots(script_text)
    if slots:
        emit({
            "status": "error",
            "reason": "unsubstituted placeholders in script — fill every <SLOT> before running",
            "slots": sorted(set(slots)),
        })
        return 2

    work_dir, wd_warnings = extract_work_dir(script_text)
    if work_dir is None:
        emit({"status": "error", "reason": wd_warnings[0]})
        return 2
    work_dir = work_dir.resolve()

    mg_root = resolve_mg_root(args.mg_root)
    if mg_root is None:
        emit({"status": "error", "reason": "MG not found. Set $MG5_HOME or pass --mg-root. See references/install.md."})
        return 2

    mg5_aMC = mg_root / "bin" / "mg5_aMC"
    work_dir.mkdir(parents=True, exist_ok=True)

    pre_runs = snapshot_run_names(work_dir)
    log_path = work_dir / "mg_run.log"
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.monotonic()
    try:
        rc, errors_tail, line_count, parsed, warnings = run(mg5_aMC, script, log_path, args.timeout)
    except KeyboardInterrupt:
        emit({"status": "interrupted", "log_path": str(log_path), "log_size_lines": 0})
        return 130
    duration_s = round(time.monotonic() - t0, 1)

    new_runs = list_new_runs(work_dir, pre_runs)

    if len(new_runs) > 1:
        # MG native scan (scan:[...] in script) produced multiple runs in one invocation.
        # Archive the script to each new run's inputs/ but skip the per-run manifest
        # (per-run xsec/err can't be attributed from a single stdout parse).
        archive_paths = [archive_script(nr, script) for nr in new_runs]
        status = "ok" if rc == 0 else ("timeout" if rc < 0 else "error")
        multi_summary = {
            "status": status,
            "mode": "multi_run_scan",
            "work_dir": str(work_dir),
            "created_runs": [nr.name for nr in new_runs],
            "run_count": len(new_runs),
            "script_archives": [str(p) for p in archive_paths],
            "log_path": str(log_path),
            "log_size_lines": line_count,
            "duration_s": duration_s,
            "mg_returncode": rc,
            "warnings_count": warnings,
            "errors_tail": errors_tail,
            "note": "Multiple runs created in one MG invocation (likely `scan:[...]`). "
                    "Per-run xsec, nevents, etc. available via `scripts/runs.py --work-dir "
                    f"{work_dir} --diff-vs baseline`.",
        }
        if wd_warnings:
            multi_summary["wrapper_warnings"] = wd_warnings
        emit(multi_summary)
        return 0 if status == "ok" else 1

    # Single-run path (the common case)
    run_dir = new_runs[0] if new_runs else None
    if run_dir is not None:
        archive_path = archive_script(run_dir, script)
        # Banner is authoritative — backfill anything stdout regex missed.
        for k, v in parse_banner(run_dir).items():
            parsed.setdefault(k, v)
    else:
        failed_dir = work_dir / "failed_runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        failed_dir.mkdir(parents=True, exist_ok=True)
        archive_path = failed_dir / "script.mg5"
        shutil.copy2(script, archive_path)

    status = "ok" if rc == 0 and (run_dir is not None) else ("timeout" if rc < 0 else "error")

    summary: dict = {
        "status": status,
        "xsec_pb": parsed.get("xsec_pb"),
        "xsec_err_pb": parsed.get("xsec_err_pb"),
        "nevents": parsed.get("nevents"),
        "run_tag": parsed.get("run_tag"),
        "seed": parsed.get("seed"),
        "work_dir": str(work_dir),
        "run_dir": str(run_dir) if run_dir else None,
        "script_archive": str(archive_path),
        "log_path": str(log_path),
        "log_size_lines": line_count,
        "duration_s": duration_s,
        "mg_returncode": rc,
        "warnings_count": warnings,
        "errors_tail": errors_tail,
    }
    if wd_warnings:
        summary["wrapper_warnings"] = wd_warnings

    if run_dir is not None:
        manifest = {
            "started_at": started_at,
            "duration_s": duration_s,
            "mg_root": str(mg_root),
            "source_script": {"path": str(script), "sha256": sha256_of(script)},
            "script_archive": str(archive_path),
            "log_path": str(log_path),
            "cli": {"timeout": args.timeout},
            "work_dir": str(work_dir),
            "result": {
                "status": status,
                "xsec_pb": parsed.get("xsec_pb"),
                "xsec_err_pb": parsed.get("xsec_err_pb"),
                "nevents": parsed.get("nevents"),
                "mg_returncode": rc,
            },
        }
        summary["manifest_path"] = str(write_manifest(run_dir, manifest))

    emit(summary)
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
