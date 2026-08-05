"""Execution of an optional input-preparation script declared in a
calibration run's YAML.

The script is a plain Python file. The framework invokes it with two named
arguments so it can locate calibration_runs/'s inputs and know which
calibration run it is prepping:

    python <script> --calib-run-dir <abs-path> --calib-run-id <id>

Absent is not an error. A non-zero exit code is a hard failure that stops
execution before the model is touched.

Ported from WF-TDM-Runs' src/tdmruns/prep.py, flattened to a single prep
script per calibration run (no run_set-level + scenario-level pair)."""

import subprocess
import sys
from pathlib import Path

from tdmcalib.exceptions import PrepScriptError


def run_prep_scripts(calib_run: dict, calib_run_dir: Path, calib_run_id: str) -> None:
    """Run the calibration run's declared prep_script, if any. Path is
    resolved relative to calib_run_dir. Output streams to the caller's
    terminal."""
    script = calib_run.get("prep_script")
    if not script:
        return
    script_path = calib_run_dir / script
    if not script_path.is_file():
        raise PrepScriptError(f"Prep script not found: {script_path}")
    cmd = [
        sys.executable,
        str(script_path),
        "--calib-run-dir", str(calib_run_dir),
        "--calib-run-id", calib_run_id,
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise PrepScriptError(
            f"Prep script '{script_path.name}' exited with code {result.returncode}."
        )
