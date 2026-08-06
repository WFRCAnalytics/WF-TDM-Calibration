"""
Post-run report caching and rendering.

Two steps run after a calibration run's outputs are curated, in order:
build_report_cache() extracts+caches this run's per-stage report data
(report/preprocess/), then render_validation() runs `quarto render` so
report/*.qmd reflects the run automatically -- replacing the old manual
"preprocess" toggle that report/config.json used to gate (see
report/README.md). Neither ever raises: the calibration run's curated
outputs are already safely on disk regardless of whether caching/rendering
succeeded, so a problem in either is recorded on the run's metadata instead
of failing the run.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def build_report_cache(repo_root: Path, calib_run_id: str) -> dict:
    """
    Runs `python -m report.preprocess.build_cache --run <calib_run_id>`
    (see report/preprocess/), which extracts+caches this run's per-stage
    report data (runs/{calib_run_id}/cache/*.parquet) so report/*.qmd reads
    cheap pre-built files instead of re-parsing raw OMX/DBF/CSV on every
    render. Must run before render_validation() so the freshly-curated
    run's cache exists by the time Quarto renders. Returns a dict with a
    "status" key ("success" or "failed"); never raises -- report/*.qmd's
    own load_cached_per_run() names the exact command to fix a stale/missing
    cache if this step didn't run or failed.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "report.preprocess.build_cache", "--run", calib_run_id],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return {"status": "failed", "reason": "report cache build timed out after 1800s"}

    if result.returncode != 0:
        return {
            "status": "failed",
            "reason": f"report cache build exited {result.returncode}",
            "stdout_tail": result.stdout[-4000:],
        }
    return {"status": "success"}


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
