# Troubleshooting

Common MG errors, what they mean, and how to fix. Use this before widening a Grep on the full log. Token-economy rule: check `errors_tail` from `run_mg.py`'s summary first — it already isolates the relevant ~10 error lines. Only open the log file with a narrow Grep pattern if `errors_tail` is insufficient.

## Setup / install

| message (or snippet) | cause | fix |
|---|---|---|
| `madgraph requires the six module` | Python `six` missing | `python -m pip install --user six` |
| `MadGraph5_aMC@NLO works with python 3.7 or higher` | Python too old | upgrade Python (3.10+ recommended) |
| `Support for Python3.9 (and below) has been dropped since end of 2025` | warning, not fatal | upgrade when convenient |
| `gfortran: command not found` | no Fortran compiler on PATH | install `gfortran` (distro package) |
| `Cannot install Delphes` / Delphes build failure | ROOT missing | install CERN ROOT first; see `install.md` |

## Model import

| message | cause | fix |
|---|---|---|
| `Invalid model /path/...` | typo in path, or directory not a valid UFO | check the path exists; UFO must contain `particles.py`, `couplings.py`, etc. |
| `No model named X in models/` | model not bundled in this MG distribution | use a path to an external UFO; see `models.md` |
| `KeyError: 'X' in particles.py` | UFO broken for this Python version | check UFO release notes; MG 3.5.14+ has `write_param_card.py` shim for 3.13-incompatible UFOs |
| `Restriction file not found: restrict_X.dat` | restriction name misspelled | `ls $MG5_HOME/models/<MODEL>/restrict_*.dat` to see actual names |

## Process generation

| message | cause | fix |
|---|---|---|
| `No diagrams for process` | process forbidden by selection rules or coupling orders | relax or check orders; for loop-induced use `loop_sm` + `[noborn=QCD]` |
| `Too many particles in the loop` | high-multiplicity loop process | reduce legs or switch to tree-level |
| `Particle not found: X` | label typo, wrong case, or not in loaded model | `display particles` to list labels; remember MG SM uses `a` for photon, `h` (lowercase) for Higgs, `ta-/ta+` for tau |
| `Several coupling orders hierarchy can be generated` | auto-pick ambiguous | specify `QED=N QCD=N` explicitly |
| `Unknown syntax: [QCD]` while using `sm` | tree-level model doesn't support loop brackets | either drop `[…]` (tree only) or `import model loop_sm` first |
| `Generation failed due to infinite loop in model` | coupling-order combination leaves only massless diagrams | tighten `QED<=` / `QCD<=` or check model self-consistency |

## `launch` / run_card

| message | cause | fix |
|---|---|---|
| `Invalid parameter name: X` | `set X value` used an unknown key | `help set` inside MG for the full list; `update to_full` to expose rare keys |
| `PDF set not found` or `LHAPDF error` | `pdlabel=lhapdf` but LHAPDF not installed, or `lhaid` unknown | install LHAPDF (`install lhapdf6`) or switch to `pdlabel=nn23lo1` |
| `beam polarization not supported` | `polbeam1` / `polbeam2` set for a non-polarized PDF | drop polarization setting or switch PDF |
| `Error in integration: phase space empty` | cuts too tight for the process | relax cuts (`ptj`, `mmjj`, etc.) — verify with partonic generator |
| `Integrand is always 0 for subprocess X` | a coupling or mass is set to zero that makes that subprocess vanish | intentional? if so, ignore. If not, check `param_card` |
| `cannot find shower program` | script asked for shower but PY8 not installed | add `shower=OFF` or `install pythia8` |

## Fortran / compilation

| message | cause | fix |
|---|---|---|
| `Compilation failed in SubProcesses/P*` | usually gfortran too old or a model bug | check gfortran version; try `--save-temps` in MG's Fortran flags |
| `Error: Syntax error in Fortran` | MG generator bug for a specific process | report upstream; try a minor process variant |
| `Segmentation fault at runtime` | numerical instability or integrator edge case | re-run with different `iseed`; reduce `sde_strategy` if applicable |

## Runtime behavior

| symptom | likely cause | fix |
|---|---|---|
| Run hangs after "Survey" | disk full, or single subprocess stuck | check disk; grep log for `ERROR` / subprocess that's not finishing |
| Xsec reported as 0 ± 0 | process has zero rate (correct physics) OR cuts eliminated all phase space | relax cuts, or verify process physically allowed |
| Xsec with huge error bar (MC error > 10 %) | too few events or tight cuts | raise `nevents`, increase survey/refine passes, or relax cuts |
| Warning: "Dynamical scale choice is on" but output looks fixed | `fixed_ren_scale=True` overrides | set `fixed_ren_scale False` to use `dynamical_scale_choice` |
| `UnboundLocalError` or Python traceback in MG | MG internal bug | try latest patch version; report to MG launchpad |

## Wrapper-specific (`run_mg.py`)

| summary field | meaning | action |
|---|---|---|
| `status: error`, `reason: "unsubstituted placeholders in script"` | script still contains `<SLOT>` tokens | fill every `<…>` before rerunning |
| `status: error`, `reason: "MG not found..."` | `$MG5_HOME` unset and fallbacks failed | see `setup.md` |
| `status: timeout` | run exceeded `--timeout` | raise timeout or reduce `nevents` / tighten cuts |
| `status: error`, `errors_tail` empty, `mg_returncode != 0` | MG died without a matched error pattern | Grep the log with a narrow pattern: `Grep -n -i 'error\|fatal\|traceback' log_path` |

## When the log is needed

Only grep when `errors_tail` plus the tables above don't resolve the issue. Narrow patterns first:

```
Grep(pattern="ERROR|Fatal|Traceback", path=log_path, -C=2, head_limit=30)
Grep(pattern="Compilation", path=log_path, -C=1, head_limit=20)
```

**Never** `Read` or `cat` the log in full. MG logs are routinely 10k–100k lines.

## When MG itself fails mysteriously

- Retry with a lower seed (`set iseed 1`) — some bugs are integration-path-dependent.
- Try the minimal variant of the process (fewer legs, no decay chain) — isolates whether the failure is process-specific.
- Check `$MG5_HOME/UpdateNotes.txt` for known fixes between your patch version and the latest.
- Report reproducible bugs at the MG launchpad with the minimal `.mg5` script that triggers it.
