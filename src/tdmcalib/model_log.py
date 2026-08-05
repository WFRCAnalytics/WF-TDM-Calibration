"""Parses the TDM's own `_Log\\_RunTime.txt` (written by the model scripts
themselves, via `_TimeStamp_ModelSuccess.block` / `_TimeStamp_ModelCrashed.block`
at :ENDMODEL / :ONERROR in the Hail Mary driver script) as a second, more
trustworthy signal for whether a model run actually succeeded.

Voyager's own process exit code, captured by RunModel.bat, is not reliable on
its own -- WF-TDM-Runs recorded real runs completing cleanly (a "TOTAL MODEL
RUN TIME" entry, no crash marker) while Voyager still returned a non-zero
exit code. The driver script also never calls Exit after :ONERROR, so the
reverse (a crash that still exits 0) is plausible too. Reading the model's
own self-report is strictly more accurate than trusting the wrapping batch
process's ERRORLEVEL.

The log file is opened with APPEND=T and reused across every retry of a
given calibration run (the raw working folder is not unique per attempt), so
it can accumulate several full run reports over time. Only the most recent
one -- the text from the previous "TOTAL MODEL RUN TIME" entry (or the start
of the file) up to and including the last one -- describes this run.

Ported unchanged from WF-TDM-Runs' src/tdmruns/model_log.py -- this parses a
TDM-side log format, unrelated to the run_set/scenario-vs-calibration-run
data model."""

import re
from pathlib import Path

_TOTAL_RE = re.compile(r"TOTAL MODEL RUN TIME")
_CRASHED_RE = re.compile(r"-- Model Crashed --")
_CRASHED_STEP_RE = re.compile(r"The model crashed in:\s*(.+)")
_BEG_TIME_RE = re.compile(r"Beg Time:\s*(.+)")
_END_TIME_RE = re.compile(r"End Time:\s*(.+)")
_RUN_TIME_RE = re.compile(r"Run Time:\s*(.+)")


def read_model_log(scenario_folder: Path) -> dict | None:
    """Returns the outcome of the most recent attempt recorded in
    <scenario_folder>\\_Log\\_RunTime.txt, or None if the file doesn't exist
    or has no recognizable "TOTAL MODEL RUN TIME" entry yet (e.g. Cube
    crashed or was killed before writing anything) -- callers should fall
    back to the process exit code in that case.

    Returned dict: {"outcome": "success" | "crashed", "crashed_step": str
    or None, "started_at": str or None, "finished_at": str or None,
    "run_time": str or None}. Time fields are the model's own raw
    'yyyy-mm-dd,  hh:nn:ss' / 'hhh:nn:ss' strings, not reformatted."""
    log_path = scenario_folder / "_Log" / "_RunTime.txt"
    if not log_path.is_file():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")

    totals = [m.start() for m in _TOTAL_RE.finditer(text)]
    if not totals:
        return None
    last_total = totals[-1]
    prev_boundary = totals[-2] if len(totals) > 1 else 0

    this_attempt = text[prev_boundary:last_total]
    crashed = _CRASHED_RE.search(this_attempt) is not None
    crashed_step = None
    if crashed:
        m = _CRASHED_STEP_RE.search(this_attempt)
        crashed_step = m.group(1).strip() if m else None

    tail = text[last_total:last_total + 400]
    beg = _BEG_TIME_RE.search(tail)
    end = _END_TIME_RE.search(tail)
    run = _RUN_TIME_RE.search(tail)

    return {
        "outcome": "crashed" if crashed else "success",
        "crashed_step": crashed_step,
        "started_at": beg.group(1).strip() if beg else None,
        "finished_at": end.group(1).strip() if end else None,
        "run_time": run.group(1).strip() if run else None,
    }
