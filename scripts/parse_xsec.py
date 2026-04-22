#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.7"
# dependencies = []
# ///
"""Read cross section + event count from a completed MG run directory.

Primary source: `<run_dir>/*_banner.txt` — always present, small (tens of KB).
Banner has central xsec value and config, but MG does NOT write the MC error
to the banner. If the run was driven by scripts/run_mg.py, the error value
is available in `<run_dir>/inputs/run_manifest.yaml` — read as fallback.

NEVER reads `.lhe(.gz)` event files.
Output: compact JSON (valid YAML) summary.

Usage: parse_xsec.py --run-dir <work_dir>/Events/run_XX
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

XSEC_PB = re.compile(r"Integrated weight\s*\(pb\)\s*:\s*([0-9.eE+\-]+)")
XSEC_ERR_PB = re.compile(r"Integrated error\s*\(pb\)\s*:\s*([0-9.eE+\-]+)")
NEVENTS = re.compile(r"Number of Events\s*:\s*(\d+)|(\d+)\s*=\s*nevents\b")
# Banner inlines run_card: "<value>  = <key> ! comment".
SEED = re.compile(r"Seed\s*:\s*(\d+)|(\d+)\s*=\s*iseed\b")
RUN_TAG = re.compile(r"run_tag\s*:\s*(\S+)|(\S+)\s*=\s*run_tag\b")


def find_banner(run_dir: Path) -> Path | None:
    cands = sorted(run_dir.glob("*_banner.txt"))
    return cands[-1] if cands else None


def read_manifest_xsec_err(run_dir: Path) -> float | None:
    """Return xsec_err_pb from run_manifest.yaml if the run was driven by run_mg.py."""
    mf = run_dir / "inputs" / "run_manifest.yaml"
    if not mf.is_file():
        return None
    try:
        data = json.loads(mf.read_text())
    except Exception:
        return None
    return data.get("result", {}).get("xsec_err_pb")


def _first_group(m: "re.Match[str]") -> str | None:
    return next((g for g in m.groups() if g is not None), None)


def parse_banner(path: Path) -> dict:
    result: dict = {}
    text = path.read_text()
    for pat, key, cast in (
        (XSEC_PB, "xsec_pb", float),
        (XSEC_ERR_PB, "xsec_err_pb", float),
        (NEVENTS, "nevents", int),
        (SEED, "seed", int),
        (RUN_TAG, "run_tag", str),
    ):
        m = pat.search(text)
        if m:
            v = _first_group(m)
            if v is not None:
                result[key] = cast(v)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Extract xsec + event count from MG run dir.")
    p.add_argument("--run-dir", required=True, help="Path to Events/run_XX/")
    args = p.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        print(json.dumps({"status": "error", "reason": f"not a directory: {run_dir}"}, indent=2))
        return 2

    banner = find_banner(run_dir)
    if banner is None:
        print(json.dumps({
            "status": "error",
            "reason": "no *_banner.txt in run_dir — run may have failed before banner was written",
            "run_dir": str(run_dir),
        }, indent=2))
        return 2

    parsed = parse_banner(banner)
    if "xsec_err_pb" not in parsed:
        err = read_manifest_xsec_err(run_dir)
        if err is not None:
            parsed["xsec_err_pb"] = err
            parsed["xsec_err_source"] = "run_manifest.yaml"
    output = {
        "status": "ok",
        "run_dir": str(run_dir),
        "banner_path": str(banner),
        **parsed,
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
