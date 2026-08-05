"""Seeding a calibration run's raw folder from a prior calibration run.

Some calibration changes only take effect late in the model pipeline (e.g. a
change applied at mode choice). Rerunning every upstream step from scratch
for those wastes time reproducing output identical to an already-completed
run. A calibration run may declare start_from_copy: <calib_run_id> to have
its raw working folder seeded with a full copy of that other run's most
recent successful run, before this run's own Control Center and driver
script are written into it.

The source is resolved via that run's run_metadata.json (metadata.py), not a
declared manual_scenario_folder -- this works uniformly whether the source
run was executed through the CLI or imported from a manual run. It uses
metadata.latest_successful_run(), which skips past newer failed attempts,
rather than requiring the single most recent run (of any status) to have
succeeded -- a run re-run for an unrelated reason (e.g. output curation
tripping the size limit) shouldn't block copying from an earlier success.

Because the raw working folder is reused across every run attempt for a
given calib_run_id (scenario_folder_template has no run_id component), a
calibration run declaring start_from_copy re-copies the source's entire
folder on every one of its own retries too -- which can be tens of GB. A run
may additionally declare lock_down_copy: true once its folder already holds
the seeded state it needs, to skip the copy on subsequent runs without
removing the start_from_copy declaration (kept for the record of where it
came from).

This mechanism only decides what state a run's folder starts with. It does
not make Cube Voyager skip any steps -- that logic, if wanted, belongs in a
custom driver_script (see driver_script.py) the analyst writes to check for
and skip past already-completed steps.

Ported from WF-TDM-Runs' src/tdmruns/scenario_seed.py, renamed off
"scenario" -- the source calibration run identified by start_from_copy plays
exactly the role a sibling scenario in the same run_set used to."""

import shutil
from pathlib import Path

from tdmcalib import metadata as md
from tdmcalib.exceptions import RunSeedError


def seed(repo_root: Path, calib_run_id: str, calib_run: dict, run_folder: Path) -> dict | None:
    """
    Copy a prior calibration run's raw folder into run_folder, if declared.

    If start_from_copy is declared and lock_down_copy is not set, copies the
    entire raw working folder from the source calibration run's most recent
    successful run into run_folder. Returns {"calib_run_id", "run_id"}
    identifying the source for the metadata record, or None if not declared
    or if lock_down_copy suppressed the copy.
    """
    source_calib_run_id = calib_run.get("start_from_copy")
    if not source_calib_run_id:
        return None
    if calib_run.get("lock_down_copy"):
        return None

    source_run = md.latest_successful_run(repo_root, source_calib_run_id)
    if source_run is None:
        raise RunSeedError(
            f"start_from_copy: '{source_calib_run_id}' has no successful recorded run "
            "-- run or import it successfully before other calibration runs can copy from it."
        )

    source_folder = Path(source_run["scenario_folder"])
    if not source_folder.is_dir():
        raise RunSeedError(
            f"start_from_copy: '{source_calib_run_id}''s recorded working folder "
            f"{source_folder} no longer exists on disk."
        )

    shutil.copytree(source_folder, run_folder, dirs_exist_ok=True)

    return {"calib_run_id": source_calib_run_id, "run_id": source_run["run_id"]}
