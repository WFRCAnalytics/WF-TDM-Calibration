"""Cube Voyager matrix conversion helpers -- used by outputs.py's matrix-type
curation. numpy/openmatrix can't read Cube's native .mtx (TPP) format
directly, so CONVERTMAT is invoked by writing a one-line .s script plus a
.bat wrapper and shelling out to VOYAGER.EXE.

Ported unchanged from WF-TDM-Runs' src/tdmruns/matrix_utils.py."""
import subprocess
import tempfile
from pathlib import Path

import openmatrix as omx

from tdmcalib.exceptions import OutputCollectionError


def _run_convertmat(script_path: Path, bat_path: Path, voyager_exe: str):
    # Empty "" title is required before the quoted exe path -- see
    # bin/RunModel.bat's own `start /w ""` invocation. Without it, cmd.exe
    # treats the exe path itself as the window title and tries to run a bare
    # (unqualified) VOYAGER.EXE instead, which fails to resolve.
    with open(bat_path, "w") as f:
        f.write(f'start /w "" "{voyager_exe}" "{script_path.resolve()}" /start -Report\n')
    subprocess.call(str(bat_path), cwd=str(bat_path.parent))


def convert_mtx_to_omx(mtx_path: Path, omx_path: Path, voyager_exe: str):
    # CONVERTMAT's own script/batch files and Voyager's TPPL*.PRN/.VAR/.PRJ
    # print logs land in whatever directory the .bat is run from -- a
    # dedicated temp dir keeps those out of omx_path's own directory (which,
    # for outputs.py's matrix curation, is the run's committed outputs/
    # folder; those incidental artifacts must never end up there).
    # ignore_cleanup_errors: Voyager's own process exit (via the `start /w`
    # wrapper) doesn't always release its file handles on this directory's
    # contents (TPPL*.PRN/.VAR/.PRJ logs) the instant it returns -- observed
    # in practice as an intermittent WinError 32 ("file in use") from this
    # context manager's own teardown, even though the conversion itself had
    # already succeeded. The scratch files left behind are harmless (OS temp
    # cleanup reclaims them eventually); letting this raise was worse, since
    # it aborted extract_matrix_tabs() before its own temp_full_omx cleanup
    # could run, stranding a full (unrimmed, sometimes 100+ MB) matrix
    # conversion in the destination's own directory.
    with tempfile.TemporaryDirectory(prefix="convertmat_", ignore_cleanup_errors=True) as work_dir_str:
        work_dir = Path(work_dir_str)
        script_path = work_dir / f"_convert_in_{mtx_path.stem}.s"
        bat_path = work_dir / f"_convert_in_{mtx_path.stem}.bat"
        with open(script_path, "w") as f:
            f.write(
                f'convertmat from="{mtx_path.resolve()}", to="{omx_path.resolve()}", '
                f'compression=2, format="omx"\n'
            )
        _run_convertmat(script_path, bat_path, voyager_exe)
        if not omx_path.exists():
            raise RuntimeError(f"CONVERTMAT did not produce {omx_path} -- check {bat_path} output")


def convert_omx_to_mtx(omx_path: Path, mtx_path: Path, voyager_exe: str):
    # ignore_cleanup_errors: see convert_mtx_to_omx's comment above.
    with tempfile.TemporaryDirectory(prefix="convertmat_", ignore_cleanup_errors=True) as work_dir_str:
        work_dir = Path(work_dir_str)
        script_path = work_dir / f"_convert_out_{mtx_path.stem}.s"
        bat_path = work_dir / f"_convert_out_{mtx_path.stem}.bat"
        with open(script_path, "w") as f:
            f.write(f'convertmat from="{omx_path.resolve()}", to="{mtx_path.resolve()}", format=TPP\n')
        _run_convertmat(script_path, bat_path, voyager_exe)
        if not mtx_path.exists():
            raise RuntimeError(f"CONVERTMAT did not produce {mtx_path} -- check {bat_path} output")


def trim_omx_tabs(source_omx: Path, tabs: list, dest_path: Path) -> None:
    """Keeps only the named tables from an already-OMX source, writing the
    result to dest_path. Pure Python (openmatrix) -- no Voyager/CONVERTMAT
    involved, since the source is already in a format numpy/openmatrix can
    read directly. Used for matrix entries whose source_format is "omx"
    rather than the default "mtx" -- e.g. importing a calibration run whose
    raw output was archived as OMX (already converted by whatever produced
    it) rather than Cube's native TPP format. Raises OutputCollectionError
    naming the available tables if any requested tab isn't present, same as
    extract_matrix_tabs()."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    src = omx.open_file(str(source_omx), "r")
    try:
        available = src.list_matrices()
        missing = [t for t in tabs if t not in available]
        if missing:
            raise OutputCollectionError(
                f"tabs {missing} not found in {source_omx.name} (available: {available})"
            )
        dst = omx.open_file(str(dest_path), "w")
        try:
            for tab in tabs:
                dst[tab] = src[tab]
        finally:
            dst.close()
    finally:
        src.close()


def extract_matrix_tabs(
    source_mtx: Path,
    tabs: list,
    dest_path: Path,
    voyager_exe: str,
    output_format: str = "omx",
    source_format: str = "mtx",
) -> None:
    """Converts source_mtx (a full, possibly huge, multi-table Cube matrix)
    to a temporary full OMX via CONVERTMAT, then keeps only the named tabs
    -- deleting the temporary full conversion afterward regardless of
    outcome. Raises OutputCollectionError naming the available tables if any
    requested tab isn't present, so a typo'd tabs: entry in a calibration
    run's YAML fails clearly rather than silently.

    source_format="mtx" (default) assumes source_mtx is Cube's native TPP
    format and requires voyager_exe. source_format="omx" means source_mtx is
    already OMX -- trims it directly via trim_omx_tabs(), no Voyager needed,
    and output_format must be "omx" (there'd be no reason to round-trip an
    already-OMX source back out to OMX via a different path; converting an
    already-OMX source to Cube's native format isn't something curation
    needs, so it isn't supported here).

    output_format="omx" (default) writes the trimmed tables directly to
    dest_path as an OMX file. output_format="mtx" writes them to a small
    temporary OMX first, then converts that back to Cube's own native TPP
    matrix format at dest_path via CONVERTMAT -- for a curated output meant
    to be read by Cube Voyager itself, not Python. Only valid when
    source_format="mtx"."""
    if source_format == "omx":
        if output_format != "omx":
            raise OutputCollectionError(
                f"matrix entry for {source_mtx.name} has source_format 'omx' but "
                f"output_format '{output_format}' -- only output_format 'omx' is "
                "supported when the source is already OMX."
            )
        trim_omx_tabs(source_mtx, tabs, dest_path)
        return

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_full_omx = dest_path.parent / f"_full_{source_mtx.stem}.omx"
    try:
        convert_mtx_to_omx(source_mtx, temp_full_omx, voyager_exe)
        trimmed_omx = dest_path if output_format == "omx" else (
            dest_path.parent / f"_trimmed_{source_mtx.stem}.omx"
        )
        try:
            trim_omx_tabs(temp_full_omx, tabs, trimmed_omx)
            if output_format == "mtx":
                convert_omx_to_mtx(trimmed_omx, dest_path, voyager_exe)
        finally:
            if output_format == "mtx" and trimmed_omx.exists():
                trimmed_omx.unlink()
    finally:
        if temp_full_omx.exists():
            temp_full_omx.unlink()
