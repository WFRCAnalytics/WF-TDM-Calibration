"""TDM submodule version resolution.

v1 design: the submodule is checked out in place and calibration runs execute
sequentially (one TDM version at a time), matching how the TDM batch entry
point actually executes -- in place, inside its own checkout, using its own
Scenarios/ folder convention. A dirty working tree or an unresolvable ref is
always a hard failure, never a warning, since silent execution against an
ambiguous checkout is exactly what destroys reproducibility later -- and
directly matches this repo's own CLAUDE.md rule against floating the
submodule pointer as a side effect.

Ported unchanged from WF-TDM-Runs' src/tdmruns/submodule.py."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from tdmcalib.exceptions import VersionResolutionError


def _git(args, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        raise VersionResolutionError(
            f"git {' '.join(args)} (in {cwd}) failed:\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


@dataclass
class TdmVersionState:
    requested_ref: str
    resolved_commit: str
    resolved_tag: str | None
    branch: str | None
    detached_head: bool
    dirty: bool

    def as_dict(self) -> dict:
        return {
            "requested_ref": self.requested_ref,
            "resolved_commit": self.resolved_commit,
            "resolved_tag": self.resolved_tag,
            "branch": self.branch,
            "detached_head": self.detached_head,
            "dirty": self.dirty,
        }


def ensure_initialized(repo_root: Path, tdm_path: Path):
    if not (tdm_path / ".git").exists():
        _git(["submodule", "update", "--init", "--recursive", str(tdm_path)], cwd=repo_root)


def is_dirty(tdm_path: Path) -> bool:
    status = _git(["status", "--porcelain"], cwd=tdm_path)
    return bool(status)


def _inspect_head(tdm_path: Path, requested_ref: str, dirty: bool) -> TdmVersionState:
    """Reads back whatever commit/branch/tags are currently at HEAD. Read-only
    -- does not fetch, checkout, or otherwise mutate the working tree."""
    resolved_commit = _git(["rev-parse", "HEAD"], cwd=tdm_path)

    branch_result = subprocess.run(
        ["git", "symbolic-ref", "-q", "--short", "HEAD"],
        cwd=str(tdm_path),
        capture_output=True,
        text=True,
    )
    branch = branch_result.stdout.strip() or None
    detached_head = branch is None

    tags_at_head = _git(["tag", "--points-at", "HEAD"], cwd=tdm_path)
    tag_list = [t for t in tags_at_head.splitlines() if t]
    resolved_tag = requested_ref if requested_ref in tag_list else (tag_list[0] if tag_list else None)

    return TdmVersionState(
        requested_ref=requested_ref,
        resolved_commit=resolved_commit,
        resolved_tag=resolved_tag,
        branch=branch,
        detached_head=detached_head,
        dirty=dirty,
    )


def current_state(tdm_path: Path, requested_ref: str) -> TdmVersionState:
    """Read-only inspection of whatever the submodule is currently checked
    out to -- no fetch, no checkout, no mutation. For recording TDM state
    against a run that wasn't executed through resolve_version (e.g. run
    manually outside the CLI), where checking out `requested_ref` now would
    not reflect what was actually used and would be a surprising side effect
    of what's meant to be an outputs-gathering step."""
    return _inspect_head(tdm_path, requested_ref, dirty=is_dirty(tdm_path))


def resolve_version(repo_root: Path, tdm_path: Path, ref: str) -> TdmVersionState:
    """Checks out `ref` in the TDM submodule and returns the actual resolved
    state. Raises VersionResolutionError if the ref does not exist or the
    working tree is dirty either before or after checkout."""
    ensure_initialized(repo_root, tdm_path)

    if is_dirty(tdm_path):
        raise VersionResolutionError(
            f"TDM submodule at {tdm_path} has uncommitted local changes. "
            "Refusing to check out a new version over a dirty working tree -- "
            "commit, stash, or discard the changes first."
        )

    try:
        # --force so a tag that was moved (force-pushed) on the remote --
        # e.g. a fixup tag under active iteration -- is actually updated
        # locally instead of silently left pointing at the old commit.
        _git(["fetch", "--all", "--tags", "--force", "--quiet"], cwd=tdm_path)
    except VersionResolutionError:
        # Best effort: a local-path or offline remote may not support fetch
        # the same way a real remote does. Proceed with what's already local;
        # checkout below will fail clearly if the ref truly isn't available.
        pass

    try:
        _git(["checkout", "--quiet", ref], cwd=tdm_path)
    except VersionResolutionError as e:
        raise VersionResolutionError(
            f"Requested TDM version '{ref}' could not be checked out in {tdm_path}. "
            f"Verify the tag, branch, or commit exists in the TDM repository.\n{e}"
        )

    if is_dirty(tdm_path):
        raise VersionResolutionError(
            f"TDM submodule working tree at {tdm_path} is dirty immediately "
            f"after checking out '{ref}'. This should not happen on a clean "
            "checkout -- investigate before trusting this run's results."
        )

    return _inspect_head(tdm_path, ref, dirty=False)


def short_version_label(state: TdmVersionState) -> str:
    """A filesystem-safe label for the resolved version. Prefers the tag
    (most human-readable), falls back to a short commit SHA."""
    return state.resolved_tag or state.resolved_commit[:8]
