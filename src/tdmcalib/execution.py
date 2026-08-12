"""
Execution orchestration: run-folder creation, command building, invoking
the TDM's fixed batch entry point, and the top-level run() that ties config,
version resolution, Control Center rendering, execution, output curation,
and metadata together into one auditable attempt.

Ported from WF-TDM-Runs' src/tdmruns/execution.py, flattened for the
run_set/scenario -> single calibration run collapse. One notable non-cosmetic
change: identity_fields forces `ParentDir`, not `ModelDir` -- this repo's
real baseline Control Center (Scenarios/_default/_ControlCenter-Calib -
BY_2023.block) uses `ParentDir` as its "where's the TDM root" variable (the
plain, non-calibration baseline WF-TDM-Runs was built against uses
`ModelDir` instead).
"""

import os
import platform
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from tdmcalib import config as cfg
from tdmcalib import controlcenter as cc
from tdmcalib import driver_script as ds
from tdmcalib import general_parameters as gp
from tdmcalib import metadata as md
from tdmcalib import model_log as mlog
from tdmcalib import outputs as out
from tdmcalib import postprocess as pp
from tdmcalib import prep
from tdmcalib import prn_log
from tdmcalib import run_seed as seed
from tdmcalib import submodule as sub
from tdmcalib.exceptions import ExecutionError


def generate_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(2)
    return f"{ts}-{suffix}"


def _write_running_record(
    framework: dict, run_dir: Path, *, control_center_path: Path, driver_script_path: str,
    command: list, log_path: Path, **build_kwargs,
) -> None:
    """
    Writes a "running" run_info/ record before the model is invoked.

    See the call site in run() for why this exists.
    """
    running_metadata = md.build(
        schema_version=framework["run_metadata_schema_version"],
        status="running",
        rendered_path=str(control_center_path),
        driver_script=driver_script_path,
        command=command,
        log_path=str(log_path),
        **build_kwargs,
    )
    md.write(run_dir, running_metadata)


def _reset_run_outputs(run_dir: Path):
    """Clears everything under run_dir except run_info/ (see metadata.py) --
    curated outputs and the report cache are wiped and rebuilt fresh on
    every attempt (only the latest is ever kept, per CLAUDE.md's "never
    commit large binary outputs" rule), but run_info/'s per-attempt metadata
    history is permanent and must survive this reset."""
    if not run_dir.exists():
        return
    for child in run_dir.iterdir():
        if child.name == "run_info":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def run_folder_path(tdm_path: Path, framework: dict, calib_run_id: str) -> Path:
    rel = framework["scenario_folder_template"].format(calib_run_id=calib_run_id)
    return tdm_path / rel


def _windows_style(path_str: str, trailing_sep: bool = True) -> str:
    s = path_str.replace("/", "\\")
    if trailing_sep and not s.endswith("\\"):
        s += "\\"
    return s


def build_command(
    framework: dict, repo_root: Path, control_center_path: Path, scenario_folder: Path
) -> list:
    execution_cfg = framework["execution"]
    entry_point_abs = (repo_root / execution_cfg["entry_point"]).resolve()
    if not entry_point_abs.is_file():
        raise ExecutionError(
            f"Batch entry point not found at {entry_point_abs} "
            f"(config/framework.yaml execution.entry_point = '{execution_cfg['entry_point']}')."
        )
    args = [
        a.format(control_center_path=str(control_center_path), scenario_folder=str(scenario_folder))
        for a in execution_cfg["args"]
    ]
    if entry_point_abs.suffix.lower() in (".bat", ".cmd") and platform.system() == "Windows":
        return ["cmd.exe", "/c", str(entry_point_abs), *args]
    if entry_point_abs.suffix.lower() == ".py":
        return [sys.executable, str(entry_point_abs), *args]
    return [str(entry_point_abs), *args]


def invoke(command: list, cwd: Path, log_path: Path, timeout_seconds: int, env: dict = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    full_env = {**os.environ, **env} if env else None
    with open(log_path, "w") as log:
        log.write(f"command: {command}\ncwd: {cwd}\n\n")
        log.flush()
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
                env=full_env,
            )
            return result.returncode
        except subprocess.TimeoutExpired:
            log.write(f"\n\nTIMED OUT after {timeout_seconds}s\n")
            return -1


