# Calibration Reports

Quarto-based reports, one file per model stage (`0-hhdisag-autoown.qmd`, `1-tripgen.qmd`,
`2-distribution.qmd`, `3-modechoice.qmd`, `4-assignhwy.qmd`, `7-modelresults.qmd`),
comparing modeled output against observed data (HTS survey, ACS/Census, transit
on-board survey, traffic counts). There is **one set of reports, not one per
calibration run** — each report loads every calibration run that has at least one
successful `tdmcalib` run under `runs/`, and a single shared "Calibration Run" dropdown
(`report/_calib_run_selector.qmd`, spliced into every page, sitting in the left sidebar)
picks which run's modeled results to view against observed data, persisted across page
navigation via `localStorage`. `compare.qmd` shows headline metrics across runs side by
side.

This mirrors the pattern used in [WF-TDM-Documentation](https://github.com/WFRCAnalytics/WF-TDM-Documentation)
for TDM version validation, adapted to point at this repo's `runs/` and `inputs/`
folders instead of `_large_files/`.

Static reference/target data (`report/data/` and the survey/count files under
`inputs/`) is copied in from `WF-TDM-Documentation`'s committed copy (that repo's
`v10x/v1000/validation/data/` and `_large_files/v1000/`) and from
`F:\SHARED\Chris\large_files_calibration\v1000\` (also the source for imported
calibration runs like `calibration_runs/C33.yaml` — see below) if it ever needs
refreshing. One file, `inputs/UT_HTS_2023_Linked_Trips.csv`, exceeds GitHub's 100MB
limit and isn't committed — see root `README.md`'s "Setup" section for the manual
copy step; every other file under `inputs/` is comfortably under the limit and stays
committed normally.

## How a report finds each run's output

`_validation_scripts.py` provides the shared discovery/loading helpers every report
uses:

- `list_available_runs(repo_root)` — every `calib_run_id` under `runs/` whose currently
  recorded run succeeded (only the latest attempt is ever kept on disk for a
  calib_run_id — see `src/tdmcalib/metadata.py`).
- `resolve_latest_run_outputs(repo_root, calib_run)` — that run's
  `runs/<calib_run>/` folder (a flat, curated set of model output, sibling of
  that run's `run_info/` attempt history — see `src/tdmcalib/outputs.py`).
- `load_per_run(repo_root, load_fn)` — calls `load_fn(calib_run, outputs_dir)` for
  every available run, tags each result with a `calib_run` column, and concatenates
  into one DataFrame. This is the pattern every stage report uses to build its modeled
  side; observed/reference data (HTS, counts, etc.) is loaded once and is *not* tagged
  with `calib_run` — it rides along on the modeled side of a merge rather than being a
  merge key, so it's legitimately duplicated across every run's rows without
  corruption.
- `find_one(outputs_dir, pattern)` — single-match glob, for curated filenames that
  carry a Cube-generated `___{runId}___` prefix (see "Known gaps" below).
- `load_cached_per_run(repo_root, name)` — like `load_per_run()`, but reads pre-built
  `runs/<calib_run>/cache/<name>.parquet` files instead of calling a loader function.
  See "Report data caching" below.

No `config.json`/preprocess toggle exists — every report always computes from whatever
runs are currently available under `runs/`. There used to be a manual `preprocess`
flag gating the expensive per-run computation; it's gone now that `tdmcalib run` /
`import_manual_run` automatically re-render this Quarto project after curating a run's
outputs (see "Post-run rendering" below), so there's no longer a reason to skip
recomputation on a plain `quarto preview`.

## Report data caching

`quarto render .` re-executes every report page on every `tdmcalib run`/`import-manual-run`,
even though only one calibration run's data actually changed. Reading raw OMX matrices,
DBF files, and large CSVs — the expensive part — used to happen inline in each `.qmd`'s
Python cells, so it reran in full regardless. `report/preprocess/` moves that parsing out
of the render's critical path:

- One module per stage (`report/preprocess/tripgen.py`, etc.), each holding the per-run
  data-loading logic extracted from the matching `.qmd`'s old `_load_*` functions —
  `load_fn(calib_run, outputs_dir, repo_root) -> DataFrame`.
- `report/preprocess/build_cache.py` — `python -m report.preprocess.build_cache --run C50`
  builds every registered dataset for one calibration run, writing
  `runs/<calib_run_id>/cache/<name>.parquet` (gitignored — a disposable build accelerator,
  always reproducible from `runs/<calib_run_id>/`, never a source of truth).
- `tdmcalib.postprocess.build_report_cache()` shells out to that CLI automatically, right
  after a run's outputs are curated and **before** the report re-renders (so the fresh
  cache exists by render time) — see `src/tdmcalib/execution.py`. Failure is recorded on
  that attempt's `run_info/{run_id}.json`'s `preprocess` key but doesn't fail the run itself.
- The `.qmd` side: `vs.load_per_run(repo_root, _load_x)` becomes
  `vs.load_cached_per_run(repo_root, "x")`, and the `_load_x` def moves to
  `report/preprocess/`. Shared/observed reference data that isn't per-`calib_run` (HTS via
  BigQuery, ACS/Census/CCS static files) deliberately stays inline — it doesn't fit a
  per-run cache model, and keeps `report/preprocess/` free of a BigQuery dependency.

**Migrated so far**: all 6 report stage files. `1-tripgen.qmd` (`modeled_tripgen`),
`0-hhdisag-autoown.qmd` (`hhdisag`, `vehown`), `7-modelresults.qmd` (`crt_model`),
`3-modechoice.qmd` (`tdm_agg`, `boardings`, `mod_boarding`, `crt_dist`),
`2-distribution.qmd` (`mod_trips_dist_gc`, `mod_intra`, `master_trips`, `dist_sum_mod`,
`mod_dist_hbw_sum`, `mod_distrib_hbw_sum`), and `4-assignhwy.qmd` (`mod_tidy`,
`ccs_daily`, `seg_detail`, `xx`) — verified: identical numeric output to each file's
pre-migration inline computation (`4-assignhwy.qmd`'s `summary_metrics_assignhwy_C33.json`
matched byte-for-byte; others matched modulo float noise at the ~13th significant digit
from the parquet round-trip). `2-distribution.qmd`'s and `4-assignhwy.qmd`'s loaders
closed over more shared state built up earlier in those files (a shared CCS-station
spatial join, a shared Google-speeds observed base table) than the other 4 files, so
those two modules (`report/preprocess/distribution.py`,
`report/preprocess/assignhwy.py`) duplicate that shared setup as private helpers, each
loader that needs it recomputing it independently rather than restructuring
`build_cache.py`'s flat loader registry into a dependency graph -- same tradeoff as
`report/preprocess/modechoice.py`'s `_load_observed_data()`.

## Adding a new calibration run

1. Add `calibration_runs/C5N.yaml` (copy an existing one as a starting point) and run
   it through `tdmcalib` (see repo root `README.md`) — `tdmcalib run --run C5N` (or
   `import-manual-run` if the model was run outside the CLI) populates
   `runs/C5N/` with a curated set of model output (plus a new
   `runs/C5N/run_info/{run_id}.json` attempt record), and automatically re-renders
   this Quarto project so the new run shows up.
2. Nothing under `report/` needs to change — every `.qmd` discovers `C5N` on its own
   via `_validation_scripts.list_available_runs()`.
3. If rendering locally instead of relying on the automatic post-run render: `quarto
   render` from the repo root, then commit `docs/` — CI does **not** render (it can't
   reach `tdm/`/Cube Voyager); it only publishes the already-rendered `docs/` to
   GitHub Pages on push to `main` (`.github/workflows/publish-pages.yml`). This can't
   be a plain "deploy from branch" Pages source instead — GitHub's own built-in
   branch-deploy build recursively checks out submodules, and fails on the pinned
   `tdm/` submodule (a private repo the build's default token can't reach) even though
   Pages only ever needed `docs/`. `actions/checkout@v4` in this workflow doesn't fetch
   submodules unless told to, which is what makes the Actions path work.

## Post-run rendering

`tdmcalib run` and `tdmcalib import_manual_run` call
`tdmcalib.postprocess.render_validation()` after a successful curation, which runs
`quarto render` against the repo root project (`config/framework.yaml`'s `postprocess`
section controls this — `render_validation: false` to disable, plus the Quarto
executable path and a timeout). A rendering failure is logged into the attempt's
`run_info/{run_id}.json` under `postprocess` but does **not** fail the run itself — the
curated outputs are already safely on disk regardless of whether the report
re-rendered cleanly. Commit the resulting `docs/` to publish.

## Cross-run comparison (`compare.qmd`)

Any stage `.qmd` can write `summary_metrics_<stage>_<calib_run>.json` (a small
`{"calib_run": ..., "stage": ..., "metrics": {name: value, ...}}` document) at the end
of its data-prep cells, once per calibration run it processes — `compare.qmd` globs
`summary_metrics_*.json` at render time and lets you pick any subset of calibration
runs to chart side by side, per metric. This is deliberately a *summary* mechanism (a
handful of scalars per stage per run), not a way to compare full distributions across
runs — keeps `compare.qmd` fast regardless of how many calibration runs accumulate.

Currently wired up: `1-tripgen.qmd` (trips per household/person by data source),
`3-modechoice.qmd` (transit mode share, system-wide transit trips % diff),
`4-assignhwy.qmd` (total volume % diff, segment RMSE). The other stages
(`0-hhdisag-autoown`, `2-distribution`, `7-modelresults`) don't emit one yet — follow
the same pattern (a `json.dump()` cell, looped over `calib_runs`, after the stage's
main comparison DataFrame is built) if they need to show up in `compare.qmd`.

## Known gaps carried over from this scaffold

- **`calibration_runs/C50.yaml`'s `outputs.include` has not been exercised against a
  live Cube run yet.** Filenames, paths, and matrix tab names are cross-checked against
  a real archived run's converted output (see `calibration_runs/C33.yaml`) rather than
  a live `tdmcalib run --run C50` — adjust after the first real run if anything
  doesn't match.
- A handful of curated filenames carry a Cube-generated `___{runId}___` prefix on a
  live `tdmcalib` run (`RegionShares_Pk/Ok.csv`, `transit_brding_summary_node.csv`,
  `transit_rider_summary_link.csv`, `Summary_SEGID(_Detailed).csv`), but typically don't
  on an imported archived run (e.g. `calibration_runs/C33.yaml`) — the `.qmd` files
  resolve these via `_validation_scripts.find_one()` with a prefix-agnostic glob (e.g.
  `"*RegionShares_Pk.csv"`) so either case matches, since the exact `runId` text depends
  on `ModelVersion`/`ScenarioName`/`RunYear` and isn't known ahead of time either way.
- **`skm_DY_Dist.omx`/`skm_DY_GC.omx` (used by `2-distribution.qmd`'s "Average Trip
  Length"/"Trip Length Frequency" sections) exceed the size ceiling even trimmed to
  just their needed tabs** — each is a dense 3630-zone matrix across the ~10 travel
  purposes those sections analyze, and a skim has no empty cells to trim away (unlike a
  trip table). Even float32 + max compression only gets each to ~250-266 MB against a
  95 MB ceiling. Per `src/tdmcalib/outputs.py`'s auto-`.gitignore` mechanism, these are
  still curated and written locally (so this section renders fully on whatever machine
  did the curating) but are never committed — on any other machine/CI, these two files
  are simply absent and that section has no data. Revisit with a sparse OD-pair
  extraction (values only at OD pairs with nonzero trips, cross-referenced against the
  trip table) if this needs to work everywhere; not implemented yet.
- **`4-assignhwy.qmd`'s "Vehicle-Miles Traveled (VMT) Validation" section (`##
  Vehicle-Miles Traveled...` through `## HOT Lane Validation`) is not yet multi-run** —
  unlike the CCS Volume dashboard and Station Level Daily Volume sections earlier in
  the same file, it always shows the most recently available calibration run
  (`calib_runs[-1]`) with no run selector, rather than loading every run via
  `_validation_scripts.load_per_run()`. Revisit if/when this section needs cross-run
  comparison; the pattern to follow is the same one already used elsewhere in this
  file (a `_load_*(calib_run, outputs_dir)` function passed to `load_per_run()`, an OJS
  `calib_run` selector, `dropna=False` groupbys where observed data rides along).
- **BigQuery access**: `1-tripgen.qmd` pulls HTS data via the shared
  `Resources/2-Python/global-functions/BigQuery.py` module (sibling repo at
  `M:\GitHub\Resources`). The `sys.path` reference was updated for this repo's
  folder depth but is untested here.
- The `.qmd` files still reference WF-TDM v1000-specific structures (purpose names,
  TAZ counts, county FIPS, etc.) — expect to adjust them once a calibration run has
  actually produced output to check the assumptions against.
- **Quarto 1.8.27 bug**: an OJS cell with `panel: input` (or any cell with multiple
  `viewof` declarations) plus a `layout-ncol` cell option throws `TypeError: Cannot
  read properties of undefined (reading 'info')` in `makeSubFigures` at render time —
  doesn't show up in `quarto inspect .`, only an actual render. Worked around by
  omitting `layout-ncol` (`panel: input` already flows multiple inputs horizontally
  without it) — see the comments left at each removed occurrence. Don't re-add
  `layout-ncol` to an OJS cell without first confirming this Quarto version's fixed it.
