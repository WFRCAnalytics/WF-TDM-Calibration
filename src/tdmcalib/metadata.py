"""Run metadata: the framework's source of truth. One JSON document per
attempt, schema-versioned, committed to the repo. Reporting reads only this
-- never the TDM submodule or the gitignored working folders directly.

Every attempt for a calib_run_id keeps its own metadata document, forever,
at runs/{calib_run_id}/run_info/{run_id}.json -- a permanent audit trail of
every run/import invocation, kept regardless of outcome. This is the one
part of runs/{calib_run_id}/ that is never wiped. Curated outputs
(runs/{calib_run_id}/*, siblings of run_info/) are a different story: only
the latest attempt's outputs are ever kept on disk (see execution.py, which
wipes and re-curates them on every attempt) -- CLAUDE.md's "never commit
large binary outputs" rule depends on not accumulating one copy of
potentially-huge curated output per historical attempt. So "latest attempt"
still matters for outputs/status purposes even though metadata history is
now unbounded: latest_run()/list_runs() resolve it by run_id, which sorts
chronologically since generate_run_id() (execution.py) prefixes it with a
UTC timestamp.

Ported from WF-TDM-Runs' src/tdmruns/metadata.py, flattened: run_set_id +
scenario_id collapse to a single calib_run_id, run_set_overrides +
scenario_overrides collapse to a single overrides dict."""
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
    run_info_dir = run_dir / "run_info"
    run_info_dir.mkdir(parents=True, exist_ok=True)
    with open(run_info_dir / f"{metadata['run_id']}.json", "w") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")


def _latest_run_id(run_dir: Path) -> str:
    """The most recent attempt's run_id under run_dir/run_info/, or None if
    none exist. run_id sorts chronologically (see module docstring), so the
    lexicographically-greatest filename stem is the latest attempt."""
    run_info_dir = run_dir / "run_info"
    if not run_info_dir.is_dir():
        return None
    candidates = sorted(run_info_dir.glob("*.json"))
    return candidates[-1].stem if candidates else None


def read(run_dir: Path, run_id: str = None) -> dict:
    """Reads one attempt's metadata document. run_id=None (the default)
    resolves to the latest attempt."""
    run_id = run_id or _latest_run_id(run_dir)
    with open(run_dir / "run_info" / f"{run_id}.json") as f:
        return json.load(f)


def list_runs(repo_root: Path, calib_run_id: str = None) -> list:
    """The latest attempt for each calibration run under runs/, optionally
    filtered to one calibration run -- sorted by calib_run_id for a stable
    order. Full attempt history lives in each run_info/ but this, like the
    old single-file layout, only ever surfaces the latest one."""
    runs_root = repo_root / "runs"
    if not runs_root.is_dir():
        return []
    calib_run_ids = (
        [calib_run_id] if calib_run_id else sorted(p.name for p in runs_root.iterdir() if p.is_dir())
    )
    found = []
    for crid in calib_run_ids:
        run = latest_run(repo_root, crid)
        if run is not None:
            found.append(run)
    return found


def list_attempts(repo_root: Path, calib_run_id: str) -> list:
    """Every attempt ever recorded for calib_run_id, oldest first -- the
    permanent audit trail runs/{calib_run_id}/run_info/ keeps regardless of
    outcome (see module docstring)."""
    run_info_dir = repo_root / "runs" / calib_run_id / "run_info"
    if not run_info_dir.is_dir():
        return []
    run_dir = run_info_dir.parent
    return [read(run_dir, run_id=p.stem) for p in sorted(run_info_dir.glob("*.json"))]


def latest_run(repo_root: Path, calib_run_id: str) -> dict:
    run_dir = repo_root / "runs" / calib_run_id
    run_id = _latest_run_id(run_dir)
    return read(run_dir, run_id=run_id) if run_id else None


def latest_successful_run(repo_root: Path, calib_run_id: str) -> dict:
    """
    Returns the recorded run for calib_run_id if its status is "success",
    None otherwise.

    Since a failed re-run replaces (rather than shadows) an earlier
    successful one, a caller relying on the last known-good state (e.g.
    start_from_copy in run_seed.py) must treat "recorded but currently
    failed" the same as "nothing recorded".
    """
    run = latest_run(repo_root, calib_run_id)
    return run if run and run["status"] == "success" else None
