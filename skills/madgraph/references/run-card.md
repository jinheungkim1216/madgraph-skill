# `run_card.dat` keys (accessed via `set` in `.mg5` scripts)

MG generates a `run_card.dat` inside each process's `Cards/` directory. Every parameter shown below is settable from a `.mg5` script with `set <key> <value>` between a `launch` line and its terminating `0`. MG validates the key and value.

Do **not** hand-edit `run_card.dat` — drive everything through `set`. The archived `Events/run_XX/inputs/script.mg5` is then the single source of truth.

The default `run_card.dat` only shows the most-common keys. To see the full set inside MG, type `update to_full` at the interactive prompt (or `help set`).

**LO vs NLO run_card**: MG ships two templates (`Template/LO/Cards/` and `Template/NLO/Cards/`). Most keys below apply to both; NLO-specific keys are grouped in the [NLO-only](#nlo-only-keys) section at the end.

## Essentials

| key | default | meaning |
|---|---|---|
| `run_tag` | `tag_1` | Short label for this run. Appears in Events filenames. |
| `nevents` | `10000` | Unweighted events to generate. **Do not exceed 1M per single run** — MG warns about this. Split large samples into multiple runs. |
| `iseed` | `0` | RNG seed. `0` = auto-pick. Fix for reproducibility. |

## Beams

| key | default | meaning |
|---|---|---|
| `lpp1` / `lpp2` | `1` / `1` | Beam 1 / beam 2 type. `1`=proton, `-1`=antiproton, `0`=no PDF (lepton), `2`=elastic photon of proton/ion, `±3`=e⁺/e⁻ PDF, `±4`=μ⁺/μ⁻ PDF. |
| `ebeam1` / `ebeam2` | `6500` / `6500` | Beam energy in GeV (total, not √s). LHC13 = 6500 each; LHC14 = 7000 each. |

### Symmetric-beam shortcuts

MG expands single-name aliases to both beams, so symmetric setups are one line:

| alias | expands to | example |
|---|---|---|
| `set ebeam <V>` | `ebeam1 = ebeam2 = V` | `set ebeam 6500` |
| `set lpp <V>` | `lpp1 = lpp2 = V` | `set lpp 1` |
| `set lhc <√s TeV>` | `lpp1=lpp2=1`, `ebeam1=ebeam2=√s*1000/2` | `set lhc 13` → LHC 13 TeV pp |
| `set lep <√s GeV>` | `lpp1=lpp2=0`, `ebeam1=ebeam2=√s/2` | `set lep 91.2` → Z-pole e⁺e⁻ |
| `set ilc <√s GeV>` | same as `lep` | |

Asymmetric setups (e.g., HERA, forward experiments) still require explicit `ebeam1`/`ebeam2` pairs.

## PDF

| key | default | meaning |
|---|---|---|
| `pdlabel` | `nn23lo1` | PDF set shortcut. `lhapdf` → use LHAPDF (needs install), `nn23lo1`/`nn23nlo` → built-in NNPDF 2.3, `iww`/`eva`/`edff`/`chff` → photon-flux approximations, `none` → no PDF (point-like). |
| `lhaid` | `230000` | LHAPDF id — used **only** when `pdlabel=lhapdf`. `260000`=NNPDF31_lo_as_0118, `303400`=NNPDF31_nnlo_as_0118, CT18/MSHT variants also available. |

## Scales

| key | default | meaning |
|---|---|---|
| `fixed_ren_scale` | `False` | `True` → use constant μ_R = `scale`; `False` → use dynamical. |
| `fixed_fact_scale` | `False` | Same for μ_F (`dsqrt_q2fact1`/`dsqrt_q2fact2`). |
| `scale` | `91.188` | Fixed μ_R in GeV. |
| `dsqrt_q2fact1` / `dsqrt_q2fact2` | `91.188` | Fixed √(μ_F²) per beam, GeV. |
| `dynamical_scale_choice` | `-1` | Dynamical scale preset: `-1`=auto, `1`=H_T/2, `2`=sum of final-state transverse masses, `3`=event-by-event (m_T, pT), `4`=√ŝ. |
| `scalefact` | `1.0` | Multiplicative factor on all scales (for scale-variation studies). |

Shortcut: `set fixed_scale <V>` turns on both fixed flags and sets `scale = dsqrt_q2fact1 = dsqrt_q2fact2 = V` in one line.

## Kinematic cuts (applied before event generation — tighter cuts = faster)

Prefix meaning: `pt` = transverse momentum, `eta` = pseudorapidity, `dr` = ΔR distance, `mm` = invariant mass. Each cut has a `min` form (the unsuffixed key) and a `max` form (with `max` suffix).

### Single-particle pT (GeV)

```
set ptj 20            # min pT for any jet
set ptb 0             # min pT for any b-jet
set pta 10            # min pT for any photon
set ptl 10            # min pT for any charged lepton
set misset 0          # min missing ET (sum of neutrino pT)
```

`ptjmax`, `ptlmax`, etc. for upper limits. Per-PDG overrides: `pt_min_pdg = {6: 100, 25: 50}` (top pT > 100, h pT > 50) — use Python dict syntax as a string.

### Pseudorapidity

```
set etaj 5.0          # max |η| for jets
set etab -1           # max |η| for b-jets (-1 = no cut)
set etaa 2.5          # max |η| for photons
set etal 2.5          # max |η| for leptons
set etajmin 0         # min |η| (rarely useful)
```

### Angular separation ΔR

```
set drjj 0.4          # min ΔR between jets
set drll 0.4          # min ΔR between leptons
set draa 0.4          # min ΔR between photons
set drjl 0            # min ΔR between jet and lepton
```

Also `drbb`, `draj`, `drbj`, `drab`, `drbl`, `dral`, and `max` variants.

### Invariant mass (GeV)

```
set mmjj 0            # min m(j,j)
set mmll 0            # min m(l+l-) same flavor
set mmaa 0            # min m(γγ)
set mmllmax 1e10      # max m(l+l-)
```

Per-pair overrides: `mxx_min_pdg = {6: 250}` (m(t t~) > 250). `mxx_only_part_antipart = True` restricts to particle/antiparticle pairs only.

### Heavy-flavor / "leading" cuts

```
set ptheavy 0         # min pT for at least one heavy final state
set xptj 0            # min pT for at least one jet (at least one passes)
set cutuse 0          # 0 = reject if ANY jet fails pt cut; 1 = reject only if ALL fail
```

### HT-like cuts

```
set htjmin 0          # min sum(jet pT)
set htjmax 1e10
set ihtmin 0          # inclusive HT over all partons incl. b
```

### VBF-specific (WBF)

```
set xetamin 0         # min |η| for the two forward jets
set deltaeta 0        # min Δη between the two forward jets  
                      # (typical VBF selection: xetamin=2, deltaeta=4)
```

### Frixione photon isolation (when process has final-state γ)

```
set ptgmin 10
set r0gamma 0.4
set xn 1
set epsgamma 1.0
```

## Multi-parton conventions

| key | default | meaning |
|---|---|---|
| `maxjetflavor` | `4` | PDG cutoff for what counts as "jet" in `j` label & MLM matching. `4` → j = u,d,c,s,g (no b). `5` → includes b. |
| `bwcutoff` | `15.0` | Breit-Wigner window (Γ units) around on-shell mass — used in diagram pruning. |
| `cut_decays` | `False` | Apply the above cuts to decay products too (not only to core process partons). |

## Event-generation tuning (rarely changed)

| key | default | meaning |
|---|---|---|
| `nhel` | `0` | `0` = sum all helicities, `1` = Monte-Carlo over helicities (faster for high-multiplicity). |
| `sde_strategy` | `1` or `2` (process-dependent) | Integration strategy — auto-chosen, override only if you know why. |
| `gridpack` | `False` | Build a gridpack for fast re-generation. |
| `time_of_flight` | `-1` | mm threshold for writing particle lifetime in LHE. `-1` = off. |
| `dsqrt_shat` | `0` | Minimum √ŝ cut on the full process (GeV). |

## Systematics (scale / PDF variations)

Most practical path: enable once, MG re-weights on the fly.

```
set use_syst True
set systematics_program systematics
set systematics_arguments ['--mur=0.5,1,2', '--muf=0.5,1,2', '--pdf=errorset']
```

Keys:

| key | meaning |
|---|---|
| `use_syst` | Master switch for systematics on/off. |
| `systematics_program` | `systematics` (Python, default), `none`, or `SysCalc` (deprecated). |
| `systematics_arguments` | List of flags forwarded to the systematics script. See MG wiki for full options. |

Variations land in the LHE event weights; parse them downstream with whatever analysis tool consumes the sample (out of v1 scope).

## Presets as `set` blocks

Drop these into the `<SET_BLOCK>` slot of a template from `examples/LO_example.md`.

### LHC13 quick (smoke test, ~1 min)

```
set lhc 13
set nevents 1000
```

### LHC13 default (10k events, NNPDF via LHAPDF)

```
set lhc 13
set nevents 10000
set pdlabel lhapdf
set lhaid 260000
```

### LHC14 default

```
set lhc 14
set nevents 10000
set pdlabel lhapdf
set lhaid 260000
```

### Scale-variation sanity check (add to any preset)

```
set use_syst True
set systematics_program systematics
set systematics_arguments ['--mur=0.5,1,2', '--muf=0.5,1,2']
```

## How MG validates `set`

- Unknown key → MG halts with `"Invalid parameter name"`. `run_mg.py` surfaces this as `status: error`.
- Out-of-range value (e.g., negative `ebeam1`) → warning, value may be clamped.
- Type mismatch (string where a number is expected, or vice versa) → halt.

For the full key list including rare options, run MG interactively and type `update to_full` — it rewrites `run_card.dat` with every knob exposed.

## NLO-only keys

Written to `run_card.dat` only when the process has an NLO bracket (`[QCD]` etc.). Many keys overlap with LO (`nevents`, `ebeam1/2`, `ptj`, `etaj`, `pdlabel`, `lhaid`, …); the keys below are additions or have NLO-specific semantics.

### Integration and accuracy

| key | default | meaning |
|---|---|---|
| `req_acc` | `-1` | Required relative accuracy on the NLO xsec. `-1` → auto-derive from `nevents`. Fixed-order xsec calculation keeps refining until this is met. Lowering below `-1` auto-default (e.g. `0.01`) → more integration time, lower MC error. |
| `npoints_fo` | `10000` | Points per iteration in fixed-order integration. Rarely touched. |
| `niters_fo` | `6` | Number of integration iterations. Rarely touched. |
| `folding` | `1,1,1` | Folding parameters for the FKS subtraction variables (ξᵢ, yᵢⱼ, φᵢ). Defaults are fine unless debugging negative-weight events. |

### Parton shower matching (MC@NLO)

Used only when `fixed_order=OFF` (out of v1 scope for event generation, but the keys persist in the card).

| key | default | meaning |
|---|---|---|
| `parton_shower` | `HERWIGPP` | Which PS the NLO subtraction terms target. Options: `HERWIG6`, `HERWIGPP`, `PYTHIA6Q`, `PYTHIA6PT`, `PYTHIA8`. Must match the shower you plan to run. |
| `shower_scale_factor` | `1.0` | Multiply default shower-starting scale. |
| `mcatnlo_delta` | `False` | Use MC@NLO-Δ matching (arXiv:2002.12716). Requires Pythia 8.309+. |
| `ickkw` | `0` | Multi-jet NLO merging: `0`=none, `3`=FxFx, `4`=UNLOPS, `-1`=NNLL+NLO jet-veto. v1 supports `0` only. |

### Scales and PDF reweighting

NLO uses its own scale keys (`muR_ref_fixed`, `muF_ref_fixed`) instead of LO's `scale` / `dsqrt_q2fact*`.

| key | default | meaning |
|---|---|---|
| `muR_ref_fixed` | `91.188` | Fixed renormalization reference scale (GeV), when `fixed_ren_scale=True`. |
| `muF_ref_fixed` | `91.188` | Fixed factorization reference scale (GeV), when `fixed_fac_scale=True`. |
| `muR_over_ref` | `1.0` | Ratio of current μ_R over the reference — scan-friendly. |
| `muF_over_ref` | `1.0` | Ratio of current μ_F over the reference. |
| `dynamical_scale_choice` | `[-1]` | List (NLO can carry multiple for reweighting). `-1`=HT/2, `10`=total transverse mass, etc. Additional choices beyond the first are included as LHE reweights. |
| `rw_rscale` | `[1.0, 2.0, 0.5]` | μ_R factors to include as on-the-fly reweights. |
| `rw_fscale` | `[1.0, 2.0, 0.5]` | μ_F factors. |
| `reweight_scale` | `[True]` | Per-dynamical-choice booleans — which scale variations to run. |
| `reweight_pdf` | `[False]` | Per-PDF booleans — which sets to compute PDF uncertainties for. |
| `store_rwgt_info` | `False` | Embed reweight metadata into the LHE for later off-line use. |

### FastJet (mandatory at NLO)

NLO has IR divergences canceling between real and virtual; jet clustering must be defined. LO treats these as optional cuts.

| key | default | meaning |
|---|---|---|
| `jetalgo` | `-1` | FastJet algorithm: `1`=kT, `0`=C/A, `-1`=anti-kT. Anti-kT is standard at LHC. |
| `jetradius` | `0.4` | Jet radius R. LHC convention: 0.4 for most, 0.8 for boosted. |

### Lepton / photon NLO extras

| key | default | meaning |
|---|---|---|
| `drll` / `drll_sf` | `0.4` / `0.4` | Min ΔR between opp-sign leptons / opp-sign same-flavor leptons. |
| `mll` / `mll_sf` | `30` / `30` | Min m(ℓ⁺ℓ⁻) / same-flavor variant. |
| `gamma_is_j` | `False` | Cluster photons with jets (if False, photons go through isolation). |
| `Rphreco` | `0.1` | Fermion–photon recombination radius. `0` = disabled. |
| `etaphreco` | `-1` | Max \|η\| for photons eligible for recombination. |
| `lepphreco` / `quarkphreco` | `True` / `True` | Whether to recombine photons with leptons / quarks. |

### Frixione photon isolation (NLO form)

| key | default | meaning |
|---|---|---|
| `ptgmin` | `0` | Min photon pT. `0` → all photon cuts off. |
| `etagamma` | `-1` | Max \|η\| for photons. |
| `R0gamma` | `0.4` | Isolation cone radius. |
| `xn` | `1` | Frixione profile exponent (eq. 3.4 of hep-ph/9801442). |
| `epsgamma` | `1.0` | Energy-fraction parameter. |

### `fixed_order` interactive switch (launch, not run_card)

Not a `run_card` key — it's a `launch` mode flag. `fixed_order=ON` → skip MC matching, produce only the NLO fixed-order xsec + histograms. This is what v1 supports. `fixed_order=OFF` → enables MC@NLO event generation path (requires `parton_shower` target and pythia8 install).
