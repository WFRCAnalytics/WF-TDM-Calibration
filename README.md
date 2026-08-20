# TDM Calibration

Calibration scripts, configs, and targets for the
[TDM](https://github.com/WFRCAnalytics/WF-TDM-Development) model. The TDM itself is
included as a **pinned git submodule** at `tdm/` — this repo never floats to the latest
TDM commit automatically, so every calibration result is tied to a specific,
reproducible TDM version.

Running a calibration iteration end to end (sync the TDM to the right version, render
its Control Center, invoke Cube Voyager, curate outputs) is handled by `tdmcalib`, a
CLI ported into this repo from the sibling
[WF-TDM-Runs](https://github.com/WFRCAnalytics/WF-TDM-Runs) repo's orchestration
framework — flattened from its `run_set`/`scenario` model down to a single axis: a
series of calibration runs (`C50`, `C51`, ...), each independently re-runnable. See
"Running a calibration iteration" below.

## Setup

```bash
git clone https://github.com/WFRCAnalytics/WF-TDM-Calibration.git
cd WF-TDM-Calibration
./setup.sh
```

`setup.sh` runs `git submodule update --init --recursive` and prints the exact TDM
commit you're now pinned to. If you'd rather do it by hand:

```bash
git submodule update --init --recursive
```

Then, for running calibrations (not needed just to browse/edit configs) — dependency
management is via [uv](https://docs.astral.sh/uv/), which creates and manages `.venv`
from `pyproject.toml`/`uv.lock`:

```bash
uv sync --extra dev
cp config/local.example.yaml config/local.yaml   # fill in Voyager_EXE for this machine
uv run tdmcalib validate-config
```

`uv run <command>` runs a command inside `.venv` without activating it; activate it the
usual way (`.venv\Scripts\activate` / `source .venv/bin/activate`) if you'd rather run
`tdmcalib`/`pytest` directly. Add `--extra reports` to `uv sync` for the packages
`report/`'s Quarto reports need beyond the base dependencies (see `report/README.md`).

For rendering `report/` locally, one file is too large for git (142MB, over GitHub's
100MB limit) and isn't committed — copy it in manually before rendering:

```bash
cp "F:\SHARED\Chris\large_files_calibration\v1000\UT_HTS_2023_Linked_Trips.csv" inputs/
```

## Repo layout

| Path                | Contents                                                  |
|---------------------|-------------------------------------------------------------|
| `tdm/`              | TDM submodule — **do not edit directly** (see below)         |
| `config/`           | `tdmcalib` framework settings (`framework.yaml`, `local.yaml` — gitignored, copy from `local.example.yaml`), JSON schemas |
| `calibration_runs/` | One YAML per calibration run (`C50.yaml`, ...) — `tdm_ref`, `control_center_overrides`/`general_parameter_overrides`, `outputs.include` |
| `runs/`             | `tdmcalib`'s curated, committed output, one folder per calibration run (`runs/{calib_run_id}/`) — curated files sit directly in that folder; `run_info/{run_id}.json` holds a permanent, never-deleted metadata record for every attempt |
| `src/tdmcalib/`      | The orchestrator CLI itself |
| `bin/`              | `RunModel.bat` — the Cube Voyager entry point `tdmcalib` invokes |
| `tests/`            | `pytest` suite for `src/tdmcalib/` |
| `inputs/`           | Calibration targets, counts, survey data                 |
| `report/`           | Quarto calibration reports (one file per stage, each covering every calibration run via an in-page selector), published to GitHub Pages — see `report/README.md` |

`scripts/` (calibration scripts) and `configs/` (their parameter/target configs) don't
exist yet — create them when actually needed, not speculatively.

## Running a calibration iteration

```bash
tdmcalib validate-config                    # schema + override-key checks, all calibration_runs/*.yaml (or --run C50)
tdmcalib sync-tdm --run C50                 # check out C50's tdm_ref in tdm/, nothing else
tdmcalib run --run C50                      # sync + render Control Center + invoke Cube Voyager + curate outputs
tdmcalib run-all                            # every calibration run declared under calibration_runs/, sequentially
tdmcalib status                             # latest known status per calibration run
```

If the model was run manually (Cube Voyager invoked directly, outside `tdmcalib`),
curate its outputs after the fact instead of `run`:

```bash
tdmcalib import-manual-run --run C50
```

Add a new calibration run by copying an existing `calibration_runs/C5N.yaml` — no
changes needed under `report/`, since every report covers all calibration runs
automatically once `runs/C5N/outputs/` exists. See `report/README.md`.

## Working with the TDM submodule

**Do not edit files inside `tdm/` directly.** Checking out `tdm/` puts you in a
detached-HEAD state by default; any commits made there are easy to lose track of and
won't automatically show up as a change in this repo (you'd need to also bump the
submodule pointer, which should happen deliberately — see below).

If calibration work surfaces a needed fix in the TDM itself:
1. Make the fix in the TDM repo directly (on a branch, PR'd and merged there).
2. Come back here and **bump the submodule pointer** (see below) in its own reviewed PR.

### Checking what version you're on

```bash
git submodule status
git -C tdm log -1
```

### Bumping the TDM version

Do this as a deliberate, reviewed step — not as a side effect of routine setup.

```bash
cd tdm
git fetch --tags
git checkout v2.5.0        # or a specific commit SHA
cd ..
git add tdm
git commit -m "Bump TDM submodule to v2.5.0 (updated transit skims)"
```

Open this as its own PR with a note on *why* the version changed. Avoid running
`git submodule update --remote` as routine habit — it floats to the tracked branch's
HEAD and defeats the point of pinning.

### Version pinned

Current TDM version: `calib/C50-start` (`ef48116d`, "fix: Update trip gen vizTool script name")
Rationale: starting point for the C50 calibration iteration.

## Outputs & large files

Raw model output lives inside the `tdm/` submodule's own working tree
(`tdm/Scenarios/{calib_run_id}/`, already gitignored there by `tdm/.gitignore`) — it
never touches this repo's git history. `tdmcalib` copies a declared subset
(`calibration_runs/*.yaml`'s `outputs.include`) into
`runs/{calib_run_id}/outputs/`, which **is** committed — that curated, checksummed set
is this repo's actual audit trail of what the latest run produced. Only the latest
attempt is ever kept for a given calibration run: starting a new run for
`{calib_run_id}` deletes whatever `runs/{calib_run_id}/` held before, rather than
accumulating one folder per attempt, so a failed re-run replaces (not shadows) an
earlier successful one. Every curated file is still written there regardless of size
(so reports render fully on the machine that curated it), but any file whose actual
written size exceeds `outputs.max_file_size_mb` is auto-excluded from git via that
`outputs/` folder's own generated `.gitignore` (and marked `"committed": false` in
`run_metadata.json`) rather than committed or failing the run — see
`report/README.md`'s "Known gaps" for which files this currently applies to.

## CI

If using GitHub Actions, make sure `actions/checkout` has `submodules: recursive` set
(see `.github/workflows/ci.yml`) — otherwise the `tdm/` folder will be empty and jobs
will fail silently or confusingly. CI is scoped to validation (config schema checks,
`tdmcalib validate-config`) and publishing rendered reports — never model
execution (Cube Voyager is licensed per-machine and runs on a researcher's workstation).
