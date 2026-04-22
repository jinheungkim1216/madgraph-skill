---
name: madgraph
description: Use when the user works with MadGraph (MG5_aMC@NLO) — writing or editing MG5 scripts (`.mg5`), generating Feynman diagrams, running LO event generation, or extracting a cross section from a completed MG run. Trigger keywords include "MadGraph", "mg5_aMC", "MG5_aMC@NLO", ".mg5 script", "proc_card.dat", "run_card.dat", "param_card.dat", "generate p p >", "import model", or requests to produce `.lhe` events for collider physics processes.
---

# MadGraph (MG5_aMC@NLO 3.x) — LO workflows

Helps author a single MG5 script, run LO event generation non-interactively, and read off cross sections.

**Validated version**: MG 3.5.15 LTS. Patch-level 3.5.x should work; see `README.md` for compatibility caveats on other releases.

Scope is deliberately narrow:

- **In scope**: MG5_aMC 3.x, LO processes (including loop-induced via `[noborn=QCD]`), SM + arbitrary UFO BSM models, script authoring, non-interactive execution, cross-section extraction from banner/results files.
- **Out of scope (v1)**: NLO (`[QCD]`, fixed-order, FKS), multi-jet merging (MLM/CKKW-L) details, parsing LHE/HepMC event files, detector-level analysis. If the user asks for these, say so and stop — do not improvise.

## Token economy — hard rules

A single LO run emits 10k–100k lines of output. Keeping that out of the context window is non-negotiable.

1. **Never invoke `mg5_aMC`, `bin/generate_events`, or MG Python modules directly through Bash.** Always go through `scripts/run_mg.py`. The wrapper redirects all stdout/stderr to a log file on disk and emits a ~20-line structured summary.
2. **Never `Read`, `cat`, `head`, or `tail` the MG log file in full.** Log is typically 10k+ lines. To inspect, use `Grep` with a narrow pattern against the `log_path` returned by the wrapper, e.g. `Grep(pattern="ERROR|Fatal|Traceback", path=log_path, -C=2, head_limit=30)`.
3. **Never Read LHE or HepMC event files.** They are MB–GB. For cross section use `scripts/runs.py`, which only reads the small banner and results files.
4. **Cache `detect_mg.py` output for the session.** Call it once per conversation; reuse the result.
5. **If the user pastes a large MG log into the conversation**, do not re-read or quote it back. Ask them to save it to disk and Grep it.

Violating any of the above is treated as a bug — back out and use the wrappers.

## Primary artifact: a single `.mg5` script

Every run is driven by **one MG5 script file**. This is the single source of truth — the exact bytes MG consumes. It contains `import model`, `define`, the process (`generate`/`add process`), `output` (for the first run creating the process directory), `launch`, any `set <key> <value>` lines, and the trailing `0` to answer MG's "any more edits?" prompt.

Two script shapes per process:

- **new** — creates the process directory. Shape: `import model → define → generate → output madevent <work_dir> → launch <work_dir> → set … → 0`.
- **rerun** — reuses an already-`output`ed directory. Shape: `launch <work_dir> → set … → 0`. No `generate`/`output`.

## Typical workflow

```
detect_mg.py  →  pick/write .mg5 script  →  run_mg.py  →  runs.py
```

### 1. Detect MG (once per session)

Run `scripts/detect_mg.py`. It reports MG root, version, toolchain, and which extensions (pythia8, lhapdf6, delphes) are installed. If MG is not found, point the user at `references/install.md` (how to install MG) and `references/setup.md` (how the skill finds it). Then stop.

### 2. Pick or write a `.mg5` script

**Do not write from scratch.** Read `examples/LO_example.md` — it is organized as:

1. **Shape templates** (`new` and `rerun`) with `<SLOTS>` marked explicitly (`<MODEL>`, `<PROCESS>`, `<WORK_DIR>`, `<SET_BLOCK>`).
2. **Value catalog** — substitutions for each slot: process strings, built-in vs UFO models, LHC13/14/quick `set` presets, common cuts.
3. **Concrete snippets** for patterns that need more than substitution: loop-induced (`loop_sm` + `[noborn=QCD]`), BSM/UFO (import + `display` introspection).
4. **Worked ttbar walkthrough** — one end-to-end run as a grounding example.

Workflow: copy the `new` (or `rerun`) template → substitute every `<SLOT>` → run. **Any unsubstituted `<…>` placeholder is a bug**; `run_mg.py` refuses to execute a script that still contains them.

Copy-paste is the idiom — MG's script language has no native `include`.

Details on individual pieces: `references/script-syntax.md`, `references/models.md`, `references/run-card.md`, `references/param-card.md`.

### 3. Run

```
scripts/run_mg.py --script path/to/my_run.mg5 [--timeout 3600]
```

The wrapper returns a compact YAML summary — the full log stays on disk:

```yaml
status: ok
xsec_pb: 507.3
xsec_err_pb: 0.8
nevents: 10000
run_dir: mg_work/ttbar/Events/run_02
script_archive: mg_work/ttbar/Events/run_02/inputs/script.mg5
log_path: mg_work/ttbar/mg_run.log
log_size_lines: 24813
duration_s: 142
errors_tail: []
warnings_count: 3
```

### 4. Extract the cross section (and compare runs)

Single run:
```
scripts/runs.py --run-dir mg_work/ttbar/Events/run_02
```

All runs in a work dir, with script-level diff:
```
scripts/runs.py --work-dir mg_work/ttbar
scripts/runs.py --work-dir mg_work/ttbar --runs run_01,run_02,run_03
scripts/runs.py --work-dir mg_work/ttbar --diff-vs baseline
scripts/runs.py --work-dir mg_work/ttbar --diff-vs both
```

