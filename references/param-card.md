# `param_card.dat` (model parameters, accessed via `set`)

Sets physical parameters of the loaded model — masses, widths, couplings, CKM entries, BSM input parameters. Written by MG based on the model at `output` time, edited via `set` commands in `.mg5` scripts.

Do **not** hand-edit `param_card.dat`. The archived `Events/run_XX/inputs/script.mg5` is the reproducibility record; drive everything through `set`.

## File structure (SLHA-style)

```
Block SMINPUTS                       # named block
     1   1.32506980E+02   # alpha_em(MZ)^(-1)
     3   1.18000000E-01   # alpha_s(MZ)
     4   9.11880000E+01   # M_Z

Block MASS                           # particle kinematic masses
     5   4.70000000E+00   # b quark
     6   1.74300000E+02   # top
    23   9.11880000E+01   # Z
    24   8.04190000E+01   # W
    25   1.20000000E+02   # Higgs

DECAY    6   1.50833649E+00   # top width
DECAY   23   2.44140351E+00   # Z width
DECAY   24   2.04759951E+00   # W width
DECAY   25   5.75308848E-03   # Higgs width
```

Rows inside a block: `<id1> [<id2> …]   <value>   # comment`. For `MASS` and `DECAY`, the `id` is the particle's PDG code.

## `set` syntax for param_card

Three forms, matched in this order:

```
set <block> <id> <value>          # e.g., set mass 6 172.5
set <particle_name> <value>       # e.g., set mass top 172.5  (MG maps name → PDG)
set <param_name> <value>          # e.g., set aewm1 137.035   (unique block-1 param)
```

For widths, use the block name `decay` (lowercase):

```
set decay 6 1.42             # set top width to 1.42 GeV
set decay 25 auto            # compute Higgs width automatically (see below)
```

## `compute_widths` (MG command, not a `set`)

MG can compute a particle's width on the fly from the tree-level partial widths in the model. Use instead of hand-setting when widths depend on other parameters you just changed.

```
launch mg_work/ttbar
set mass 25 125.0          # change Higgs mass
set decay 25 auto          # ← "auto" triggers compute_widths internally
0
```

Equivalently, call `compute_widths` before `launch` (inside the script, before or after `output`):

```
import model sm
compute_widths 25 23          # compute h, Z widths at load time
generate p p > h j j
output madevent mg_work/vbf_h
launch mg_work/vbf_h
0
```

`compute_widths all` computes for every unstable particle. Slow but safe.

## SM parameters worth knowing (defaults from `sm` model)

### `Block SMINPUTS`

| id | param | default | notes |
|---|---|---|---|
| 1 | 1/α_em(M_Z) | 132.507 | |
| 2 | G_F (Fermi) | 1.166·10⁻⁵ | |
| 3 | α_s(M_Z) | 0.118 | |
| 4 | M_Z | 91.188 GeV | |

### `Block MASS` (PDG code → mass in GeV)

| PDG | particle | default |
|---|---|---|
| 1 / 2 / 3 | d / u / s | 0 (massless) |
| 4 | c | 0 in default `sm`; nonzero with `-c_mass` |
| 5 | b | 4.70 |
| 6 | t | 174.3 |
| 11 / 13 / 15 | e⁻ / μ⁻ / τ | 0 / 0 / 1.777 |
| 12 / 14 / 16 | ν_e / ν_μ / ν_τ | 0 |
| 22 | photon | 0 |
| 23 | Z | 91.188 |
| 24 | W | 80.419 |
| 25 | h | 120.0 (**not** 125 — update for realistic studies) |

Common edits:

```
set mass 6 172.5              # top pole mass
set mass 25 125.0             # Higgs mass (physical value)
```

### `DECAY` (widths in GeV)

| PDG | particle | default |
|---|---|---|
| 6 | t | 1.508 |
| 23 | Z | 2.441 |
| 24 | W | 2.048 |
| 25 | h | 0.00575 |

Updating one of these is usually paired with a corresponding mass update — use `auto` / `compute_widths` to keep them consistent.

### `Block MGYUKAWA` (Yukawa-sector masses — independent from pole masses)

Used when the Yukawa coupling depends on a running mass different from the pole mass. Usually leave as-is.

| id | param | default |
|---|---|---|
| 5 | m_b in y_b | 4.20 |
| 4 | m_c in y_c | 1.42 |
| 6 | m_t in y_t | 164.5 |
| 15 | m_τ in y_τ | 1.777 |

### `Block MGCKM`

CKM matrix entries — only present when the model restriction keeps them (`sm-ckm` / `sm-zeromass_ckm`).

## BSM / UFO parameters

UFO models define additional blocks (e.g., `FRBlock`, `NPBLOCK`, model-specific names). Get the list with:

```
import model /path/to/MyModel_UFO
display parameters            # all external + internal parameters
```

`display parameters` prints the block-and-id structure. Then:

```
set <block_name> <id> <value>
```

UFO-specific defaults should never be inferred — always set explicitly when the physics depends on them.

## Restriction cards (at model import time)

Some parameters are frozen at `import model` time via `restrict_<name>.dat` (see `models.md`). Attempting to `set` a frozen parameter produces a warning. To un-freeze, re-import without the restriction.

Common frozen-by-restriction parameters:

| restriction | freezes |
|---|---|
| `sm` default | CKM ≈ identity, some Yukawa couplings = 0 |
| `sm-no_b_mass` | `mass 5` = 0 |
| `sm-no_widths` | every `DECAY` = 0 |
| `sm-no_tau_mass` | `mass 15` = 0 |

## What NOT to edit via `set`

- `Block LOOP` or `Block LOOPSCALES` (loop_sm) — MG-managed, usually safe as defaults.
- Block entries marked `DEPENDENT` in the UFO — computed from other parameters; setting them is ignored.
- Entries that the model computes from others (MG displays these with `DECAY` + `AUTO` in `display parameters`).

## Quick recipe cards

### Realistic SM point

```
set mass 6 172.5
set mass 25 125.0
set decay 25 auto
set aewm1 132.507     # 1/α_em(M_Z), optional — default is same
set asmz 0.118        # α_s(M_Z), optional — default is same
```

### On-shell production only (widths off)

Prefer the `-no_widths` restriction at `import model` time over setting every `DECAY` to zero by hand.

### After changing a mass, always

```
set mass <pdg> <new_value>
set decay <pdg> auto      # re-compute width for consistency
```
