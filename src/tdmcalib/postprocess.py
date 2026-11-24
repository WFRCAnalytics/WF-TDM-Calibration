"""
Post-run report caching, rendering, and git publish.

Three steps run after a calibration run's outputs are curated, in order:
build_report_cache() extracts+caches this run's per-stage report data
(report/preprocess/), then render_validation() runs `quarto render` so
report/*.qmd reflects the run automatically -- replacing the old manual
"preprocess" toggle that report/config.json used to gate (see
report/README.md) -- then publish_to_git() commits+pushes the curated
outputs, submodule pointer, and re-rendered report to the remote, replacing
the standing habit of doing that by hand after every run (see CLAUDE.md and
the commit-push-autonomy project convention). None of the three ever raise:
the calibration run's curated outputs are already safely on disk regardless
of whether caching/rendering/publishing succeeded, so a problem in any of
them is recorded on the run's metadata instead of failing the run.
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
        # --no-clean: a plain `quarto render` deletes docs/ before writing it
        # back, which fails outright on Windows if anything -- a stray local
        # `quarto preview`, Explorer, antivirus, OneDrive -- holds so much as
        # a file handle open under it. --no-clean overwrites in place instead,
        # so this step can't be silently skipped by an unrelated process
        # having docs/ open; it only risks leaving an orphaned HTML file
        # behind if a .qmd page was deleted, which a manual `quarto render`
        # cleans up next time docs/ isn't locked by anything.
        result = subprocess.run(
            [quarto_exe, "render", ".", "--no-clean"],
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


# Each group is committed separately (its own `git add` + `git commit`) so
# that, e.g., a submodule pointer change still gets committed even if the
# report re-render produced nothing to commit. Paths are explicit pathspecs,
# never `git add -A`, so this never sweeps in unrelated dirty state
# elsewhere in the working tree -- only the files this calibration run's own
# sync-tdm/curate/render steps could plausibly have touched.
_PUBLISH_GROUPS = [
    (["tdm"], "Record tdm submodule pointer for {calib_run_id}"),
    (
        ["scenario-configs/{calib_run_id}.yaml", "runs/{calib_run_id}"],
        "Add {calib_run_id} calibration run outputs",
    ),
    (["docs", "report/_pictures"], "Re-render reports with {calib_run_id}"),
]


def publish_to_git(
    repo_root: Path, calib_run_id: str, framework: dict, render_status: str | None = None
) -> dict:
    """
    Commits and pushes this run's curated outputs, submodule pointer, and
    re-rendered report to the remote -- the same three commits (submodule
    pointer / runs+scenario-configs / docs+report pictures) a manual
    commit-after-a-run has used, now automatic. Only commits paths relevant
    to this calib_run_id (see _PUBLISH_GROUPS); never `git add -A`. A group
    with nothing changed under its paths is skipped rather than producing an
    empty commit. Returns a dict with a "status" key ("skipped", "success",
    or "failed"); never raises -- a push failure (or nothing to push) leaves
    the calibration run's outputs exactly as safely committed/curated as
    they already were.

    render_status is render_validation()'s own "status" ("success", "failed",
    or "skipped") for this same run. When it's "failed", the docs/report
    group is never committed -- `quarto render`'s cleanup step can leave
    docs/ emptied or partial (e.g. a stale local preview server holding a
    file lock), and committing+pushing that would put a broken report on the
    live GitHub Pages site. The other two groups (tdm pointer, runs+scenario-configs)
    are independent of rendering and still get published normally.
    """
    pub_cfg = framework.get("postprocess", {})
    if not pub_cfg.get("git_publish", False):
        return {"status": "skipped", "reason": "postprocess.git_publish is false"}

    def _git(args):
        return subprocess.run(
            ["git", *args], cwd=str(repo_root), capture_output=True, text=True
        )

    committed = []
    skipped_render_failed = False
    for raw_paths, raw_message in _PUBLISH_GROUPS:
        if raw_paths == ["docs", "report/_pictures"] and render_status == "failed":
            skipped_render_failed = True
            continue
        paths = [p.format(calib_run_id=calib_run_id) for p in raw_paths]
        paths = [p for p in paths if (repo_root / p).exists()]
        if not paths:
            continue
        status = _git(["status", "--porcelain", "--", *paths])
        if not status.stdout.strip():
            continue
        add = _git(["add", "--", *paths])
        if add.returncode != 0:
            return {
                "status": "failed",
                "reason": f"git add failed: {add.stderr.strip()}",
                "committed": committed,
            }
        message = raw_message.format(calib_run_id=calib_run_id)
        message += "\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
        commit = _git(["commit", "-m", message])
        if commit.returncode != 0:
            return {
                "status": "failed",
                "reason": f"git commit failed: {commit.stderr.strip()}",
                "committed": committed,
            }
        committed.append(message)

    if not committed:
        if skipped_render_failed:
            return {
                "status": "skipped",
                "reason": "nothing to commit (docs/report group skipped: render_validation failed)",
            }
        return {"status": "skipped", "reason": "nothing to commit"}

    try:
        push = subprocess.run(
            ["git", "push"], cwd=str(repo_root), capture_output=True, text=True, timeout=1800
        )
    except subprocess.TimeoutExpired:
        return {"status": "failed", "reason": "git push timed out after 1800s", "committed": committed}

    if push.returncode != 0:
        return {
            "status": "failed",
            "reason": f"git push failed: {push.stderr.strip()}",
            "committed": committed,
        }
    result = {"status": "success", "committed": committed}
    if skipped_render_failed:
        result["reason"] = "docs/report group skipped: render_validation failed"
    return result
