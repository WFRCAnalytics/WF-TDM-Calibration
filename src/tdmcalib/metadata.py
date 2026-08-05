"""Run metadata: the framework's source of truth. One JSON document per run,
schema-versioned, committed to the repo. Reporting reads only this -- never
the TDM submodule or the gitignored working folders directly.

Ported from WF-TDM-Runs' src/tdmruns/metadata.py, flattened: run_set_id +
scenario_id collapse to a single calib_run_id, run_set_overrides +
scenario_overrides collapse to a single overrides dict, and runs/ drops one
directory level (runs/{calib_run_id}/{run_id}/ instead of
runs/{run_set_id}/{scenario_id}/{run_id}/)."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def framework_commit(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def build(
    schema_version: int,
    calib_run_id: str,
    run_id: str,
    status: str,
    started_at: str,
    framework_commit_sha: str,
    tdm_state: dict,
    baseline_file: str,
    overrides: dict,
    rendered_path: str = None,
    driver_script: str = None,
    seeded_from: dict = None,
    scenario_folder: str = None,
    command: list = None,
    exit_code: int = None,
    log_path: str = None,
    status_source: str = None,
    model_log: dict = None,
    inventory_count: int = None,
    inventory_total_bytes: int = None,
    curated: list = None,
    finished_at: str = None,
    error: str = None,
    execution_mode: str = "cli",
    postprocess: dict = None,
) -> dict:
    # rendered_path/command/driver_script are only meaningful when the
    # orchestrator itself rendered a Control Center, staged a driver script,
    # and invoked the model (execution_mode "cli") -- always set together in
    # that case, always absent for a manual import. Left out entirely rather
    # than set to null, since the schema types them as non-nullable.
    control_center = {
        "baseline_file": baseline_file,
        "overrides": overrides,
    }
    if rendered_path is not None:
        control_center["rendered_path"] = rendered_path
    if driver_script is not None:
        control_center["driver_script"] = driver_script

    execution = {}
    if command is not None:
        execution["command"] = command
    if exit_code is not None:
        execution["exit_code"] = exit_code
    if log_path is not None:
        execution["log_path"] = log_path
    if status_source is not None:
        execution["status_source"] = status_source
    if model_log is not None:
        execution["model_log"] = model_log

    result = {
        "schema_version": schema_version,
        "calib_run_id": calib_run_id,
        "run_id": run_id,
        "status": status,
        "execution_mode": execution_mode,
        "started_at": started_at,
        "finished_at": finished_at,
        "framework_commit": framework_commit_sha,
        "tdm": tdm_state,
        "control_center": control_center,
        "scenario_folder": scenario_folder,
        "execution": execution,
        "outputs": {
            "inventory_count": inventory_count,
            "inventory_total_bytes": inventory_total_bytes,
            "curated": curated or [],
        },
        "error": error,
    }
    # seeded_from is only set when start_from_copy actually fired -- absent
    # otherwise, same "leave out entirely" convention.
    if seeded_from is not None:
        result["seeded_from"] = seeded_from
    # postprocess is only set when render_validation() actually ran (i.e.
    # this run succeeded) -- absent otherwise, same convention.
    if postprocess is not None:
        result["postprocess"] = postprocess
    return result


def write(run_dir: Path, metadata: dict):
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "run_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")


def read(run_dir: Path) -> dict:
    with open(run_dir / "run_metadata.json") as f:
        return json.load(f)


def list_runs(repo_root: Path, calib_run_id: str = None) -> list:
    """Scans runs/ for run_metadata.json files, optionally filtered to one
    calibration run, sorted newest-first by run_id (which is
    timestamp-prefixed)."""
    runs_root = repo_root / "runs"
    if not runs_root.is_dir():
        return []
    pattern = f"{calib_run_id or '*'}/*/run_metadata.json"
    found = sorted(runs_root.glob(pattern), key=lambda p: p.parent.name, reverse=True)
    return [read(p.parent) for p in found]


def latest_run(repo_root: Path, calib_run_id: str) -> dict:
    runs = list_runs(repo_root, calib_run_id)
    return runs[0] if runs else None


def latest_successful_run(repo_root: Path, calib_run_id: str) -> dict:
    """
    Like latest_run(), but skips past newer failed attempts.

    Returns the most recent run with status "success" -- a calibration run
    re-run for an unrelated reason (e.g. a later attempt that failed)
    shouldn't shadow an earlier successful one.
    """
    for run in list_runs(repo_root, calib_run_id):
        if run["status"] == "success":
            return run
    return None
