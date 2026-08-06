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
one -- the text up to and including the last "TOTAL MODEL RUN TIME" entry --
describes this run.

Every Hail Mary driver variant (plain, resumable, 1-subfolder, ...) declares
only one :ONERROR/:ENDMODEL pair each, but none of them call Exit from
:ONERROR -- so a caught error logs its crash+total block and execution
simply falls through to whatever comes next in the script, rather than
stopping. If that next thing is another real step, :ONERROR can fire again
later for a different step, appending another crash+total block, and so on,
all within one single process run. So "TOTAL MODEL RUN TIME" alone is not
reliably a once-per-run final marker for ANY Hail Mary variant -- a crash+
total block can describe a superseded checkpoint that the run recovered
from and kept going past.

Newer TDM pins add an unambiguous fix for this: _TimeStamp_ModelSuccess.block
(only ever reached via the single :ENDMODEL, never :ONERROR) now writes a
trailing "MODEL RUN SUCCESSFUL" line that the crash block does not. Its mere
presence at the true tail of the file is conclusive proof of a real finish,
regardless of how many crash+retry checkpoints came before it, so it's
checked first and preferred whenever present. Calibration runs pinned to an
older TDM commit that predates this line (see calibration_runs/C33.yaml's
tdm_ref: "unknown-historical") fall back to the older heuristic: the last
"TOTAL MODEL RUN TIME" entry only counts as this run's outcome if nothing
else was logged after it; otherwise the real outcome for this attempt
hasn't been written yet, same as if Cube hadn't written anything at all.

Ported from WF-TDM-Runs' src/tdmruns/model_log.py (extended for the
checkpoint/success-marker handling above) -- this parses a TDM-side log
format, unrelated to the run_set/scenario-vs-calibration-run data model."""

import re
from pathlib import Path

_SUCCESS_MARKER = "MODEL RUN SUCCESSFUL"
_TOTAL_RE = re.compile(r"TOTAL MODEL RUN TIME")
_BEG_TIME_RE = re.compile(r"Beg Time:\s*(.+)")
_END_TIME_RE = re.compile(r"End Time:\s*(.+)")
_RUN_TIME_RE = re.compile(r"Run Time:\s*(.+)")

# _TimeStamp_ModelCrashed.block writes "-- Model Crashed --" and its crashed
# step directly ahead of "TOTAL MODEL RUN TIME" in the same PRINT statement,
# with nothing but that fixed template text in between -- so anchoring the
# crash marker to end exactly where a given TOTAL MODEL RUN TIME occurrence
# starts ties it to *that* occurrence specifically, unlike a fixed-size
# look-back, which can cross into an earlier, unrelated checkpoint's crash
# marker once enough step activity separates the two.
_CRASH_THEN_TOTAL_RE = re.compile(
    r"-- Model Crashed --\s*\nThe model crashed in:\s*(.+?)\s*\n\s*\nTOTAL MODEL RUN TIME"
)


def _times_from(text: str, total_pos: int) -> dict:
    tail = text[total_pos:total_pos + 400]
    beg = _BEG_TIME_RE.search(tail)
    end = _END_TIME_RE.search(tail)
    run = _RUN_TIME_RE.search(tail)
    return {
        "started_at": beg.group(1).strip() if beg else None,
        "finished_at": end.group(1).strip() if end else None,
        "run_time": run.group(1).strip() if run else None,
    }


def read_model_log(scenario_folder: Path) -> dict | None:
    """Returns the outcome of the most recent attempt recorded in
    <scenario_folder>\\_Log\\_RunTime.txt, or None if the file doesn't exist,
    has no recognizable completion entry yet (e.g. Cube crashed or was
    killed before writing anything), or its last entry has been superseded
    by further step activity logged after it (a checkpoint that was caught,
    retried, and kept going) -- callers should fall back to the process exit
    code in all of these cases.

    Returned dict: {"outcome": "success" | "crashed", "crashed_step": str
    or None, "started_at": str or None, "finished_at": str or None,
    "run_time": str or None}. Time fields are the model's own raw
    'yyyy-mm-dd,  hh:nn:ss' / 'hhh:nn:ss' strings, not reformatted."""
    log_path = scenario_folder / "_Log" / "_RunTime.txt"
    if not log_path.is_file():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")

    success_pos = text.rfind(_SUCCESS_MARKER)
    if success_pos != -1 and not text[success_pos + len(_SUCCESS_MARKER):].strip():
        total_pos = text.rfind("TOTAL MODEL RUN TIME", 0, success_pos)
        return {
            "outcome": "success",
            "crashed_step": None,
            **_times_from(text, total_pos if total_pos != -1 else success_pos),
        }

    totals = [m.start() for m in _TOTAL_RE.finditer(text)]
    if not totals:
        return None
    last_total = totals[-1]

    tail = text[last_total:last_total + 400]
    run = _RUN_TIME_RE.search(tail)
    block_end = last_total + (run.end() if run else len(tail))
    if text[block_end:].strip():
        return None

    crashed = False
    crashed_step = None
    for m in _CRASH_THEN_TOTAL_RE.finditer(text):
        if m.end() == last_total + len("TOTAL MODEL RUN TIME"):
            crashed = True
            crashed_step = m.group(1).strip()
            break

    return {
        "outcome": "crashed" if crashed else "success",
        "crashed_step": crashed_step,
        **_times_from(text, last_total),
    }
