# MadGraph 5 installation

One-time, system-level installation of MG5_aMC@NLO 3.x and its optional extensions. Once this is done, `references/setup.md` covers how this skill hooks into the installed MG. Facts verified against MG 3.5.15 LTS source (smoke-tested end-to-end on this version).

## Prerequisites

**Required for LO:**

- **Python 3.7+** (3.10+ strongly recommended — MG prints a deprecation warning on <3.10 since end of 2025).
- **Python `six` module** — `python -m pip install --user six` if missing.
- **bash**.
- **perl 5.8+**.
- **Fortran 77 compiler** — `gfortran` is standard. Any version works for LO.

**Not supported**: Windows native (even cygwin breaks madevent output). Use WSL if on Windows.

## Install MG

MG is shipped as a tarball — no build step for the core, but Fortran is compiled per-process at `output` time.

1. **Download** the LTS tarball from [launchpad.net/mg5amcnlo](https://launchpad.net/mg5amcnlo) (e.g. `LTS_MG5aMC_v3.5.15.tgz`).
2. **Extract** to a stable location:

   ```
   tar xzf LTS_MG5aMC_v3.5.15.tgz
   # → creates ./MG5_aMC_v3_5_15/
   ```

3. **Point `MG5_HOME` at the extracted directory**:

   ```
   export MG5_HOME=/abs/path/to/MG5_aMC_v3_5_15
   ```

   This is the minimal variable the skill needs. How it's made available across sessions is the user's choice — see `setup.md`.

4. **Verify** the binary works:

   ```
   $MG5_HOME/bin/mg5_aMC --help
   ```

## Optional extensions (`install` from within MG)

For bare parton-level LO with a built-in PDF, **none are needed**. Install only what the analysis demands — each extension adds build time and dependencies.

Launch MG and use its `install` command (downloads + builds into `$MG5_HOME/HEPTools/`):

```
$MG5_HOME/bin/mg5_aMC
MG5_aMC> install lhapdf6
MG5_aMC> install pythia8
MG5_aMC> install Delphes        # requires ROOT, see below
MG5_aMC> install MadAnalysis5
MG5_aMC> exit
```

### Prereqs per extension

| extension | prereqs | when needed |
|---|---|---|
| `lhapdf6` | C++ compiler | any run using `pdlabel = lhapdf` (most realistic LHC runs). Without it, MG uses built-in sets like `nn23lo1`. |
| `pythia8` | C++ compiler, ~2 GB RAM for build | only if the analysis wants showered events. Parton-level xsec does **not** need it. |
| `Delphes` | **CERN ROOT** (external, install separately) + C++ compiler | detector simulation — out of v1 scope. Skip unless ROOT is already on the system; MG's `install` command will download Delphes source but the build/link fails without ROOT. |
| `MadAnalysis5` | Python env only (ROOT needed only for expert mode) | optional, not used by this skill. |

After each install, MG records the path in `$MG5_HOME/input/mg5_configuration.txt`. To use system installs instead of HEPTools-local builds, edit that file (or `~/.mg5/mg5_configuration.txt` for a user-level override):

```
lhapdf_py3 = /usr/bin/lhapdf-config
pythia8_path = /opt/pythia8
```

## Install-time config knobs

`$MG5_HOME/input/mg5_configuration.txt` — relevant entries for installation and resource control. All commented by default; uncomment to change.

| key | default | notes |
|---|---|---|
| `fortran_compiler` | `None` (auto-detect) | Set explicitly if multiple gfortrans are installed. |
| `cpp_compiler` | `None` (auto-detect) | Same idea for extensions that need C++. |
| `run_mode` | `2` | 0=single core, 1=cluster, 2=multi-core. Multi-core is usually best on a workstation. |
| `nb_core` | `None` (all cores) | Cap cores used across MG subprocesses. |
| `timeout` | `60` | Seconds before MG gives up on individual subtasks. Rarely needs changing. |
| `automatic_html_opening` | `True` | Set `False` on headless systems — otherwise MG tries to `xdg-open` results. |
| `auto_update` | `7` | Days between update checks. Set `0` to disable. |

Inside MG, `display options` prints the currently effective values.

## Verify install end-to-end

A minimal process without any extensions:

```
cat > /tmp/mg_install_check.mg5 <<'EOF'
import model sm
generate e+ e- > mu+ mu-
output madevent /tmp/mg_install_check
launch /tmp/mg_install_check
set nevents 100
set ebeam1 500
set ebeam2 500
0
EOF

$MG5_HOME/bin/mg5_aMC /tmp/mg_install_check.mg5
```

Success: MG prints a cross section (~2 pb at 1 TeV e⁺e⁻) and `/tmp/mg_install_check/Events/run_01/unweighted_events.lhe.gz` exists. Expect ~30 seconds.

If this fails, grep the log for `ERROR` / `Fatal` — do not paste the full output into the skill conversation; see SKILL.md token-economy rules.

For the **skill-side** smoke test (verifying the wrappers also work), see `setup.md`.

## File layout after install

```
$MG5_HOME/
├── bin/mg5_aMC                         # entry script (what detect_mg.py looks for)
├── VERSION                             # version string
├── INSTALL                             # authoritative prerequisite list
├── UpdateNotes.txt                     # release notes
├── models/                             # built-in + imported models (sm, loop_sm, …)
├── Template/LO/Cards/                  # default card templates copied into each output
├── input/
│   ├── mg5_configuration.txt           # user-editable config
│   └── multiparticles_default.txt      # defines p, j, l+, l-, vl, vl~
└── HEPTools/                           # populated by `install pythia8 / lhapdf6 / …`
```
