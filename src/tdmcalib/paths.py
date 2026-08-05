"""Shared path resolution. The CLI can be invoked from anywhere inside the
repo; these helpers find the repo root by looking for config/framework.yaml,
rather than assuming the current working directory is the root."""

from pathlib import Path

from tdmcalib.exceptions import tdmcalibError


def find_repo_root(start: Path = None) -> Path:
    start = Path(start or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "config" / "framework.yaml").is_file():
            return candidate
    raise tdmcalibError(
        f"Could not find a tdmcalib repo root above {start} (looked for config/framework.yaml)."
    )


def calibration_runs_dir(repo_root: Path) -> Path:
    return repo_root / "calibration_runs"


def calibration_run_file(repo_root: Path, calib_run_id: str) -> Path:
    return calibration_runs_dir(repo_root) / f"{calib_run_id}.yaml"


def runs_dir(repo_root: Path, calib_run_id: str = None, run_id: str = None) -> Path:
    p = repo_root / "runs"
    if calib_run_id:
        p = p / calib_run_id
        if run_id:
            p = p / run_id
    return p
