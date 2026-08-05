# CLAUDE.md

Guidance for Claude Code (and Claude generally) when working in this repo.

## What this repo is

Calibration scripts, configs, and targets for the TDM. The TDM model code itself
lives in a **separate repo** and is included here as a **pinned git submodule** at
`tdm/`. This repo's whole purpose is reproducible calibration runs tied to an exact
TDM version — nothing here should silently change which TDM commit is in use.

## Hard rules

- **Never edit files inside `tdm/`.** It's a submodule in detached-HEAD state by
  default. If a TDM code change is needed, that change belongs in the TDM repo itself,
  on its own branch/PR there — not here.
- **Never run `git submodule update --remote`** as part of a task unless explicitly
  asked to "bump the TDM version." That command floats the submodule to the tracked
  branch's HEAD, which defeats the pinning this repo exists to provide.
- **Never commit large binary outputs** (skims, trip tables, matrices, logs) into git.
  Raw model output lives inside the `tdm/` submodule's own working tree
  (`tdm/Scenarios/{calib_run_id}/`, already gitignored there) — only a curated,
  size-capped subset ever gets committed, under `runs/{calib_run_id}/{run_id}/outputs/`,
  produced by `tdmcalib`'s output curation (`outputs.include` in `calibration_runs/*.yaml`
  — see `config/framework.yaml`'s `outputs.max_file_size_mb`). This is enforced
  automatically, not just by convention: any curated file whose actual written size
  exceeds the ceiling is kept locally (so reports still render fully on the machine
  that curated it) but marked `"committed": false` in `run_metadata.json` and listed in
  its `outputs/` folder's auto-generated `.gitignore` — never committed, regardless of
  what `outputs.include` declares (see `src/tdmcalib/outputs.py`'s `copy_selected()`).
  Don't `git add` anything under `tdm/Scenarios/` directly, don't widen an
  `outputs.include` pattern just to make a large file fit, and don't hand-edit an
  `outputs/.gitignore` — it's regenerated on every curation run.
- If asked to "update the TDM" or "bump the submodule," treat it as a deliberate,
  reviewed action: fetch tags, checkout the specific target tag/commit inside `tdm/`,
  then `git add tdm && git commit` with a message stating what changed and why. Don't
  do this as a side effect of an unrelated task.

## Repo layout

| Path                | Contents                                                  |
|---------------------|-------------------------------------------------------------|
| `tdm/`              | TDM submodule — read-only from this repo's perspective       |
| `config/`           | `tdmcalib` framework settings (`framework.yaml`, `local.yaml` — gitignored, per-machine, copy from `local.example.yaml`), JSON schemas |
| `calibration_runs/` | One YAML per calibration run (`C50.yaml`, ...) — `tdm_ref`, Control Center overrides, `outputs.include` — see `README.md`'s tdmcalib section |
| `runs/`             | `tdmcalib`'s curated, committed output + `run_metadata.json` per run attempt (`runs/{calib_run_id}/{run_id}/`) |
| `src/tdmcalib/`     | The orchestrator (installable as the `tdmcalib` CLI) — ported from the sibling `WF-TDM-Runs` repo's `tdmruns`, flattened for a single calibration-run axis instead of run_set/scenario nesting |
| `bin/`              | `RunModel.bat` — TDM-version-independent Cube Voyager entry point `tdmcalib` invokes |
| `tests/`            | `pytest` suite for `src/tdmcalib/` |
| `inputs/`           | Calibration targets, counts, survey data                     |
| `report/`           | Quarto calibration reports (one file per stage, each covering every calibration run via an in-page selector) + `compare.qmd` (cross-run comparison), published to GitHub Pages — see `report/README.md` |

`scripts/` (calibration scripts — matrix estimation, target matching) and `configs/`
(their parameter/target configs, distinct from `calibration_runs/`'s TDM-execution
config) don't exist yet — create them when the first actual script/config needs them,
not speculatively. See Conventions below for naming once they do.

## Before doing calibration work

1. Confirm `tdm/` is initialized (`git submodule status` — if it shows `-<sha>` with a
   leading `-`, it's not initialized; run `git submodule update --init --recursive`).
2. Check what TDM version is pinned (`git -C tdm log -1 --oneline`) before assuming
   behavior — TDM interfaces/outputs can change between versions, and calibration
   scripts should match the pinned version, not the latest TDM.
3. Scripts (once `scripts/` exists — see Repo layout) should reference the TDM via the
   `tdm/` relative path, not a hardcoded absolute path or a separately-cloned copy — so
   the pinned version is always the one actually used.

## Conventions

- Create `scripts/` and `configs/` only when the first real script/config needs them —
  don't scaffold them speculatively.
- New calibration scripts go in `scripts/`, named for what they calibrate (e.g.
  `calibrate_mode_choice.py`, not `run2_final.py`).
- Config/target files are data, not code — keep parameter values in `configs/`
  or `inputs/`, not hardcoded in scripts.
- If a script's output is meant to be compared across TDM versions or calibration
  iterations, include the TDM commit/tag in the output filename or a metadata header,
  so results stay traceable to the version that produced them.

## When in doubt

Prefer asking or flagging over guessing — especially before bumping the submodule
pointer, editing anything under `tdm/`, or committing anything under `runs/`.
