# NLO example — templates, catalog, concrete snippets

Fixed-order NLO (QCD) workflows. Structure mirrors `LO_example.md`. NLO+PS matching and multi-jet merging are deferred; see the end of this doc.

## Shape templates

### `new_nlo` (create NLO process directory)

```
import model <LOOP_MODEL>
<DEFINES>
generate <PROCESS> [<CORRECTION>]
<ADD_PROCESSES>
output <WORK_DIR>
launch <WORK_DIR>
fixed_order=ON
shower=OFF
madspin=OFF
reweight=OFF
madanalysis=OFF
<SET_BLOCK>
0
```

Fill rules:

| slot | required | notes |
|---|---|---|
| `<LOOP_MODEL>` | yes | Must be loop-capable: `loop_sm` (SM NLO QCD), `loop_sm-no_b_mass`, `loop_qcd_qed_sm` (needed for `[QED]` — **not bundled in 3.5.15 LTS**), or a loop-UFO BSM. Plain `sm` does not work for NLO. |
| `<PROCESS>` | yes | SM process string. Same syntax as LO. |
| `<CORRECTION>` | yes | `[QCD]` (most common), `[real=QCD]`, `[virt=QCD]`, `[QED]`, `[QCD QED]`. See `references/script-syntax.md` for semantics. |
| `<WORK_DIR>` | yes | Same on `output` and `launch` lines. Note: no `madevent` argument needed — MG auto-detects NLO and uses the aMC@NLO template. |
| `<SET_BLOCK>` | yes | NLO-specific presets below. |

### `rerun_nlo` (reuse existing process dir)

```
launch <WORK_DIR>
fixed_order=ON
shower=OFF
madspin=OFF
reweight=OFF
madanalysis=OFF
<SET_BLOCK>
0
```

### Why explicit switches instead of `nlo` shortcut

Convenience shortcuts (`nlo`, `aMC@NLO`, etc.) exist but set multiple switches at once in a version-dependent way. Explicit `fixed_order=ON shower=OFF …` is more portable and self-documenting.

## Value catalog

### `<LOOP_MODEL>` values

| value | bundled in 3.5.15 LTS | supports |
|---|---|---|
| `loop_sm` | ✓ | `[QCD]`, `[noborn=QCD]` (loop-induced LO) |
| `loop_sm-no_b_mass` | ✓ | as above, with m_b=0 (faster for non-b-tagged processes) |
| `loop_qcd_qed_sm` | ✗ (separate download) | `[QCD]`, `[QED]`, `[QCD QED]`, `[QCD QED QED]` |
| UFO@NLO BSM | user-supplied | BSM NLO — depends on model |

### `<CORRECTION>` values

| bracket | physics | cost (rel. to LO) |
|---|---|---|
| `[QCD]` | Full NLO QCD | ~5–30× |
| `[real=QCD]` | NLO real-emission only | ~3–10× |
| `[virt=QCD]` | NLO virtual only (needs local subtraction setup) | ~2–5×, niche |
| `[QED]` | NLO QED | (requires loop_qcd_qed_sm) |
| `[QCD QED]` | Mixed NLO | (requires loop_qcd_qed_sm) |

### `<PROCESS>` values — common NLO QCD targets

| pattern | process string | LO σ (LHC13) | typical K-factor |
|---|---|---|---|
| Drell–Yan | `p p > e+ e- [QCD]` (add `set mll 50`) | ~1600 pb | ~1.15 |
| Top pair | `p p > t t~ [QCD]` | ~500 pb | ~1.5 |
| W + jet | `p p > w+ j [QCD]` | — | ~1.3 |
| Z + jet | `p p > z j [QCD]` | — | ~1.3 |
| Dijet | `p p > j j [QCD]` | (huge, apply cuts!) | ~1.2 |
| Higgs via gluon fusion (N/NLO loop-induced) | `g g > h [noborn=QCD]` is LO — NLO ggH needs `heft` or dedicated model |

For BSM NLO, always run `display particles` / `display couplings` after importing the loop UFO.

### `<SET_BLOCK>` presets for NLO

Drop into the `<SET_BLOCK>` slot.

#### LHC13 NLO default

```
set nevents 10000
set ebeam1 6500
set ebeam2 6500
set pdlabel lhapdf
set lhaid 303400              # NNPDF31_nnlo_as_0118 — prefer NNLO-evolved PDFs for NLO runs
set req_acc -1
```

#### LHC13 NLO quick (smoke test)

```
set nevents 1000
set ebeam1 6500
set ebeam2 6500
set req_acc 0.05              # coarser accuracy → much faster
```

#### LHC14 NLO default

```
set nevents 10000
set ebeam1 7000
set ebeam2 7000
set pdlabel lhapdf
set lhaid 303400
set req_acc -1
```

#### Scale + PDF uncertainty (reweight on-the-fly)

```
set dynamical_scale_choice [-1]
set rw_rscale [1.0, 2.0, 0.5]
set rw_fscale [1.0, 2.0, 0.5]
set reweight_scale [True]
set reweight_pdf [False]
```

The `scale_envelope` field in `runs.py` output comes from these.

#### FastJet (mandatory for NLO with jets)

```
set jetalgo -1                # anti-kT
set jetradius 0.4
set ptj 20                    # basic generation cut
set etaj 5.0
```

