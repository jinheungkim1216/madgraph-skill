# Skill setup

How this skill finds an existing MadGraph install and how a project using the skill is laid out. Installing MG itself is `install.md` — this doc assumes that step is done.

## What the skill requires

Exactly one environment variable:

```
export MG5_HOME=/abs/path/to/MG5_aMC_v3_x_xx
```

Everything else is inferred. How this variable is made available (shell session, project `.env`, wrapper script, Makefile, …) is up to the user — the skill does not prescribe a method.

## How the skill locates MG

Before searching, the scripts load `./.env` (if present) — see "Project-local `.env` file" below. Then `scripts/detect_mg.py` tries, in order:

1. `--mg-root <path>` CLI argument (explicit override — **strict**: fails if the path doesn't contain `bin/mg5_aMC`, does NOT fall through).
2. `$MG5_HOME` environment variable.
3. `mg5_aMC` on `$PATH` (via `which`).
4. Glob: `./MG5_aMC*/bin/mg5_aMC` relative to the **current working directory** (project-local installs — useful when the tarball is extracted inside the repo).
5. Glob: `~/MG5_aMC*/bin/mg5_aMC`, `/opt/MG5_aMC*/bin/mg5_aMC`.

The first successful hit wins. Call `detect_mg.py` once per session and cache its summary; it is not a cheap probe (inspects version, available extensions, compilers).

If none of 1–5 resolve, the output carries a `searched` list showing every strategy tried and a `remedies` list with copy-pasteable commands. Point the user at `install.md` if MG is not yet installed.

## Project-local `.env` file

Instead of polluting your shell with `export MG5_HOME=...`, drop a `.env` file at the **current working directory** (usually your project root). The skill's wrappers load it automatically:

```
# ./.env  — add this to your project's .gitignore
MG5_HOME=/abs/path/to/MG5_aMC_v3_5_15
CCACHE_DISABLE=1        # NLO compile workaround if ccache tmp is read-only
```

Format: one `KEY=VALUE` per line; `#` comments allowed; optional matching `"` / `'` around values. **The shell environment always wins** — values already set in `os.environ` are never overridden, so your existing exports keep priority over `.env`.

Output fields in detect_mg/run_mg/make_diagrams summaries include `env_file_loaded: <path>` when a `.env` was picked up; `null` otherwise.

## Work directory convention

MG's `output` creates a process tree hundreds of MB in size. Keep these outside the repo root:

- **Default**: `./mg_work/<proc_name>/` (relative to project root).
- `run_mg.py` creates the work dir if missing.
- Each run's inputs + summary are archived under `<work_dir>/Events/run_XX/inputs/` for reproducibility — the authoritative per-run record.

Add this to `.gitignore`:

```
# .gitignore
mg_work/
# If the extracted MG lives inside the project (it usually shouldn't):
MG5_aMC_v*/
HEPTools/
```

## Smoke test (skill wrappers work end-to-end)

Verifies the skill's wrapper chain on top of an already-installed MG. Assumes `MG5_HOME` is set.

```
cat > /tmp/skill_smoke.mg5 <<'EOF'
import model sm
generate e+ e- > mu+ mu-
output madevent /tmp/mg_work/smoke
launch /tmp/mg_work/smoke
set nevents 100
set ebeam1 500
set ebeam2 500
0
EOF

scripts/detect_mg.py
scripts/run_mg.py --script /tmp/skill_smoke.mg5
scripts/runs.py --run-dir /tmp/mg_work/smoke/Events/run_01
```

Success criteria:

- `detect_mg.py` prints a YAML block with `mg_root`, `version`, and extension status.
- `run_mg.py` returns `status: ok`, a non-empty `xsec_pb`, and `script_archive: /tmp/mg_work/smoke/Events/run_01/inputs/script.mg5`.
- `runs.py --run-dir …` echoes the same `xsec_pb` value.

If `run_mg.py` fails, check `errors_tail` in its summary before touching the log — see SKILL.md token-economy rules. Never paste the MG log back into the conversation.

## Never call `mg5_aMC` directly from the skill

Even in smoke tests or quick checks, go through `scripts/run_mg.py`. The wrapper enforces:

- Full stdout/stderr redirection to `mg_run.log` on disk (10k+ lines per run otherwise flood the conversation).
- Per-run `inputs/script.mg5` archive + `run_manifest.yaml`.
- Slot guard: scripts containing unsubstituted `<PLACEHOLDERS>` are rejected before invocation.

For `mg5_aMC` invocations that predate the wrappers (e.g., the smoke test in `install.md`), still redirect output to a file and grep afterward:

```
$MG5_HOME/bin/mg5_aMC /tmp/check.mg5 > /tmp/mg.log 2>&1
# then Grep /tmp/mg.log — never `cat` it whole.
```

## Where `MG5_HOME` is NOT set

If a user runs the skill without setting `MG5_HOME` and MG isn't on `PATH`, `detect_mg.py` will fall through all four resolution steps and report `status: not_found`. At that point:

- If MG is installed somewhere the user knows: export `MG5_HOME` or pass `--mg-root`.
- If MG is not installed: read `install.md`.
