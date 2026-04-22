# `.mg5` script syntax (LO)

The exact grammar MG consumes when invoked as `mg5_aMC <script.mg5>`. Commands are consumed top-to-bottom. There is no variable substitution, no conditional, and no `include` — copy-paste is the composition idiom. Lines starting with `#` are comments.

## Anatomy of a run

A `new` (first time) script produces a process directory and one run:

```
import model <MODEL>
<DEFINES>                    # optional
generate <PROCESS>
<ADD_PROCESSES>              # optional
output madevent <WORK_DIR>
launch <WORK_DIR>
<SET_BLOCK>
0
```

A `rerun` script skips `generate`/`output` and points `launch` at an existing directory:

```
launch <WORK_DIR>
<SET_BLOCK>
0
```

`run_mg.py` writes the exact script used into `Events/run_XX/inputs/script.mg5` — that archive is the authoritative record of what ran.

## `import model`

```
import model <name>                       # built-in or UFO on PATH
import model <name>-<restriction>         # built-in with a restriction card applied
import model /abs/path/to/MyModel_UFO     # external UFO
```

Selecting the right model is required **before** `generate`:

- `sm` — default SM, massless u/d/c/s/b. The usual starting point.
- `sm-no_b_mass`, `sm-no_widths`, `sm-no_tau_mass`, … — SM with a `restrict_<suffix>.dat` applied (see `models.md`).
- `loop_sm` — SM variant that supports loop-induced processes (`[noborn=QCD]`). Required for e.g. `g g > h`.
- UFO path or UFO name resolvable in `$MG5_HOME/models/` — for BSM. Always run `display particles` before writing the process (see `models.md`).

Only one `import model` per script — importing a second one resets the process list.

## `define` (multiparticle labels)

```
define <label> = <particle> [<particle>...]
```

MG ships with these pre-defined (see `input/multiparticles_default.txt`); you do **not** need to `define` them yourself:

| label | expands to |
|---|---|
| `p` | `g u c d s u~ c~ d~ s~` |
| `j` | `g u c d s u~ c~ d~ s~` |
| `l+` | `e+ mu+` |
| `l-` | `e- mu-` |
| `vl` | `ve vm vt` |
| `vl~` | `ve~ vm~ vt~` |

Common reasons to add your own `define`:

- Include b-quarks in `p`/`j` when the process allows: `define p = g u c d s b u~ c~ d~ s~ b~`.
- Add τ to leptons: `define lep+ = e+ mu+ ta+`.
- BSM multiplet shortcuts: `define sq = ul ur dl dr cl cr sl sr`.

A `define` overrides the built-in label only within that script.

## `generate` and `add process`

```
generate <particles_in> > <particles_out> [, <decay>, ...] [ORDERS] [BRACKETS]
add process ...
```

Where:

- **`<particles_in> > <particles_out>`** — process spec using particle labels (PDG names MG expects; see `models.md` for lookup).

- **Decay chain (optional, comma-separated)** — each `, (...)` decays one unstable particle:

  ```
  generate p p > t t~, (t > b w+, w+ > l+ vl), (t~ > b~ w-, w- > j j)
  ```

  MG treats decay-chain children as on-shell; use it when narrow-width approximation is fine. For full off-shell, put everything in the main process (`generate p p > b b~ w+ w- > b b~ l+ vl j j`) — much more expensive.

- **Coupling orders (optional, no leading bracket)** — constrain coupling powers. Space-separated. Two levels exist:

  - **Amplitude level** (`QED=`, `QCD=`, `NP=`, or `<=` / `>=`) — counts coupling vertices in each Feynman diagram.

    ```
    generate p p > h j j QED=3 QCD=0         # VBF-H only (no gluon-fusion contamination)
    generate p p > e+ e- QED<=2 QCD<=99      # allow up to 2 EW couplings
    ```

  - **Squared-amplitude level** (`QED^2=`, `QCD^2=`, `NP^2=`, with `==` / `<=` / `>=`) — counts couplings in |M|², selecting specific interference terms after squaring.

    ```
    generate p p > e+ e- NP^2==2             # pure BSM-squared (drop SM² and SM×BSM)
    generate p p > e+ e- NP^2<=2             # keep SM² + SM×BSM, drop BSM²
    ```

    Amplitude and squared orders can be combined. Use `^2` whenever you need to isolate interference terms — this is the only way to separate SM², SM×BSM, and BSM² contributions.

  Default is MG's auto-choice (minimal QED, maximal QCD). Always specify orders when your selection is non-default — MG prints what it chose otherwise.

- **Bracketed modifier (optional)** — `[noborn=QCD]` marks a **loop-induced** process at LO. The tree amplitude would be zero (e.g., `g g > h` in SM), so the one-loop amplitude is squared at leading order.

  ```
  import model loop_sm
  generate g g > h [noborn=QCD]
  ```

  Requires `loop_sm` (or another loop-compatible model). `[QCD]`/`[real=QCD]` are NLO — out of v1 scope.

