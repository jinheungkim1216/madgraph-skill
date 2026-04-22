# LO example — templates, catalog, concrete snippets

Where this skill's `.mg5` starter content lives. Copy a shape template → substitute every `<SLOT>` → run via `scripts/run_mg.py`. Unsubstituted placeholders are rejected by the wrapper.

## Shape templates

### `new` (create process directory)

```
import model <MODEL>
<DEFINES>
generate <PROCESS>
<ADD_PROCESSES>
output madevent <WORK_DIR>
launch <WORK_DIR>
shower=OFF
detector=OFF
<SET_BLOCK>
0
```

Fill rules:

| slot | required | notes |
|---|---|---|
| `<MODEL>` | yes | see "Model values" below |
| `<DEFINES>` | no | delete the line or fill with `define ...` statements; leave blank if built-in `p`, `j`, `l+`, `l-` suffice |
| `<PROCESS>` | yes | the process string; see "Process values" |
| `<ADD_PROCESSES>` | no | delete or add `add process ...` lines |
| `<WORK_DIR>` | yes | same path on both `output` and `launch` lines — e.g., `mg_work/ttbar` |
| `<SET_BLOCK>` | yes | see "Set presets"; must set at least `ebeam1`, `ebeam2`, `nevents` unless defaults are acceptable |

### `rerun` (reuse existing process directory)

```
launch <WORK_DIR>
shower=OFF
detector=OFF
<SET_BLOCK>
0
```

No `import`, `generate`, or `output`. Produces `Events/run_02`, `run_03`, … Use when only `<SET_BLOCK>` changes between runs.

## Value catalog

### `<MODEL>` values

| value | when |
|---|---|
| `sm` | default for LHC tree-level SM |
| `sm-no_b_mass` | faster SM when b-initial-state is irrelevant |
| `loop_sm` | **required** for loop-induced LO (`[noborn=QCD]`) |
| `MSSM_SLHA2` | MSSM studies |
| `/abs/path/to/MyModel_UFO` | external UFO |

### `<PROCESS>` values

| pattern | process string | notes |
|---|---|---|
| ttbar | `p p > t t~` | canonical SM 2→2 |
| Drell–Yan | `p p > l+ l-` | uses built-in `l+ l-` (e/μ, no τ) |
| Dijet | `p p > j j` | `j` = built-in jet label |
| VBF-H | `p p > h j j QED=3 QCD=0` | **always** specify orders for VBF to kill gluon-fusion |
| ZH | `p p > h z` | |
| Single top (t-channel) | `p p > t j` | |
| W+jets | `p p > w+ j` | |
| Decay chain | `p p > t t~, (t > b w+, w+ > l+ vl)` | comma-separated, each in `( )` |
| Loop-induced | `g g > h [noborn=QCD]` | **must use `<MODEL>=loop_sm`** |

For BSM, **never guess the process**. Run `display particles` first — see "BSM concrete snippet".

### `<SET_BLOCK>` presets

Paste the content of one preset into `<SET_BLOCK>`:

MG lets you write symmetric beams in one line: `set lhc 13` expands to `lpp1=lpp2=1, ebeam1=ebeam2=6500`. Same for `set lep 91.2` (e⁺e⁻), and `set ebeam V` / `set lpp V` for the individual pair. See `run-card.md` for all aliases.

#### LHC13 quick — smoke test, ~1 minute

```
set lhc 13
set nevents 1000
```

#### LHC13 default — 10k events, NNPDF via LHAPDF

```
set lhc 13
set nevents 10000
set pdlabel lhapdf
set lhaid 260000
```

#### LHC14 default

```
set lhc 14
set nevents 10000
set pdlabel lhapdf
set lhaid 260000
```

#### Add common cuts (optional)

```
set ptj 20
set etaj 5.0
set drjj 0.4
set ptl 10
set etal 2.5
```

#### Add scale-variation systematics (optional)

```
set use_syst True
set systematics_program systematics
set systematics_arguments ['--mur=0.5,1,2', '--muf=0.5,1,2']
```

#### Realistic SM physical parameters (optional, add to any preset)

```
set mass 6 172.5
set mass 25 125.0
set decay 25 auto
```

## Concrete snippets (more than simple substitution)

### Loop-induced `g g > h`

```
import model loop_sm
generate g g > h [noborn=QCD]
output madevent mg_work/gg_h
launch mg_work/gg_h
shower=OFF
detector=OFF
set lhc 13
set nevents 10000
set mass 25 125.0
set decay 25 auto
0
```

`[noborn=QCD]` squares the one-loop amplitude at LO. Requires `loop_sm` — `sm` gives "no diagrams".

### BSM / UFO — introspect before writing

```
import model /abs/path/to/MyModel_UFO
display particles
display multiparticles
display couplings
display parameters

# read the printout (Grep log for "Particle", "Coupling", etc.), then write the process:
generate p p > my_bsm_particle my_bsm_particle~ NP=2 QED=0 QCD=2
output madevent mg_work/bsm_run
launch mg_work/bsm_run
shower=OFF
detector=OFF
set lhc 13
set nevents 10000
# BSM-specific param_card edits go here, e.g.:
# set my_np_block 1 1.0
0
```

If the UFO defines widths as zero placeholders, add `compute_widths <pdg>` lines before `output`.

## Worked walkthrough — ttbar at LHC13 quick

### 1. Detect MG

```
scripts/detect_mg.py
```

Expect a JSON block with `status: ok`, `mg_root`, `version`, `python`, `gfortran`, and extension status.

### 2. Write the `.mg5` script

```
# mg_scripts/ttbar_run1.mg5
import model sm
generate p p > t t~
output madevent mg_work/ttbar
launch mg_work/ttbar
shower=OFF
detector=OFF
set lhc 13
set nevents 1000
set mass 6 172.5
0
```

### 3. Run

```
scripts/run_mg.py --script mg_scripts/ttbar_run1.mg5
```

Expected summary (approximate values):

```json
{
  "status": "ok",
  "xsec_pb": 487.2,
  "xsec_err_pb": 1.8,
  "nevents": 1000,
  "run_tag": "run_01",
  "run_dir": "/abs/path/mg_work/ttbar/Events/run_01",
  "script_archive": "/abs/path/mg_work/ttbar/Events/run_01/inputs/script.mg5",
  "log_path": "/abs/path/mg_work/ttbar/mg_run.log",
  "log_size_lines": 17000,
  "duration_s": 72.3,
  "mg_returncode": 0,
  "warnings_count": 4,
  "errors_tail": []
}
```

### 4. Extract cross section from the run dir

```
scripts/parse_xsec.py --run-dir mg_work/ttbar/Events/run_01
```

This reads only the banner file. Output matches `xsec_pb` / `xsec_err_pb` / `nevents` from step 3.

### 5. Iterate with a rerun script

```
# mg_scripts/ttbar_run2.mg5  — reuses the process dir, just more events
launch mg_work/ttbar
shower=OFF
detector=OFF
set lhc 13
set nevents 10000
set mass 6 172.5
0
```

```
scripts/run_mg.py --script mg_scripts/ttbar_run2.mg5
```

Produces `run_02`. Compare the two:

```
diff mg_work/ttbar/Events/run_01/inputs/script.mg5 mg_work/ttbar/Events/run_02/inputs/script.mg5
```