def _append_prn_errors(error: str, scenario_folder: Path) -> str:
    """Folds Voyager's own F(NNN): fatal-error lines from the most recent
    *.PRN file into a failed run's error message, alongside decide_status's
    step-level summary -- see prn_log.py for why that PRN is the right one
    and how a real Voyager error line is told apart from an F(x) function
    reference inside PILOT script code. No-ops (returns error unchanged) if
    there's no PRN file or none of its lines match, e.g. a hang/timeout that
    never got as far as Voyager reporting anything."""
    prn_path, fatal_lines = prn_log.latest_fatal_errors(scenario_folder)
    if not fatal_lines:
        return error
    return f"{error}\n\nVoyager errors ({prn_path.name}):\n" + "\n".join(fatal_lines)


def decide_status(
    exit_code: int, model_log_result: dict | None, log_path: Path, scenario_folder: Path
) -> tuple:
    r"""Decides run status/error from the model's own _Log\_RunTime.txt
    completion report alone -- the only check trusted here, and the only one
    that gates whether run() extracts outputs. It applies uniformly across
    every Hail Mary driver variant (plain, resumable, 1-subfolder, ...),
    since they all funnel through the same _TimeStamp_ModelSuccess.block /
    _TimeStamp_ModelCrashed.block pair. Voyager's own process exit code is
    not reliable on its own -- WF-TDM-Runs recorded real runs completing
    cleanly (a "TOTAL MODEL RUN TIME" entry, no crash marker) while Voyager
    still returned a non-zero exit code, and the driver script never calls
    Exit after :ONERROR, so the reverse (a crash -- or an unresolved,
    superseded checkpoint, see model_log.py -- that still exits 0) is
    plausible too. No resolved model-log entry is therefore treated as
    failed rather than falling back to the exit code: a run is never called
    "success" without the model's own confirmation. exit_code is still
    folded into the error text for diagnostics.

    Returns (status, error, status_source, model_log_result) -- the last one
    is the input dict with exit_code_mismatch filled in (or None, unchanged).
    """
    if model_log_result is None:
        status = "failed"
        error = (
            f"No resolved model completion report in "
            f"{scenario_folder / '_Log' / '_RunTime.txt'} (see {log_path}). "
            f"Voyager exit code: {exit_code}."
        )
        return status, error, "exit_code", None

    if model_log_result["outcome"] == "crashed":
        status = "failed"
        step = model_log_result["crashed_step"] or "an unrecognized step"
        error = (
            f"Model crashed during {step} (see "
            f"{scenario_folder / '_Log' / '_RunTime.txt'}). Voyager exit code: {exit_code}."
        )
    else:
        status = "success"
        error = None
    model_log_result["exit_code_mismatch"] = (status == "success") != (exit_code == 0)
    return status, error, "model_log", model_log_result


def _validate_overrides(
    tdm_path: Path,
    framework: dict,
    calib_run_id: str,
    baseline: dict,
    overrides: dict,
    general_parameter_overrides: dict,
    local_layer: dict,
) -> dict:
    """Hard-fails before anything else in run() executes if any override key
    -- this calibration run's control_center_overrides/
    general_parameter_overrides, or config/local.yaml's machine-specific
    values -- doesn't actually exist in its respective baseline file.
    Returns cc_local_layer (local_layer minus Voyager_EXE, which is a
    framework-only value, not a real Control Center key) for render() to use."""
    cc.validate_overrides(
        baseline, overrides, f"calibration run '{calib_run_id}'.control_center_overrides"
    )
    cc_local_layer = {k: v for k, v in local_layer.items() if k != "Voyager_EXE"}
    cc.validate_overrides(baseline, cc_local_layer, "config/local.yaml")

    if general_parameter_overrides:
        gp_baseline = gp.load_baseline(tdm_path, framework["general_parameters_path"])
        cc.validate_overrides(
            gp_baseline,
            general_parameter_overrides,
            f"calibration run '{calib_run_id}'.general_parameter_overrides",
        )
    return cc_local_layer


