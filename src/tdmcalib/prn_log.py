"""Extracts Cube Voyager's own fatal-error messages from the scenario
folder's PRN print files, to fold the actual "F(NNN): <description>" text
into a failed run's error message alongside model_log.py's crashed_step
(which only names the .s step, not what Voyager itself reported).

Voyager numbers PRN files sequentially per RUN PGM= step (TPPLnnnn.PRN, ...)
directly in the scenario folder -- the same folder as _ControlCenter.block
and the Hail Mary driver script, never nested in a subfolder like
Temp/4_ModeChoice/ (those are step-local working copies, not where the
driver script's own PRN trail lands). __HailMary.s deletes every *.PRN there
at :BEGINMODEL (`*(DEL *.PRN)`), so whichever one has the newest mtime when a
run fails is unambiguously the one Voyager was writing when it crashed.

Voyager's own runtime messages follow a `<Letter>(<code>): <description>`
line format -- confirmed from a real crash:

    F(004): Problems opening ..\\..\\..\\2_ModelScripts\\2_Tripgen\\1_TripGen_vizTool.s (err=2)
    F(004): OS reports: The system cannot find the file specified.

and from a real non-fatal example already seen in this repo's own PRN output
(tdm/Scenarios/C51/TPPL0017.PRN):

    M(792): ARRAY NEIGHBORS requires 80 bytes.

F(...) is fatal, M(...) is an informational memory-allocation message, and
plain "F(x)" also shows up unrelated to any of this -- as a function/field
reference inside PILOT expressions (e.g. `F(2)`). What distinguishes a real
Voyager message from that is the fixed `): ` immediately after the code, and
that it always starts the line (Voyager, not scripted PILOT code, writes
it) -- an expression's `F(2)` never appears at the start of a line followed
by a colon. Anchoring on `^F(\\d+):` at line-start, rather than a bare
`F(\\d+)` search anywhere in the line, is what keeps this from matching
equation/field-reference uses of the same letter+parens shape.
"""

import re
from pathlib import Path

_FATAL_LINE_RE = re.compile(r"^\s*F\(\s*\d+\s*\):.*$", re.MULTILINE)


def find_latest_prn(scenario_folder: Path) -> Path | None:
    """The most recently written *.PRN file directly in scenario_folder (not
    recursive -- see module docstring), or None if there isn't one."""
    prns = [p for p in scenario_folder.glob("*.PRN") if p.is_file()]
    if not prns:
        return None
    return max(prns, key=lambda p: p.stat().st_mtime)


def extract_fatal_errors(prn_path: Path) -> list:
    """Every F(NNN): line in prn_path, in file order, stripped of leading
    whitespace. Empty list if the file has none (e.g. a hang/timeout with no
    Voyager-reported error, or a crash format not covered above)."""
    text = prn_path.read_text(encoding="utf-8", errors="replace")
    return [m.group(0).strip() for m in _FATAL_LINE_RE.finditer(text)]


def latest_fatal_errors(scenario_folder: Path) -> tuple:
    """Convenience wrapper for execution.py: resolves the latest PRN in
    scenario_folder and extracts its fatal-error lines in one call. Returns
    (prn_path, errors) -- prn_path is None (and errors []) if there's no PRN
    file to check."""
    prn_path = find_latest_prn(scenario_folder)
    if prn_path is None:
        return None, []
    return prn_path, extract_fatal_errors(prn_path)
