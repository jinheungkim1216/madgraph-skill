# Models (built-in, restricted, UFO)

Choosing the right model is the first decision in any `.mg5` script — it fixes the particle content, coupling structure, and available multiparticle labels. Always `import model` before `generate`.

## Built-in models (MG 3.5.15 LTS distribution)

Confirmed present in `$MG5_HOME/models/`:

| name | purpose | when to use |
|---|---|---|
| `sm` | Standard Model, default restriction. First two quark generations massless; b, t, leptons and gauge bosons keep PDG masses. | Default for any tree-level SM process. |
| `loop_sm` | SM extended to support loop amplitudes. | **Required** for loop-induced LO processes (`[noborn=QCD]`) like `g g > h`. Slightly slower to load but functionally equivalent to `sm` at tree level. |
| `MSSM_SLHA2` | Minimal SUSY, SLHA2 conventions. | MSSM studies. |
| `hgg_plugin` | Hgg effective coupling plugin. | Niche. |
| `taudecay_UFO` | τ decay model. | Used with MadSpin; skip in v1. |

Notably **not in this distribution**: `heft` (Higgs effective theory, common for `g g > h` tree-level), `sm_ckm`, `2HDMtII`, etc. If a user's workflow expects `heft` or another model, they must drop the UFO tree into `$MG5_HOME/models/<name>/` or supply an absolute path. See "UFO models" below.

## SM restrictions — `sm-<restriction>`

A restriction card freezes some parameters to exact values (usually zero) at load time. Speeds up diagram generation and clarifies physics intent. Present in `models/sm/`:

| suffix | effect |
|---|---|
| `default` | applied automatically when you say `import model sm` |
| `no_b_mass` | sets m_b → 0. Use when b-initial-state contributions aren't physically relevant (most LHC tree-level). |
| `no_widths` | sets all widths → 0. Use for on-shell production only (no resonant s-channel). |
| `no_masses` | sets all particle masses → 0. Use for QCD-like toy studies. |
| `no_tau_mass` | sets m_τ → 0. |
| `lepton_masses` | inverse: keeps lepton masses non-zero (not the default). |
| `c_mass` | keeps m_c non-zero. |
| `ckm` | uses a non-diagonal CKM matrix (default SM has identity CKM). |
| `zeromass_ckm` | CKM with massless quarks. |

Syntax:

```
import model sm-no_b_mass
```

`loop_sm` has the same suffixes plus `test`, `parallel_test`, `cms`.

**Rule of thumb**: start with plain `sm`. Only add a restriction when you know why.

## UFO models (BSM)

UFO (Universal FeynRules Output) is a Python-directory format describing particles, parameters, Lagrangian vertices, and coupling orders. Any BSM model exportable from FeynRules, SARAH, or similar can be imported.

### Importing

```
# By absolute or relative path
import model /abs/path/to/MyModel_UFO

# If the UFO lives under $MG5_HOME/models/
import model MyModel
```

MG looks for the UFO directory in `$MG5_HOME/models/` first; anything else needs an explicit path. Subdirectory name = model name MG uses internally.

UFOs often ship multiple restriction files (`restrict_<name>.dat`). Apply with the same suffix syntax: `import model MyModel-no_b_mass`.

### Introspection — do this BEFORE writing the process

UFO particle labels, coupling orders, and parameter names differ from SM. Writing a `generate` line by guessing will either fail or (worse) silently select the wrong diagrams. After `import model`, query the model:

```
import model /path/to/MyModel_UFO
display particles                   # all particle labels + PDG codes
display multiparticles              # any custom multiparticle shortcuts
display couplings                   # coupling hierarchies (QCD, QED, NP, ...)
display interactions                # 3-point and 4-point vertices
display parameters                  # all external/internal parameters
```

`run_mg.py` captures this output to the log file like any other MG output — use Grep on `log_path` to extract a specific table.

### Coupling-order hierarchy

Every UFO defines a set of coupling *orders* (e.g., `QCD`, `QED`, `NP` for new-physics). The `generate` line can constrain these:

```
generate p p > zp > l+ l- NP=2 QED=0 QCD=0     # NP-only amplitude
generate p p > zp > l+ l- NP<=2                # allow SM+NP interference
```

Omitting orders lets MG pick the default minimum that makes the amplitude non-zero. Always set orders explicitly for BSM — the default is rarely what you want when multiple coupling types overlap.

### Widths — `compute_widths`

BSM particles usually ship with default widths = 0 or placeholder values. Compute widths at load time (after import, before `generate` if widths affect channel selection):

```
import model /path/to/MyModel_UFO
compute_widths 9000001 9000002      # PDG codes of particles to compute
# or
compute_widths all
```

`compute_widths` adds entries to `param_card.dat` that subsequent runs reuse. See `param-card.md`.

### Restriction cards for UFOs

If the UFO ships `restrict_no_b_mass.dat`, you can do `import model MyModel-no_b_mass` — same as SM. Some UFO authors ship numerical restriction cards (e.g., `restrict_CPV.dat`) that fix specific BSM parameters. Check the UFO's own README.

## SM particle name reference

For writing `generate` / `define` lines without guessing. Source: `models/sm/particles.py`.

| kind | names |
|---|---|
| gauge | `g`, `a` (photon), `Z`, `W+`, `W-` |
| quarks | `u`, `d`, `c`, `s`, `b`, `t` and antiquarks `u~`, `d~`, `c~`, `s~`, `b~`, `t~` |
| charged leptons | `e-`, `e+`, `mu-`, `mu+`, `ta-`, `ta+` |
| neutrinos | `ve`, `vm`, `vt`, and antis `ve~`, `vm~`, `vt~` |
| Higgs | `h` |
| ghosts (internal) | `ghA`, `ghZ`, `ghWp`, `ghWm`, `ghG` — do not appear in physical processes |

Built-in multiparticles (from `$MG5_HOME/input/multiparticles_default.txt`):

- `p`, `j` = `g u c d s u~ c~ d~ s~` (no b by default)
- `l+` = `e+ mu+`, `l-` = `e- mu-` (no τ)
- `vl` = `ve vm vt`, `vl~` = `ve~ vm~ vt~`

To include b in jets: `define p = g u c d s b u~ c~ d~ s~ b~` before `generate`.

## Model-choice quick map

| scenario | model |
|---|---|
| LHC tree-level SM (ttbar, DY, dijet, VBF, VH, …) | `sm` |
| Above but faster and b initial state irrelevant | `sm-no_b_mass` |
| `g g > h` and similar loop-induced at LO | `loop_sm` + `[noborn=QCD]` |
| MSSM study | `MSSM_SLHA2` |
| Custom BSM | external UFO, imported by path |

See `examples/LO_example.md` for ready-to-edit shapes in each case.