def run(repo_root: Path, calib_run_id: str, force: bool = False) -> dict:
    """
    Executes one full attempt of a calibration run: resolve version, render
    Control Center, invoke the TDM, curate outputs, write metadata. Returns
    the run metadata dict. Raises on validation failures that should stop
    execution before anything happens (config errors, unknown override keys,
    unresolvable TDM ref); execution and output failures are instead
    recorded in a 'failed' run record.
    """
    framework = cfg.load_framework_config(repo_root)
    calib_run = cfg.load_calibration_run(repo_root, calib_run_id)

    if not force:
        existing = md.latest_run(repo_root, calib_run_id)
        if existing and existing["status"] == "success":
            return existing

    tdm_path = repo_root / framework["tdm_submodule_path"]
    requested_ref = calib_run["tdm_ref"]
    baseline_filename = calib_run["baseline_control_center"]
    cr_dir = repo_root / "calibration_runs"
    overrides = cfg.resolved_control_center_overrides(calib_run, cr_dir)
    general_parameter_overrides = cfg.resolved_general_parameter_overrides(calib_run)
    output_spec = cfg.resolved_output_spec(framework, calib_run)

    run_id = generate_run_id()
    started_at = md.utc_now_iso()
    fw_commit = md.framework_commit(repo_root)

    # --- version resolution (hard failure stops everything before execution) ---
    version_state = sub.resolve_version(repo_root, tdm_path, requested_ref)

    # --- render Control Center (hard failure on unknown override keys) ---
    baseline = cc.load_baseline(
        tdm_path, framework["control_center_defaults_dir"], baseline_filename
    )
    local_layer = framework.get("_local", {})
    cc_local_layer = _validate_overrides(
        tdm_path, framework, calib_run_id, baseline, overrides, general_parameter_overrides,
        local_layer,
    )

    # --- prep script (hard failure stops this run before execution) ---
    prep.run_prep_scripts(calib_run, cr_dir, calib_run_id)

    folder = run_folder_path(tdm_path, framework, calib_run_id)
    folder.mkdir(parents=True, exist_ok=True)

    # --- seed from a prior calibration run's raw folder, if declared
    # (before this run's own Control Center/driver script are written, so
    # they overwrite any stale copies rather than the other way around) ---
    seeded_from = seed.seed(repo_root, calib_run_id, calib_run, folder)

    # NOTE: ModelDir, not ParentDir -- see module docstring. TDM step scripts
    # throughout 2_ModelScripts/ reference '@ScenarioDir@' standalone (e.g.
    # 0_FolderSetup.s's `FILEO PRINTO = '@ScenarioDir@\0_FolderSetup.txt'`),
    # so ScenarioDir must be absolute, not relative -- matching the baseline
    # template's own convention (Scenarios/_default/_ControlCenter -
    # BY_2023.block sets `ScenarioDir = ModelDir + 'Scenarios\...\'`, itself
    # absolute since ModelDir is). A relative ScenarioDir instead produces
    # F(102) "cannot find the path specified" errors, since RunModel.bat
    # pushes into the scenario folder before invoking Voyager, so a relative
    # ScenarioDir resolves against itself. vizToolDir/ModelDir_Py/
    # ScenarioDir_Py/vizToolDir_Py are left untouched -- they're PILOT
    # expressions built from ModelDir/ScenarioDir in the baseline itself, so
    # they resolve correctly once ModelDir is.
    identity_fields = {
        "ScenarioName": calib_run_id,
        "ScenarioDir": _windows_style(str(folder.resolve()), trailing_sep=True),
        "ModelDir": _windows_style(str(tdm_path.resolve()), trailing_sep=True),
    }
    rendered = cc.render(overrides, cc_local_layer, identity_fields)
    baseline_path = tdm_path / framework["control_center_defaults_dir"] / baseline_filename
    control_center_path = folder / "_ControlCenter.block"
    cc.write_block_file(baseline_path, rendered, control_center_path)

    # --- write the General Parameter override file, if declared (see
    # general_parameters.py) -- driver_script.stage() below inserts the
    # extra READ FILE line that picks this up ---
    if general_parameter_overrides:
        gp.write_override_file(general_parameter_overrides, folder / gp.OVERRIDE_FILENAME)

    # --- stage the driver script: driver_script is required, no framework default ---
    driver_script_path = ds.stage(
        cr_dir,
        tdm_path,
        framework["control_center_defaults_dir"],
        calib_run,
        folder,
    )

    # --- execute ---
    command = build_command(framework, repo_root, control_center_path, folder)
    log_path = folder / "logs" / "orchestrator_invocation.log"
    run_dir = repo_root / "runs" / calib_run_id

    # Write a "running" record to run_info/ *before* invoking the model, not
    # after. invoke() below can run for hours (Cube Voyager); without this,
    # an attempt killed mid-run by a crash or power loss leaves zero trace
    # anywhere -- run_info/ is supposed to be the permanent audit trail of
    # every attempt, so "started but never finished" needs its own record
    # rather than nothing. Overwritten in place (same run_id -> same
    # filename) with the terminal status once the attempt actually finishes.
    _write_running_record(
        framework, run_dir,
        control_center_path=control_center_path,
        driver_script_path=driver_script_path,
        command=command,
        log_path=log_path,
        calib_run_id=calib_run_id,
        run_id=run_id,
        started_at=started_at,
        framework_commit_sha=fw_commit,
        tdm_state=version_state.as_dict(),
        baseline_file=baseline_filename,
        overrides=overrides,
        general_parameter_overrides=general_parameter_overrides,
        seeded_from=seeded_from,
        scenario_folder=str(folder),
    )

    exit_code = invoke(
        command,
        cwd=tdm_path,
        log_path=log_path,
        timeout_seconds=framework["execution"]["timeout_seconds"],
        env={"VOYAGER_EXE": local_layer.get("Voyager_EXE", "")},
    )
    model_log_result = mlog.read_model_log(folder)
    status, error, status_source, model_log_result = decide_status(
        exit_code, model_log_result, log_path, folder
    )
    if status == "failed":
        error = _append_prn_errors(error, folder)

    # --- inventory always (for run_metadata's inventory_count/bytes), but
    # only curate/extract outputs once decide_status's model-log check above
    # -- the only check trusted for this -- has confirmed a clean finish. No
    # more "best effort on failure": a run that didn't unambiguously
    # complete doesn't get its outputs pulled into runs/, partial or not.
    full_inventory = out.inventory(folder)
    # Only the latest attempt's outputs are ever kept on disk for a
    # calib_run_id -- wipe whatever a previous attempt left (everything but
    # run_info/'s permanent history) before this attempt's own curate()
    # recreates it, so a narrowed outputs.include or a failed re-run can't
    # leave stale files behind.
    _reset_run_outputs(run_dir)
    if status == "success":
        status, error, curated = out.curate(
            folder, full_inventory, output_spec, run_dir, status, error, repo_root,
            voyager_exe=local_layer.get("Voyager_EXE"),
        )
    else:
        curated = []

    run_metadata = md.build(
        schema_version=framework["run_metadata_schema_version"],
        calib_run_id=calib_run_id,
        run_id=run_id,
        status=status,
        started_at=started_at,
        framework_commit_sha=fw_commit,
        tdm_state=version_state.as_dict(),
        baseline_file=baseline_filename,
        overrides=overrides,
        general_parameter_overrides=general_parameter_overrides,
        rendered_path=str(control_center_path),
        driver_script=driver_script_path,
        seeded_from=seeded_from,
        scenario_folder=str(folder),
        command=command,
        exit_code=exit_code,
        log_path=str(log_path),
        status_source=status_source,
        model_log=model_log_result,
        inventory_count=len(full_inventory),
        inventory_total_bytes=sum(e["size_bytes"] for e in full_inventory),
        curated=curated,
        finished_at=md.utc_now_iso(),
        error=error,
    )
    md.write(run_dir, run_metadata)

    # --- cache this run's per-stage report data, then re-render the
    # report/ Quarto project so it picks up this run (only on success --
    # resolve_latest_run_outputs() only looks at successful runs anyway, so
    # there's nothing new for a report to show otherwise). Must run after
    # md.write() above: the report's own list_available_runs() only sees a
    # run once its run_metadata.json actually exists on disk -- caching/
    # rendering first would find this run missing. Caching must run before
    # rendering, so the freshly-built cache exists by render time.
    # Re-written into the same file afterward once known. ---
    if status == "success":
        run_metadata["preprocess"] = pp.build_report_cache(repo_root, calib_run_id)
        run_metadata["postprocess"] = pp.render_validation(repo_root, framework)
        md.write(run_dir, run_metadata)

    return run_metadata


