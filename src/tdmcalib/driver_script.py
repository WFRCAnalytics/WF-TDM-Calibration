r"""Staging of the driver script (_HailMary.s variant) for a run.

The TDM's Scenarios/_default/ library ships __HailMary.s, whose
'..\..\...' READ FILE paths resolve two levels up to the tdm/ root --
exactly the depth of the per-run working folder this framework creates
(Scenarios/{calib_run_id}/, see config/framework.yaml's
scenario_folder_template comment). The _1Subfolder variants resolve three
levels up instead and fail here.

Every calibration run must declare driver_script (required by
calibration_run.schema.json) -- there is no framework-wide default it falls
back to, so which driver script ran is always explicit in the run's own
config, never an assumption baked into the framework. declared is resolved
first against calibration_runs/ (a fully custom file, e.g.
calibration_runs/hail-mary/__HailMary_1Subfolder_c50.s -- companion/modified
step scripts it references are NOT auto-staged, they stay wherever
calibration_runs/ keeps them, referenced by a relative path computed back to
that location the same way the default file's own
'..\..\..\2_ModelScripts\...' references are relative to wherever it ends up
running from), then as a bare filename against defaults_dir (a TDM-provided
variant, e.g. __HailMary.s or __HailMary_resumable.s -- same 2-levels-up path
convention, so no relative-path rewriting is needed). Either way, the staged
copy keeps its own filename, not renamed to match anything else.

A calibration run's raw working folder is reused across every run attempt
(no run_id component in scenario_folder_template), so a driver script staged
by an earlier attempt (a different driver_script value at the time) can still
be sitting there from before. bin/RunModel.bat locates the driver script by
globbing the folder for *.s, so more than one present is ambiguous. stage()
therefore deletes any *.s files already present before copying the resolved
one in, keeping the invariant that exactly one is ever present.

Every calibration run also declares start_at_label (required by the same
schema). 'STEP0' -- the default for all new calibration runs -- means a
normal run from the beginning, so no rewrite happens. Any other value means
the run is resuming: the staged copy (in the per-run working folder, not the
tdm/ source library staged from -- the same "fair game" scratch area write()
already uses for the rendered _ControlCenter.block) has its RESUME POINT
line's GOTO target rewritten to that label, so a crashed run can be picked
back up without re-running the steps that already completed. Requires the
resolved driver script to actually contain a RESUME POINT marker (see
_rewrite_resume_point) -- raises DriverScriptError otherwise, since a
silently-ignored start_at_label would be worse than an explicit failure.

This is a distinct mechanism from Control Center overrides (controlcenter.py):
it substitutes which code runs, not a parameter value, so it never touches
the overrides dict or its baseline-key validation.

Ported from WF-TDM-Runs' src/tdmruns/driver_script.py, flattened for the
single-layer calibration run config (no run_set/scenario precedence)."""

import re
import shutil
from pathlib import Path

from tdmcalib import config as cfg
from tdmcalib.exceptions import DriverScriptError

# Matches the RESUME POINT marker comment in a resumable driver script
# template (see calibration_runs/hail-mary/ or the TDM's own
# Scenarios/_default/__HailMary_resumable.s) through its GOTO line, keeping
# the line's own indentation but capturing the label so it can be swapped
# for start_at_label's value. Cube Voyager PILOT's GOTO takes a bare label
# (no ':' prefix -- that's only for the label's own definition).
_RESUME_POINT_RE = re.compile(r"(RESUME POINT:.*?\n[ \t]*GOTO )(:?)([A-Za-z0-9_]+)", re.DOTALL)

# start_at_label value meaning "run from the beginning" -- the required
# default for all new calibration runs. No RESUME POINT rewrite is performed
# for this value, so it's valid regardless of which driver script is staged.
STEP0 = "STEP0"


def _rewrite_resume_point(text: str, label: str, script_path: Path) -> str:
    new_text, n = _RESUME_POINT_RE.subn(rf"\g<1>{label}", text, count=1)
    if n == 0:
        raise DriverScriptError(
            f"start_at_label is '{label}' but {script_path} has no 'RESUME POINT' "
            "GOTO marker to rewrite -- it isn't a resumable driver script variant."
        )
    return new_text


def stage(
    calib_run_dir: Path,
    tdm_path: Path,
    defaults_dir: str,
    calib_run: dict,
    run_folder: Path,
) -> str:
    """Copies the calibration run's declared driver script into run_folder,
    keeping its own filename. driver_script is required (see
    calibration_run.schema.json) -- there is no framework-default fallback,
    so every run's driver script is an explicit, traceable choice, not a
    silently-assumed one. Resolved against calibration_runs/ first (a fully
    custom file), then as a bare filename against defaults_dir. Returns the
    source path for the metadata record -- calibration_runs/-relative for a
    custom script, tdm-relative otherwise.

    When start_at_label is anything other than STEP0, the staged copy's
    RESUME POINT GOTO target is rewritten to that label after copying (see
    _rewrite_resume_point) -- the source file itself is never modified."""
    declared = cfg.resolved_driver_script(calib_run)
    if (calib_run_dir / declared).is_file():
        script_path = calib_run_dir / declared
        source_label = declared
    else:
        script_path = tdm_path / defaults_dir / declared
        source_label = f"{defaults_dir}/{declared}"

    if not script_path.is_file():
        raise DriverScriptError(f"driver_script not found: {script_path}")

    for stale in run_folder.glob("*.s"):
        stale.unlink()

    dest_path = run_folder / script_path.name
    start_at_label = calib_run["start_at_label"]
    if start_at_label != STEP0:
        text = script_path.read_text()
        dest_path.write_text(_rewrite_resume_point(text, start_at_label, script_path))
    else:
        shutil.copy2(script_path, dest_path)

    return source_label
