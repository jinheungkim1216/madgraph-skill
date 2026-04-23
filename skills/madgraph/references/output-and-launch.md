# `output` and `launch` — what MG actually does

Syntax for these commands lives in `script-syntax.md`. This doc explains what happens under the hood: disk layout, timing, and the prompts a `.mg5` script must answer during `launch`.

## `output madevent <dir>`

One-time per process. Creates the full process directory tree:

```
<dir>/
├── Source/                           # generated Fortran (matrix elements)
├── SubProcesses/                     # one subdir per subprocess
├── Cards/
│   ├── run_card.dat                  # MG fills from Template/LO/Cards/run_card.dat
│   ├── param_card.dat                # from the imported model
│   ├── proc_card_mg5.dat             # records the generate/define calls
│   └── (pythia8_card.dat, etc. — copied even if PY8 isn't installed)
├── HTML/                             # results viewer (populated after launch)
├── Events/                           # empty until launch
├── bin/
│   ├── madevent                      # interactive event generator
│   └── generate_events               # the binary run_mg.py ultimately invokes
└── README                            # auto-generated process summary
```

The `Source/` Fortran is compiled lazily — the first `launch` triggers the build. A simple 2→2 process builds in ~10–30 s, a 2→4 multi-leg process in minutes. Subsequent launches on the same directory skip the rebuild.

Space: a single 2→2 output is ~20–50 MB before events; high-multiplicity or multi-subprocess outputs can reach hundreds of MB.

Rerunning `output` into an existing directory asks for confirmation — the `rerun` script shape (`launch` only, no `output`) avoids this.

## `launch <dir>` — what the prompts are

`launch` enters an interactive menu system. A `.mg5` script drives it non-interactively by writing the answers in order, ending with `0`.

### Prompts that appear (in order), and how to answer

1. **Shower selection** — only appears if `pythia8` (or `pythia-pgs`) is installed.
   ```
   Do you want to run:
     0) No shower
     1) Pythia8
   ```
   Parton-level run: `shower=OFF` or just let the final `0` accept the default.

2. **Detector selection** — only appears if `Delphes` is installed.
   ```
   Do you want to run:
     0) No detector
     1) Delphes
   ```
   Parton-level: `detector=OFF` or accept default.

3. **Analysis selection** — only if `MadAnalysis5` or similar is configured. `analysis=OFF` / default.

4. **Card edit menu** — always appears.
   ```
   Do you want to edit a card?
     0) Continue
     1) run_card.dat
     2) param_card.dat
     ...
   ```
   The `set <key> <value>` lines in the script apply here. Terminating `0` means "no more edits, start the run".

### Script-form that handles all cases

```
launch <WORK_DIR>
shower=OFF          # harmless if not installed; required if PY8 installed and you want parton-level
detector=OFF        # harmless if not installed
analysis=OFF
set nevents 10000
set ebeam1 6500
set ebeam2 6500
0
```

Including `shower=OFF` / `detector=OFF` makes the script portable across machines with different extensions installed.

## What `launch` does after the prompts

1. **Build** (first time only): compiles Fortran in `Source/` and each `SubProcesses/P*/` — minutes for complex processes.
2. **Survey**: runs a quick phase-space scan with a small number of points to estimate integrand weight per subprocess.
3. **Refine**: iteratively improves the integration grid.
4. **Unweight**: generates events from the grid until `nevents` unweighted events exist.
5. **Combine**: merges per-subprocess events into `Events/run_XX/unweighted_events.lhe.gz`.
6. **Write banner**: `Events/run_XX/<run_tag>_banner.txt` inlines the effective `run_card`, `param_card`, and process summary — authoritative reproducibility record.
7. **Report**: cross section + Monte-Carlo error in stdout and `HTML/run_XX/results.html`.

Time: 2→2 LO with 10k events runs in 1–5 minutes on a 4-core laptop. Multi-leg or tight cuts can stretch this by 10× or more.

## `Events/run_XX/` after a successful run

```
Events/run_XX/
├── <run_tag>_banner.txt                # run_card + param_card + proc_card inlined (READ THIS for reproducibility)
├── unweighted_events.lhe.gz            # the events (do NOT Read — MB–GB)
├── events.lhe.gz                       # alias/symlink in some cases
├── parton_systematics.log              # if use_syst=True, scale/PDF variation log
├── summary.txt                         # high-level summary (a few KB)
└── inputs/                             # ← written by scripts/run_mg.py (this skill)
    ├── script.mg5                      # exact script used for this run
    └── run_manifest.yaml               # mg version, cli args, sha256, xsec summary
```

`runs.py` reads the banner + `inputs/run_manifest.yaml` only — never the `.lhe.gz`.

