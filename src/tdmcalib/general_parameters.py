"""GeneralParameters.block override rendering.

tdm/1_Inputs/0_GlobalData/GeneralParameters.block (config/framework.yaml's
general_parameters_path) is a single file shared by every calibration run's
working folder -- the driver script's own `READ FILE = '..\\..\\1_Inputs\\
0_GlobalData\\GeneralParameters.block'` line resolves to the same file under
tdm/ no matter which scenario is running. So unlike the Control Center (see
controlcenter.py), a calibration run can't override it by writing a per-run
*copy* of the whole file with substituted lines -- there's nothing to copy
from without touching tdm/ itself, which CLAUDE.md forbids, and the copy
would be shared/clobbered across runs anyway.

Instead: validate override keys against the real file (same typo-catching as
Control Center overrides, via controlcenter.validate_overrides), then write
only the overridden key/value pairs to a small per-run file
(OVERRIDE_FILENAME, in the run's scenario folder). driver_script.py inserts
one extra READ FILE line right after the real GeneralParameters.block READ
so Cube Voyager's own last-assignment-wins semantics apply the override --
the ~1200-line source file itself is never copied or modified.
"""

from pathlib import Path

from tdmcalib import controlcenter as cc

# Written into the run's scenario folder (a sibling of _ControlCenter.block),
# never into tdm/ -- see module docstring. Read via a bare filename, same as
# _ControlCenter.block's own READ FILE, since Cube resolves it relative to
# the scenario folder RunModel.bat pushes into before invoking Voyager.
OVERRIDE_FILENAME = "_GeneralParametersOverrides.block"


def load_baseline(tdm_path: Path, general_parameters_path: str) -> dict:
    """Loads tdm/'s real GeneralParameters.block (read-only) so override keys
    can be checked against what it actually defines -- reuses
    controlcenter.py's own parser, since it's just another Cube block file."""
    path = tdm_path / general_parameters_path
    return cc.load_baseline(path.parent, "", path.name)


def write_override_file(overrides: dict, output_path: Path):
    """Writes a standalone Cube block file containing only the overridden
    key/value pairs. Not a copy of GeneralParameters.block (see module
    docstring), so there's no template to preserve comments/structure from --
    every line here is orchestrator-generated."""
    lines = [
        ";--- General Parameter overrides for this calibration run",
        "; (see calibration_runs/*.yaml's general_parameter_overrides) ---",
        *cc.render_assignment_lines(overrides),
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
