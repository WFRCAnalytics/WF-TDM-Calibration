r"""Staging of the driver script (_HailMary.s variant) for a run.

The TDM's Scenarios/_default/ library ships __HailMary.s, whose
'..\..\...' READ FILE paths resolve two levels up to the tdm/ root --
exactly the depth of the per-run working folder this framework creates
(Scenarios/{calib_run_id}/, see config/framework.yaml's
scenario_folder_template and default_driver_script's comment). The
_1Subfolder variants resolve three levels up instead and fail here. Every
run stages a copy of the configured default into that folder before
execution, alongside the rendered _ControlCenter.block.

A calibration run may declare driver_script to stage its own copy instead --
e.g. to add, remove, or replace a step. The custom file lives in the
calibration_runs/ directory (e.g. calibration_runs/hail-mary/
__HailMary_1Subfolder_c50.s) and is staged keeping its own on-disk filename,
not renamed to match the default's.

Either way, only the one driver script file itself is staged. Companion or
modified step scripts referenced by a custom driver script are NOT staged --
they stay wherever calibration_runs/ keeps them and must be referenced from
the staged file by a relative path computed back to that location, the same
way the default file's own '..\..\..\2_ModelScripts\...' references are
relative to wherever it ends up running from.

A calibration run's raw working folder is reused across every run attempt
(no run_id component in scenario_folder_template), so a driver script staged
by an earlier attempt (the default, or a different custom one) can still be
sitting there from before. bin/RunModel.bat locates the driver script by
globbing the folder for *.s, so more than one present is ambiguous. stage()
therefore deletes any *.s files already present before copying the resolved
one in, keeping the invariant that exactly one is ever present.

This is a distinct mechanism from Control Center overrides (controlcenter.py):
it substitutes which code runs, not a parameter value, so it never touches
the overrides dict or its baseline-key validation.

Ported from WF-TDM-Runs' src/tdmruns/driver_script.py, flattened for the
single-layer calibration run config (no run_set/scenario precedence)."""

import shutil
from pathlib import Path

from tdmcalib import config as cfg
from tdmcalib.exceptions import DriverScriptError


def stage(
    calib_run_dir: Path,
    tdm_path: Path,
    defaults_dir: str,
    default_filename: str,
    calib_run: dict,
    run_folder: Path,
) -> str:
    """Copies the resolved driver script into run_folder, keeping its own
    filename. Uses the calibration run's declared driver_script if any,
    otherwise the TDM's own default_filename under defaults_dir. Always
    stages something. Returns the source path for the metadata record --
    calibration_runs/-relative for a custom script, tdm-relative for the
    default."""
    declared = cfg.resolved_driver_script(calib_run)
    if declared:
        script_path = calib_run_dir / declared
        source_label = declared
    else:
        script_path = tdm_path / defaults_dir / default_filename
        source_label = f"{defaults_dir}/{default_filename}"

    if not script_path.is_file():
        raise DriverScriptError(f"driver_script not found: {script_path}")

    for stale in run_folder.glob("*.s"):
        stale.unlink()

    shutil.copy2(script_path, run_folder / script_path.name)

    return source_label