## Concrete snippet — NLO QCD Drell–Yan (tested)

This is the first NLO run-through verified end-to-end on MG 3.5.15 LTS. Full walkthrough in the next section.

```
import model loop_sm
generate p p > e+ e- [QCD]
output mg_work/dy_nlo
launch mg_work/dy_nlo
fixed_order=ON
shower=OFF
madspin=OFF
reweight=OFF
madanalysis=OFF
set nevents 1000
set ebeam1 6500
set ebeam2 6500
set mll 50
set req_acc 0.05
0
```

## K-factor workflow (NLO/LO comparison)

One of the most common NLO questions: "what's the K-factor for this process?" Use the same work dir for both LO and NLO runs, then compare.

```
# 1. LO baseline (run_01)
#    base.mg5:
import model sm
generate p p > e+ e-
output mg_work/dy_both
launch mg_work/dy_both
shower=OFF
detector=OFF
set nevents 10000
set ebeam 6500
set mll 50
0
```

```
# 2. NLO on the SAME work dir — but NLO needs a different process directory
#    because [QCD] changes the generated code. So use a DIFFERENT work_dir:
#    base_nlo.mg5:
import model loop_sm
generate p p > e+ e- [QCD]
output mg_work/dy_both_nlo
launch mg_work/dy_both_nlo
fixed_order=ON
shower=OFF
madspin=OFF
reweight=OFF
madanalysis=OFF
set nevents 10000
set ebeam 6500
set mll 50
set req_acc -1
0
```

```
# 3. Read both results manually (LO from one work dir, NLO from the other)
scripts/runs.py --run-dir mg_work/dy_both/Events/run_01
scripts/runs.py --run-dir mg_work/dy_both_nlo/Events/run_01
```

The NLO summary entry will include `order: NLO` + `scale_envelope`. Divide xsec values for the K-factor.

**Why two work dirs**: `[QCD]` vs no bracket generate different Fortran code, so the process directories are incompatible. Unlike LO iteration (which reuses one process dir for many runs), LO↔NLO comparison needs two dirs.

## Worked walkthrough — p p > e+ e- [QCD] at LHC13

Verified end-to-end on MG 3.5.15 LTS. Takes ~4 min on a 4-core machine for a first run (first-time library compilation dominates).

### 1. Detect MG

```
scripts/detect_mg.py
```

Same as LO — nothing NLO-specific here beyond noting that gfortran is found.

### 2. Write the script

```
# dy_nlo.mg5
import model loop_sm
generate p p > e+ e- [QCD]
output mg_work/dy_nlo
launch mg_work/dy_nlo
fixed_order=ON
shower=OFF
madspin=OFF
reweight=OFF
madanalysis=OFF
set nevents 1000
set ebeam 6500
set mll 50
set req_acc 0.05
0
```

### 3. Run (with generous timeout)

```
CCACHE_DISABLE=1 scripts/run_mg.py --script dy_nlo.mg5 --timeout 900
```

The `CCACHE_DISABLE=1` is a workaround for sandboxed shells where ccache's tmp dir is read-only; on an unrestricted shell it isn't needed.

Expected summary (truncated):

```json
{
  "status": "ok",
  "order": "NLO",
  "xsec_pb": 1811.0,
  "xsec_err_pb": 7.6,
  "nevents": 1000,
  "run_dir": "mg_work/dy_nlo/Events/run_01",
  "log_size_lines": 369,
  "duration_s": 236.2
}
```

### 4. Read full NLO result (including scale envelope)

```
scripts/runs.py --run-dir mg_work/dy_nlo/Events/run_01
```

Returns (abbreviated):

```json
{
  "order": "NLO",
  "xsec_pb": 1811.0,
  "xsec_err_pb": 7.6,
  "scale_envelope": {
    "central_pb": 1811.0,
    "plus_pct": "5.7%",
    "minus_pct": "10.4%"
  }
}
```

## Not covered (deferred)

**Out of v1 scope even for NLO**:

1. **NLO+PS matching (MC@NLO)** — `fixed_order=OFF shower=PYTHIA8` path. Requires `install pythia8` inside MG + MCatNLO-PY8 interface library. Produces showered events but doubles the integration machinery complexity.
2. **Multi-jet merging at NLO** — FxFx (`ickkw=3`), UNLOPS (`ickkw=4`), NNLL+NLO jet veto (`ickkw=-1`). Additional per-emission matching logic required.
3. **MadSpin at NLO** — spin-correlation-aware decays in NLO-matched events. Works syntactically (`madspin=ON`) but not tested by this skill.
4. **NLO EW corrections** — `[QED]`, `[QCD QED]`, mixed-order (`QCD^2`, `QED^2` constraints). Needs `loop_qcd_qed_sm` UFO, not in LTS.
5. **BSM NLO** — UFO@NLO models (SMEFT@NLO, etc.). Requires the specific loop UFO.
6. **NLO gridpack / event re-weighting** — `gridpack=True` at NLO + offline reweighting.
7. **NLO plots / histograms** — MG auto-generates `MADatNLO.HwU` but this skill doesn't parse it; users can run `gnuplot MADatNLO.gnuplot` manually.

If a user's request touches any of these, acknowledge the out-of-scope status and stop — don't improvise.