## Multiple runs on one process directory

Each `launch` creates the next `Events/run_NN` (auto-incremented). Original process directory is untouched — only `Cards/` and `Events/` change per run.

```
launch mg_work/ttbar      # produces run_01
launch mg_work/ttbar      # produces run_02
```

Different runs can have different `set` blocks; the banner of each run records what was active.

## When to use which work-dir layout

| scenario | layout |
|---|---|
| Single process, iterate params | one `mg_work/<proc>/` with many `Events/run_XX/` |
| Multiple processes | one `mg_work/<proc>/` per process — do not share |
| Parameter scan (same process, many points) | single `mg_work/<proc>/` — use MG native `set <key> scan:[v1, v2, ...]` in one launch block (param_card keys only). See `references/script-syntax.md` § `scan:[...]`. |

Never `output` into repo root or into an already-existing unrelated directory — MG writes dozens of files at the target path.

## NLO launch flow

When the generated process carries an NLO bracket (`[QCD]`, etc.), MG uses the aMC@NLO template — `output` auto-detects this and does not need an explicit mode argument (just `output <dir>`, no `madevent`). The `launch` prompt set is different from LO:

```
Which switches would you like to change?
  1. Type of perturbative computation   order    = NLO
  2. No MC@[N]LO matching / event gen   fixed_order = ON | OFF
  3. Shower the generated events        shower   = OFF | PYTHIA8 | HERWIGPP | ...
  4. Decay onshell particles            madspin  = OFF | ON
  5. Add weights to events              reweight = OFF | ON
  6. Run MadAnalysis5 on the events     madanalysis = OFF | ON
```

Convenient shortcuts (one-word lines inside the launch block):

| shortcut | effect |
|---|---|
| `nlo` | order=NLO, fixed_order=ON, shower=OFF → **parton-level NLO** (v1 target) |
| `lo` | order=LO, fixed_order=ON, shower=OFF → LO equivalent path through aMC@NLO template |
| `aMC@NLO` | order=NLO, fixed_order=OFF, shower=ON → NLO+PS matching (needs pythia8) |
| `noshower` | order=NLO, fixed_order=OFF, shower=OFF → produce NLO-matched LHE events without running the shower |
| `aMC@LO` | order=LO, fixed_order=OFF, shower=ON |

### Script-form for fixed-order NLO (v1 target)

```
launch <WORK_DIR>
fixed_order=ON
shower=OFF
madspin=OFF
reweight=OFF
madanalysis=OFF
set nevents 10000
set req_acc -1
set ebeam1 6500
set ebeam2 6500
0
```

Explicit switches are more portable than shortcuts across MG versions.

### NLO run_XX directory differences

NLO writes more/different files than LO:

```
Events/run_XX/
├── <run_tag>_banner.txt          # run_card + param_card (NO xsec in NLO banner)
├── summary.txt                   # ★ NLO xsec + scale envelope live HERE
├── MADatNLO.HwU                  # HwU histogram data
├── MADatNLO.ps / .pdf            # auto-generated histogram plots
├── MADatNLO.gnuplot              # data + script for gnuplot
├── res_0.txt / res_1.txt         # raw integration results per channel
├── alllogs_*.html                # verbose per-subprocess logs
├── RunMaterial.tar.gz            # Fortran sources snapshot
└── inputs/                       # ← written by run_mg.py
    ├── script.mg5
    └── run_manifest.yaml
```

Key practical differences:
- **No `unweighted_events.lhe.gz`** in pure fixed-order mode — events are not unweighted.
- **`summary.txt` is the xsec source** for NLO. `runs.py` reads it automatically and flags `order: NLO`.
- **Automatic histograms**: MG produces `MADatNLO.{HwU,ps,pdf}` with basic kinematic plots. Not parsed by the skill but available on disk.

### NLO time and resource notes

- **First-run compilation**: NLO auto-installs `Ninja`, `Collier`, optionally `CutTools` into `$MG5_HOME/HEPTools/`. First run is slow (~minutes). Subsequent runs reuse the libraries.
- **ccache interaction**: If ccache is enabled and its cache dir is read-only (sandbox cases), NLO compilation fails. Export `CCACHE_DISABLE=1` to work around.
- **Integration time**: Fixed-order NLO typically takes 5–30× longer than equivalent LO. Start with low stats (e.g. `req_acc=0.05` or `nevents=1000`) for quick checks.
- **`--timeout`** on `run_mg.py`: set generously for NLO (e.g. `--timeout 1800`).

## Advanced launch flags (not used by this skill)

`launch -f` (force defaults) and `launch -i <tag>` (interactive) exist but complicate scripting. `run_mg.py` always uses plain `launch <dir>` and drives the prompts via the script's lines.
