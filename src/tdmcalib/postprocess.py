"""
Post-run report rendering.

Runs `quarto render` against the repo-root Quarto project after a
calibration run's outputs are curated, so report/*.qmd reflects the run
automatically -- replacing the old manual "preprocess" toggle that
report/config.json used to gate (see report/README.md). Rendering failure
never raises: the calibration run's curated outputs are already safely on
disk regardless of whether the report re-rendered cleanly, so a rendering
problem is recorded on the run's metadata instead of failing the run.
"""

import shutil
import subprocess
from pathlib import Path


def render_validation(repo_root: Path, framework: dict) -> dict:
    """
    Renders the repo-root Quarto project (index.qmd + report/**/*.qmd, per
    _quarto.yml) via `quarto render`. Returns a dict with at least a
    "status" key ("skipped", "success", or "failed") describing the
    outcome; never raises.
    """
    pp_cfg = framework.get("postprocess", {})
    if not pp_cfg.get("render_validation", False):
        return {"status": "skipped", "reason": "postprocess.render_validation is false"}

    quarto_exe = pp_cfg.get("quarto_exe", "quarto")
    if shutil.which(quarto_exe) is None:
        return {"status": "failed", "reason": f"'{quarto_exe}' not found on PATH"}

    timeout_seconds = pp_cfg.get("timeout_seconds", 3600)
    try:
        result = subprocess.run(
            [quarto_exe, "render", "."],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {"status": "failed", "reason": f"quarto render timed out after {timeout_seconds}s"}

    if result.returncode != 0:
        return {
            "status": "failed",
            "reason": f"quarto render exited {result.returncode}",
            "stderr_tail": result.stderr[-4000:],
        }
    return {"status": "success"}
