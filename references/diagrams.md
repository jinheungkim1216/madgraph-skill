# Feynman-diagram generation

For when the user wants to **see diagrams** for a process — not cross sections, not events. Uses `scripts/make_diagrams.py`.

## `.mg5` script shape

Three lines, no `launch`, no `set`, no trailing `0`:

```
import model sm
generate p p > t t~
output madevent mg_work/ttbar_diag
```

`<MODEL>` and `<PROCESS>` follow the same catalog as `examples/LO_example.md`. Output path (`mg_work/<name>`) is where MG writes `SubProcesses/P*/matrix*.ps` files.

## Run

```
scripts/make_diagrams.py --script ttbar_diagrams.mg5
```

After MG completes, the script scans every `SubProcesses/P*/matrix*.ps` (there can be many subprocesses, each with multiple PS files) and converts each to PDF.

## Output layout

PDFs land in **one aggregated folder**:

```
<work_dir>/diagrams/<subprocess>__<matrix_name>.pdf
```

Example: `mg_work/ttbar_diag/diagrams/P1_gg_ttx__matrix3.pdf`. Original `SubProcesses/P*/matrix*.ps` files are left untouched.

Summary JSON from the wrapper reports `diagrams_dir` (the aggregated folder) and a per-subprocess breakdown with `pdf_count` and diagram filenames.

## Skip MG (convert existing output)

When the process was already `output`-ed (either by a previous `run_mg.py` run or a prior `make_diagrams.py`), skip re-running MG:

```
scripts/make_diagrams.py --work-dir mg_work/ttbar
```

Only converts existing `matrix*.ps` files. No MG invocation.

## Prerequisites

- `ps2pdf` (ships with ghostscript) on `PATH`, or
- `gs` (ghostscript) as fallback.

Both absent → wrapper reports `status: error` with "neither ps2pdf nor gs on PATH — install ghostscript".

## Not covered

- **Merging into a single PDF**: `make_diagrams.py` produces one PDF per diagram. To merge, use `pdfunite` or `gs -sDEVICE=pdfwrite -o all.pdf diagrams/*.pdf` manually.
- **Custom diagram styling**: MG's `set` options for PS rendering (colors, Feynman-rule variants) — out of scope; the PS files use MG defaults.