def import_manual_run(repo_root: Path, calib_run_id: str, scenario_folder: Path = None) -> dict:
    """
    Curates outputs and records metadata for a calibration run that was
    executed outside the CLI -- e.g. Cube Voyager invoked directly against a
    raw working folder. Applies the same select/size-check/copy sequence
    run() uses after a real execution, so runs/ stays the one place curated
    outputs land regardless of how the model was actually invoked. Does not
    check out, fetch, or otherwise touch the TDM submodule -- only its
    current (read-only) state is recorded, since a checkout here would not
    reflect what was actually used for this manual run anyway.

    scenario_folder defaults to the run's declared manual_scenario_folder
    (relative to the TDM submodule root) when not passed explicitly, falling
    back further to the scenario_folder_template convention
    (Scenarios/<calib_run_id>) already used for CLI-driven runs.

    Unlike run(), there's no skip-if-already-successful check: this is only
    ever invoked deliberately, so the invocation itself is the signal that
    outputs should be (re-)gathered -- every call creates a new timestamped
    run rather than guessing whether the raw folder changed since the last
    import.
    """
    framework = cfg.load_framework_config(repo_root)
    calib_run = cfg.load_calibration_run(repo_root, calib_run_id)

    tdm_path = repo_root / framework["tdm_submodule_path"]
    if scenario_folder is None:
        scenario_folder = cfg.resolved_manual_run_folder(
            tdm_path, framework, calib_run_id, calib_run
        )

    requested_ref = calib_run["tdm_ref"]
    baseline_filename = calib_run["baseline_control_center"]
    cr_dir = repo_root / "calibration_runs"
    overrides = cfg.resolved_control_center_overrides(calib_run, cr_dir)
    general_parameter_overrides = cfg.resolved_general_parameter_overrides(calib_run)
    output_spec = cfg.resolved_output_spec(framework, calib_run)

    run_id = generate_run_id()
    started_at = md.utc_now_iso()
    fw_commit = md.framework_commit(repo_root)
    version_state = sub.current_state(tdm_path, requested_ref)

    local_layer = framework.get("_local", {})
    full_inventory = out.inventory(scenario_folder)
    run_dir = repo_root / "runs" / calib_run_id
    # Same "latest attempt only" wipe as run() -- see its comment.
    _reset_run_outputs(run_dir)
    status, error, curated = out.curate(
        scenario_folder, full_inventory, output_spec, run_dir, "success", None, repo_root,
        voyager_exe=local_layer.get("Voyager_EXE"),
    )

    run_metadata = md.build(
        schema_version=framework["run_metadata_schema_version"],
        calib_run_id=calib_run_id,
        run_id=run_id,
        status=status,
        started_at=started_at,
        framework_commit_sha=fw_commit,
        tdm_state=version_state.as_dict(),
        baseline_file=baseline_filename,
        overrides=overrides,
        general_parameter_overrides=general_parameter_overrides,
        scenario_folder=str(scenario_folder),
        inventory_count=len(full_inventory),
        inventory_total_bytes=sum(e["size_bytes"] for e in full_inventory),
        curated=curated,
        finished_at=md.utc_now_iso(),
        error=error,
        execution_mode="manual",
    )
    md.write(run_dir, run_metadata)

    # --- cache this run's per-stage report data, then re-render the
    # report/ Quarto project so it picks up this run (only on success --
    # same reasoning/ordering as run()) ---
    if status == "success":
        run_metadata["preprocess"] = pp.build_report_cache(repo_root, calib_run_id)
        run_metadata["postprocess"] = pp.render_validation(repo_root, framework)
        md.write(run_dir, run_metadata)

    return run_metadata