- **`add process`** — subsequent calls add another subprocess to the same output. Typical for multi-jet samples:

  ```
  generate p p > t t~
  add process p p > t t~ j
  add process p p > t t~ j j
  ```

  All added processes share one `output` and are generated together (MLM-style matching requires run_card tweaks — beyond v1 scope here).

## `output`

```
output madevent <dir>
```

`madevent` is the only mode this skill uses — it generates the Fortran integrator for event generation, which is what you need for cross sections and `.lhe` events. (MG also supports `standalone`, `standalone_cpp`, `pythia8`, etc., but these are out of v1 scope.)

Path: **always** under the work dir (`mg_work/<proc_name>`); MG writes hundreds of MB under this directory. Writing to repo root pollutes the tree.

Running `output` a second time on an existing directory asks for confirmation. The `rerun` shape avoids this by skipping `output` entirely.

## `launch`

```
launch <WORK_DIR>
```

Starts a run using the cards in `<WORK_DIR>/Cards/`. Without subsequent `set` lines, MG enters an interactive prompt asking whether to edit cards. The script drives this non-interactively:

```
launch mg_work/ttbar
set nevents 10000
set ebeam1 6500
set ebeam2 6500
0
```

The terminating `0` answers MG's final "edit any more?" prompt with "no, start the run".

Multiple `launch` calls in one script each produce a new `Events/run_NN` directory — MG auto-increments `NN`.

## `set <key> <value>`

Applies only between a `launch` and its `0`. `<key>` is matched against keys in `run_card.dat` first, then `param_card.dat`. Examples:

```
set nevents 10000           # run_card
set ebeam1 6500             # run_card
set mass 6 172.5            # param_card: top quark mass
set decay 23 2.4952         # param_card: Z width
set width 25 auto           # param_card: compute this width automatically
```

See `run-card.md` for full key list and `param-card.md` for particle-indexed sets.

Values passed to `set` are validated by MG. Unknown keys produce an error; out-of-range values are warned.

### `scan:[...]` — parameter sweep inside MG

MG natively iterates a `set` value over a list of points, producing one run per point in **one** invocation:

```
launch mg_work/ttbar
set mass 6 scan:[170, 172.5, 175]
set nevents 10000
0
```

Creates three consecutive `run_NN` directories. Each run's banner records the specific value used.

**Only param_card keys support `scan:[...]`**. That includes masses, widths, couplings, CKM entries, BSM parameters — anything `run_card.md` would describe as living in `param_card.dat`. **Run_card keys (`nevents`, `ebeam`, `pdlabel`, cuts, …) do NOT support scan** — MG silently takes the literal string as the value and you get one run with garbage, not a sweep. To sweep a run_card key, either edit multiple scripts by hand or file it under a future `scan.py` helper.

Multiple `scan:` lines in one `launch` block → **Cartesian product**:

```
launch mg_work/ttbar
set mass 6 scan:[170, 172.5]
set aewm1 scan:[130, 135]
0
```

Produces 4 runs covering every (mass, aewm1) pair.

Why use MG's native scan:

- MG reuses phase-space grids across points — faster than independent `launch` calls.
- Each run gets its own banner; scan summary goes to `Events/scan_run_*.txt` with a table of (run_name, param_values, xsec).

### Interaction with the wrappers

- `run_mg.py` detects the multiple new `run_NN` directories, switches its summary to `mode: multi_run_scan` with a `created_runs` list, and skips per-run xsec fields (single stdout can't cleanly attribute them to individual runs).
- Follow up with:

  ```
  scripts/runs.py --work-dir <path> --diff-vs baseline
  ```

  For each scan-produced run, `runs.py` attaches a `scan_values` field (e.g. `{"sminputs#1": "1.35e+02"}`) by parsing `Events/scan_run_*.txt`. Combined with the per-run `xsec_pb` from banner, this gives the full scan table in one call.

## The terminating `0`

Required at the end of every `launch` block. MG treats it as "I'm done editing cards, run". Without it MG blocks on interactive input — `run_mg.py` will time out or hang.

If a script has multiple `launch` blocks, each needs its own `0`:

```
launch mg_work/ttbar
set nevents 1000
0
launch mg_work/ttbar
set nevents 100000
0
```

(Two runs: `run_01` then `run_02`.)

## What NOT to put in a script (v1)

- `install <ext>` — install extensions from an interactive MG session, not from a run script.
- `madspin` blocks — MadSpin decay insertion is supported but out of this skill's v1 scope.
- `systematics` — inline systematic variations; possible but considered an advanced case; see MG docs if needed.
- NLO brackets (`[QCD]`, `[real=QCD]`) — out of v1 scope.

## Minimal complete example

```
import model sm
generate p p > t t~
output madevent mg_work/ttbar
launch mg_work/ttbar
set nevents 10000
set ebeam1 6500
set ebeam2 6500
0
```

Eight lines. Most variants are a one-line delta on `generate`. See `examples/LO_example.md` for the templated form with value catalog.
