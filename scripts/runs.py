#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.7"
# dependencies = []
# ///
"""Inspect one or more MG run directories.

Modes:

  --run-dir <path>
      Single-run summary: xsec_pb, xsec_err_pb, nevents, seed, run_tag.
      Reads <run_dir>/*_banner.txt (always present, small) plus
      <run_dir>/inputs/run_manifest.yaml as fallback for xsec_err_pb
      (MG does not write MC error into the banner).

  --work-dir <path>
      Multi-run comparison: every <work_dir>/Events/run_* is read; the
      first (by sort order) is the baseline, each subsequent run gets a
      set-level diff against it (script.mg5 + model/process comparison).

  --work-dir <path> --runs run_01,run_02,run_03
      Restrict to a subset.

NEVER reads .lhe(.gz) event files. Output: compact JSON (valid YAML).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Banner regex — banner inlines run_card in "<value> = <key>" form, and has
# a top summary block where keys appear as "Key : value". Both variants covered.
XSEC_PB = re.compile(r"Integrated weight\s*\(pb\)\s*:\s*([0-9.eE+\-]+)")
XSEC_ERR_PB = re.compile(r"Integrated error\s*\(pb\)\s*:\s*([0-9.eE+\-]+)")
NEVENTS = re.compile(r"Number of Events\s*:\s*(\d+)|(\d+)\s*=\s*nevents\b")
SEED = re.compile(r"Seed\s*:\s*(\d+)|(\d+)\s*=\s*iseed\b")
RUN_TAG = re.compile(r"run_tag\s*:\s*(\S+)|(\S+)\s*=\s*run_tag\b")


def find_banner(run_dir):
    cands = sorted(run_dir.glob("*_banner.txt"))
    return cands[-1] if cands else None


def read_manifest(run_dir):
    """Return the parsed run_manifest.yaml dict if present, else {}."""
    mf = run_dir / "inputs" / "run_manifest.yaml"
    if not mf.is_file():
        return {}
    try:
        return json.loads(mf.read_text())
    except Exception:
        return {}


def _first_group(m):
    return next((g for g in m.groups() if g is not None), None)


def parse_banner(path):
    result = {}
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


def summarize_run(run_dir):
    """Return a dict for one run. banner + manifest fallback + script metadata."""
    summary = {"run": run_dir.name, "run_dir": str(run_dir)}

    banner = find_banner(run_dir)
    if banner is None:
        summary["banner_available"] = False
        return summary
    summary["banner_path"] = str(banner)
    summary.update(parse_banner(banner))

    manifest = read_manifest(run_dir)
    if "xsec_err_pb" not in summary:
        err = manifest.get("result", {}).get("xsec_err_pb")
        if err is not None:
            summary["xsec_err_pb"] = err
            summary["xsec_err_source"] = "run_manifest.yaml"
    if manifest:
        summary["duration_s"] = manifest.get("duration_s")

    # Archived script (if the run was driven by run_mg.py)
    script_path = run_dir / "inputs" / "script.mg5"
    if script_path.is_file():
        summary["script_archive"] = str(script_path)
        summary["_script_parsed"] = parse_script(script_path.read_text())
    return summary


def parse_script(text):
    """Extract model / process / set-key-value dict from a .mg5 script."""
    model = None
    process = None
    sets = {}
    for raw in text.splitlines():
        # strip trailing comment after '#'
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("import model "):
            model = line[len("import model "):].strip()
        elif line.startswith("generate ") and process is None:
            process = line[len("generate "):].strip()
        elif line.startswith("set "):
            parts = line[4:].split()
            if len(parts) >= 2:
                # All tokens except the last form the key path
                # (handles `set nevents 1000` and `set mass 6 172.5`).
                key = " ".join(parts[:-1])
                sets[key] = parts[-1]
    return {"model": model, "process": process, "sets": sets}


def compute_diff(baseline, other):
    """Diff two parsed scripts. Returns dict with model_changed, process_changed, set_diff."""
    diff = {}
    if baseline["model"] != other["model"]:
        diff["model_changed"] = {"from": baseline["model"], "to": other["model"]}
    if baseline["process"] != other["process"]:
        diff["process_changed"] = {"from": baseline["process"], "to": other["process"]}

    base_sets = baseline["sets"]
    other_sets = other["sets"]
    set_diff = {}
    all_keys = set(base_sets) | set(other_sets)
    for k in sorted(all_keys):
        bv = base_sets.get(k)
        ov = other_sets.get(k)
        if bv != ov:
            set_diff[k] = {"from": bv, "to": ov}
    if set_diff:
        diff["set_diff"] = set_diff
    return diff


def list_run_dirs(work_dir, subset):
    events = work_dir / "Events"
    if not events.is_dir():
        return []
    all_runs = sorted(p for p in events.iterdir() if p.is_dir() and p.name.startswith("run_"))
    if subset:
        wanted = set(subset)
        picked = [p for p in all_runs if p.name in wanted]
        missing = wanted - {p.name for p in picked}
        return picked, sorted(missing)
    return all_runs, []


def main():
    p = argparse.ArgumentParser(description="Inspect one MG run or compare several.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-dir", help="Path to a single Events/run_XX/")
    g.add_argument("--work-dir", help="Process directory; scans Events/run_*")
    p.add_argument("--runs", help="Comma-separated subset of run names (only with --work-dir)")
    args = p.parse_args()

    if args.run_dir:
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
        summary = summarize_run(run_dir)
        summary.pop("_script_parsed", None)  # internal, not for output
        output = {"status": "ok", **summary}
        print(json.dumps(output, indent=2))
        return 0

    # --work-dir mode
    work_dir = Path(args.work_dir).resolve()
    if not (work_dir / "Events").is_dir():
        print(json.dumps({"status": "error",
                          "reason": f"no Events/ under {work_dir}"}, indent=2))
        return 2

    subset = [s.strip() for s in args.runs.split(",")] if args.runs else []
    run_dirs, missing = list_run_dirs(work_dir, subset)
    if not run_dirs:
        print(json.dumps({
            "status": "error",
            "reason": "no run_* directories found" + (f"; requested subset {subset} not present" if subset else ""),
            "work_dir": str(work_dir),
        }, indent=2))
        return 2

    summaries = [summarize_run(rd) for rd in run_dirs]
    baseline = summaries[0]
    baseline_parsed = baseline.get("_script_parsed")

    runs_output = []
    for i, s in enumerate(summaries):
        entry = {k: v for k, v in s.items() if not k.startswith("_")}
        if i == 0:
            entry["baseline"] = True
        elif baseline_parsed and s.get("_script_parsed"):
            diff = compute_diff(baseline_parsed, s["_script_parsed"])
            if diff:
                entry.update(diff)
            else:
                entry["set_diff"] = {}  # explicitly empty → runs had identical scripts
        else:
            entry["script_diff_unavailable"] = "script.mg5 missing in one or both runs' inputs/"
        runs_output.append(entry)

    result = {
        "status": "ok",
        "work_dir": str(work_dir),
        "baseline": baseline["run"],
        "run_count": len(summaries),
        "runs": runs_output,
    }
    if missing:
        result["warnings"] = [f"requested run(s) not found: {', '.join(missing)}"]
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