Returns `xsec_pb`, `xsec_err_pb`, `nevents`, `run_tag`, `seed` per run. Multi-run mode also reports per-run `set_diff` (plus `model_changed` / `process_changed` when applicable). Reads only small files — never the `.lhe(.gz)`.

**Diff modes** (`--diff-vs`):

| value | meaning | use when |
|---|---|---|
| `previous` (default) | Each run diffed against the one immediately before it (step-by-step delta). | "What did I change in this iteration?" — the common case. |
| `baseline` | Each run diffed against run_01 (cumulative drift from the first). | "How far has my setup drifted from the baseline?" |
| `both` | Include both `diff_vs_previous` and `diff_vs_baseline` per run. | Debugging or reviewing an experiment series. |

Output key: each non-baseline run carries `diff_vs_previous` and/or `diff_vs_baseline`, each containing `{against_run, set_diff, optional model_changed / process_changed}`. An empty `set_diff` means the two scripts were identical for that comparison.

## Iteration pattern (multiple runs on one process dir)

To sweep parameters on an already-generated process:

1. Copy the rerun `.mg5` block from `examples/LO_example.md` into a new file.
2. Edit `set nevents`, `set ebeam1`, etc.
3. `run_mg.py --script my_run.mg5` — work dir is read from the script's `launch <dir>` line; MG auto-increments to `run_02`, `run_03`, …
4. Compare runs via `diff mg_work/ttbar/Events/run_0{1,2}/inputs/script.mg5`.

Each run's exact script is archived at `Events/run_XX/inputs/script.mg5` alongside `run_manifest.yaml`. The archive is the authoritative record — the user's working copy can be anywhere.

## Work directory & archive convention

- **Work dir**: default `./mg_work/<proc_name>/`. MG output trees (hundreds of MB) live here, never in repo root. Add `mg_work/` to `.gitignore`.
- **Per-run archive**: `<work_dir>/Events/run_XX/inputs/script.mg5` (exact script used) + `run_manifest.yaml` (mg version, source path + sha256, cli args, result). Written by `run_mg.py` automatically.
- **Failed runs**: if MG aborts before a `run_XX` directory is created, archive goes to `<work_dir>/failed_runs/<timestamp>/` with the script and log.
- **User's source `.mg5`**: no enforced location. Users may keep scripts under `mg_work/<proc>/scripts/`, in a personal repo, or anywhere. The archive covers reproducibility.

## Decision tree

- **SM LO process**: start from the `new` block in `examples/LO_example.md` → diff-edit → run.
- **Rerunning same process with different params**: start from the `rerun` block in `examples/LO_example.md`, edit `set` lines only.
- **BSM / UFO model**: read `references/models.md` + the BSM block in `examples/LO_example.md`. Import the model, then use `display particles` / `display multiparticles` / `display couplings` **before** writing the process — do not guess particle labels.
- **Loop-induced (e.g. `g g > h`)**: use `loop_sm` model and append `[noborn=QCD]` to the process line — still a LO observable. See the loop-induced block in `examples/LO_example.md`.
- **Error during run**: do **not** Read the log. First check `errors_tail` from the run summary. Then `references/troubleshooting.md`. Only then Grep `log_path` with a narrow pattern.
- **User wants Feynman diagrams only** (no xsec, no events): load `references/diagrams.md`. Different `.mg5` shape (no `launch`) and uses `scripts/make_diagrams.py`.
- **User asks for NLO / MLM+PY8 merging details / LHE parsing / detector simulation**: out of v1 scope. For NLO specifically, `examples/NLO_example.md` is a reserved slot but has no content yet — tell the user and stop.

## References (load on demand)

- `references/install.md` — installing MG + optional extensions (one-time system setup).
- `references/setup.md` — how the skill finds an installed MG (`MG5_HOME`, detection order), work-dir convention, skill smoke test.
- `references/script-syntax.md` — .mg5 script structure: import/define/generate/add process/output/launch/set/0, amplitude/squared-amplitude coupling orders.
- `references/models.md` — built-in + UFO models, introspection commands.
- `references/run-card.md` — run_card.dat keys accessible via `set`.
- `references/param-card.md` — masses, widths, couplings, compute_widths.
- `references/output-and-launch.md` — output modes, launch options, shower/detector notes.
- `references/troubleshooting.md` — MG error messages → cause/fix.
- `references/diagrams.md` — Feynman-diagram PDFs workflow (load only when user asks for diagrams).

## Examples

- `examples/LO_example.md` — templated `.mg5` shapes + value catalog + concrete snippets for non-obvious patterns + one ttbar worked walkthrough. This is where `.mg5` starter content lives.
- `examples/NLO_example.md` — reserved slot for NLO workflows; stub only in v1.

## Scripts

All scripts are `uv run` single-file (PEP-723 inline metadata) — no separate venv needed.

- `scripts/detect_mg.py` — locate MG, report version + extensions.
- `scripts/run_mg.py` — non-interactive MG driver; log → disk, summary → stdout, archive + manifest per run.
- `scripts/runs.py` — read xsec ± err + event count from one run (`--run-dir`), or compare all runs under a work dir with set-level diff (`--work-dir`). Reads banner + manifest only; never LHE.
- `scripts/make_diagrams.py` — generate Feynman-diagram PDFs. When the user asks for diagrams (not events/xsec), see `references/diagrams.md` for the specialized `.mg5` shape and usage.
