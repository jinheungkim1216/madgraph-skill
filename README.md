# madgraph-skill

A [Claude Code](https://docs.claude.com/en/docs/claude-code) skill for driving [MadGraph5_aMC@NLO](https://launchpad.net/mg5amcnlo) (MG5_aMC) from an LLM without blowing the context window.

MadGraph is a Monte-Carlo event generator for collider physics. A typical run emits 10k–100k lines of stdout that, if piped into an LLM chat, instantly exhausts the token budget. This skill fixes that: all MG output goes to a disk log, the LLM only sees a compact structured summary (cross section, event count, error tail, paths), and the wrappers enforce the discipline automatically.

## What it does

- **Non-interactive MG driver** — runs `mg5_aMC <script.mg5>`, streams stdout/stderr to a log file on disk, emits a ~20-line JSON summary. Archives the exact script + a manifest (MG version, sha256, CLI args, result) per run.
- **Cross-section extraction** — parses the small banner + manifest files in a completed run directory. Never reads `.lhe` event files.
- **Feynman-diagram PDFs** — converts `SubProcesses/P*/matrix*.ps` files into a single aggregated `diagrams/` folder.
- **MG detection** — locates the MG install via `$MG5_HOME` / `$PATH` / CWD glob / home glob, verifies Python + `six` + gfortran + extensions (pythia8, lhapdf6, delphes).
- **Slot-guarded templates** — `.mg5` scripts with unsubstituted `<PLACEHOLDERS>` are rejected before invocation.

## Scope

**v1** covers LO workflows with MG 3.5.x: card authoring, non-interactive execution, shallow cross-section extraction, diagram PDFs. Supports SM, SM restrictions, and arbitrary UFO BSM models.

**Out of scope (v1)**: NLO (`[QCD]`, fixed-order, FKS), multi-jet merging, LHE/HepMC event-file parsing, detector-level analysis. `examples/NLO_example.md` is a reserved slot for when NLO is added.

## Requirements

- **MG5_aMC 3.5.x** installed on the host. See `references/install.md` for the install procedure (Python 3.7+, `six`, gfortran, optional `lhapdf6`/`pythia8`/`Delphes`).
- **Python 3.7+** for the wrapper scripts. No pip dependencies — all scripts are stdlib-only.
- **ghostscript** (`ps2pdf` / `gs`) only if you use `make_diagrams.py`.

## Compatibility

Developed and smoke-tested against **MG 3.5.15 LTS** with Python 3.10 on Linux. Expected to work on any 3.5.x patch release (`run_card` keys, banner format, multiparticle defaults are stable within the 3.5 LTS line).

**Not tested:**
- MG 3.4.x and earlier — some `run_card` keys may be missing or differ.
- MG 3.6.x / 3.7.x — newer releases may change the banner format or add required keys.
- MG 2.9.x LTS — different `.mg5` DSL in places; do not use.

One version-specific note: the 3.5.15 **LTS** distribution does **not** include the `heft` (Higgs effective theory) model, commonly referenced in tutorials. Full MG distributions have it. `sm` + `loop_sm` cover most LO physics without `heft`.

If you hit a `set <key> <value>` failure or banner-parse issue on a non-3.5.15 MG, report the version — regexes in `runs.py` / `run_mg.py` may need loosening.

## Install as a Claude Code skill

Two options. Both make `madgraph` appear in the available-skills list after restarting Claude Code.

### Option A — Claude Code plugin (recommended)

One command inside Claude Code:

```
/plugin install https://github.com/<your-github-user>/madgraph-skill
```

Claude Code reads `.claude-plugin/plugin.json` from the repo root and registers the bundled skill under `skills/madgraph/`. Pulling upstream changes: `/plugin update madgraph`.

### Option B — Manual (no marketplace)

Clone the repo and expose just the skill directory at the standard user-level path:

```
git clone https://github.com/<your-github-user>/madgraph-skill /tmp/madgraph-skill
ln -s /tmp/madgraph-skill/skills/madgraph ~/.claude/skills/madgraph
```

Or project-local (skill active only inside one repo):

```
ln -s /tmp/madgraph-skill/skills/madgraph <your-project>/.claude/skills/madgraph
```

Restart the Claude Code session after either option.

## Post-install

Point the skill at an MG install by setting `MG5_HOME` (see `skills/madgraph/references/install.md` for how to install MG itself):

```
export MG5_HOME=/abs/path/to/MG5_aMC_v3_5_15
```

Verify from within Claude Code — ask something like "check that MadGraph is ready" and the skill should run `detect_mg.py`, reporting version, toolchain, and whether the Python `six` module is available.

## Quick usage

Point the skill at an MG install (once per shell):

```
export MG5_HOME=/abs/path/to/MG5_aMC_v3_5_15
```

Write a `.mg5` script:

```
import model sm
generate e+ e- > mu+ mu-
output madevent /tmp/smoke
launch /tmp/smoke
shower=OFF
detector=OFF
set lep 1000
set nevents 100
0
```

Run (from inside Claude Code, just ask the skill to execute the script — it resolves the path internally). For direct shell use:

```
# If installed as a plugin:
~/.claude/plugins/.../skills/madgraph/scripts/run_mg.py --script smoke.mg5

# If symlinked at ~/.claude/skills/madgraph:
~/.claude/skills/madgraph/scripts/run_mg.py --script smoke.mg5
~/.claude/skills/madgraph/scripts/runs.py --run-dir /tmp/smoke/Events/run_01
```

In practice you don't type these yourself — let Claude invoke them. Summary prints to stdout as JSON, and the full MG log stays on disk.

## Layout

```
.claude-plugin/plugin.json      # Claude Code plugin manifest (enables /plugin install)
README.md                       # this file
skills/
  madgraph/                     # the skill itself
    SKILL.md                    # skill entrypoint (LLM-facing)
    references/
      install.md                # one-time MG install
      setup.md                  # how the skill finds MG (MG5_HOME + fallbacks)
      script-syntax.md          # .mg5 grammar, NLO brackets, scan:[...]
      models.md                 # built-in + UFO models, introspection
      run-card.md               # run_card.dat keys + NLO-only keys
      param-card.md             # masses, widths, compute_widths
      output-and-launch.md      # output/launch internals, NLO launch flow
      troubleshooting.md        # common error messages → cause/fix
      diagrams.md               # Feynman-diagram PDFs (load on demand)
    scripts/
      detect_mg.py              # MG locator + toolchain + six check
      run_mg.py                 # non-interactive MG driver + archive + manifest
      runs.py                   # single-run xsec or multi-run compare with diff
      make_diagrams.py          # SubProcesses/P*/matrix*.ps → <work_dir>/diagrams/
    examples/
      LO_example.md             # templated shapes + value catalog + ttbar walkthrough
      NLO_example.md            # fixed-order NLO QCD workflow + K-factor recipe
```

## Design notes

- **Single `.mg5` script per run** — the archive at `Events/run_XX/inputs/script.mg5` is the authoritative reproducibility record.
- **Work dir derived from script** — the `launch <dir>` line in the `.mg5` determines where MG writes; no CLI flag duplicates this.
- **Hard rules against context floods** — SKILL.md's "Token economy — hard rules" section enforces: never invoke `mg5_aMC` directly, never Read the MG log, never Read LHE/HepMC event files.
- **Progressive disclosure** — granular reference docs loaded only when the relevant topic comes up; the entrypoint stays lean.