def import_manual_run_all(repo_root: Path, only: list = None) -> list:
    """
    Runs import_manual_run() for every calibration run declared under
    calibration_runs/, resolving each one's raw folder via
    resolved_manual_run_folder(). A run whose resolved folder doesn't
    actually hold the declared outputs.include patterns is recorded as a
    failed result rather than stopping the rest.
    """
    calib_run_ids = cfg.list_calibration_run_ids(repo_root)
    if only:
        calib_run_ids = [c for c in calib_run_ids if c in only]
    results = []
    for calib_run_id in calib_run_ids:
        try:
            results.append(import_manual_run(repo_root, calib_run_id))
        except Exception as e:  # noqa: BLE001 -- one run's error shouldn't stop the rest
            results.append(
                {
                    "calib_run_id": calib_run_id,
                    "run_id": None,
                    "status": "failed",
                    "error": str(e),
                }
            )
    return results


def run_all(repo_root: Path, only: list = None, force: bool = False) -> list:
    """
    Runs every calibration run declared under calibration_runs/ sequentially.
    A failed run does not stop the rest -- successful runs already on disk
    are untouched, and the function returns metadata for every attempted
    run so the caller can report a clear success/failure summary.
    """
    calib_run_ids = cfg.list_calibration_run_ids(repo_root)
    if only:
        calib_run_ids = [c for c in calib_run_ids if c in only]
    results = []
    for calib_run_id in calib_run_ids:
        try:
            results.append(run(repo_root, calib_run_id, force=force))
        except Exception as e:  # noqa: BLE001 -- config/version errors stop this run, not the rest
            results.append(
                {
                    "calib_run_id": calib_run_id,
                    "run_id": None,
                    "status": "failed",
                    "error": str(e),
                }
            )
    return results
