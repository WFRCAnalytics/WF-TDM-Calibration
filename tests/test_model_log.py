from pathlib import Path

from tdmcalib import model_log

SUCCESS_BLOCK = """
TOTAL MODEL RUN TIME
    Beg Time:  2026-08-06,  08:00:35
    End Time:  2026-08-06,  09:43:31
    Run Time:  001:42:56

"""

CRASHED_BLOCK = """
=======================================================================
 -- Model Crashed --
The model crashed in:           ?         ?

TOTAL MODEL RUN TIME
    Beg Time:  2026-08-06,  08:00:35
    End Time:  2026-08-06,  09:43:31
    Run Time:  001:42:56

"""

# Newer TDM pins (calib/C50-start onward) -- _TimeStamp_ModelSuccess.block
# now writes this trailing line, only reachable via :ENDMODEL.
MARKER_SUCCESS_BLOCK = """
TOTAL MODEL RUN TIME
    Beg Time:  2026-08-06,  08:00:35
    End Time:  2026-08-06,  09:43:31
    Run Time:  001:42:56

MODEL RUN SUCCESSFUL"""


def _write_log(tmp_path: Path, text: str) -> Path:
    scenario_folder = tmp_path / "C50"
    (scenario_folder / "_Log").mkdir(parents=True)
    (scenario_folder / "_Log" / "_RunTime.txt").write_text(text, encoding="utf-8")
    return scenario_folder


def test_missing_log_returns_none(tmp_path):
    assert model_log.read_model_log(tmp_path / "C50") is None


def test_no_total_marker_returns_none(tmp_path):
    scenario_folder = _write_log(tmp_path, "some step ran\nbut never finished\n")
    assert model_log.read_model_log(scenario_folder) is None


def test_clean_success(tmp_path):
    scenario_folder = _write_log(tmp_path, SUCCESS_BLOCK)
    result = model_log.read_model_log(scenario_folder)
    assert result["outcome"] == "success"
    assert result["crashed_step"] is None


def test_clean_crash(tmp_path):
    scenario_folder = _write_log(tmp_path, CRASHED_BLOCK)
    result = model_log.read_model_log(scenario_folder)
    assert result["outcome"] == "crashed"
    assert result["crashed_step"] == "?         ?"


def test_crash_checkpoint_superseded_by_further_activity_is_unresolved(tmp_path):
    """Resumable Hail Mary case: a step crashes, is caught and retried, and
    the model keeps going -- more step activity gets logged after the
    crash+total checkpoint, with no final marker yet. This should NOT be
    read as this run's outcome (regression test for the real C50 log that
    triggered this fix)."""
    text = CRASHED_BLOCK + "\n    Boardings Report                   2026-08-06,  09:52:21,  000:01:10\n"
    scenario_folder = _write_log(tmp_path, text)
    assert model_log.read_model_log(scenario_folder) is None


def test_success_after_earlier_superseded_crash_checkpoint(tmp_path):
    """A crash+retry checkpoint earlier in the file must not leak into the
    outcome once a later, final checkpoint is reached."""
    text = (
        CRASHED_BLOCK
        + "\n    Boardings Report                   2026-08-06,  09:52:21,  000:01:10\n"
        + SUCCESS_BLOCK
    )
    scenario_folder = _write_log(tmp_path, text)
    result = model_log.read_model_log(scenario_folder)
    assert result["outcome"] == "success"


def test_only_most_recent_full_attempt_considered(tmp_path):
    """Two full, resolved attempts appended to the same file (e.g. two
    separate tdmcalib retries) -- only the last one's outcome counts."""
    text = CRASHED_BLOCK + SUCCESS_BLOCK
    scenario_folder = _write_log(tmp_path, text)
    result = model_log.read_model_log(scenario_folder)
    assert result["outcome"] == "success"


def test_marker_success(tmp_path):
    """Newer TDM pins: the trailing MODEL RUN SUCCESSFUL line alone is
    conclusive, preferred over the older totals-based heuristic."""
    scenario_folder = _write_log(tmp_path, MARKER_SUCCESS_BLOCK)
    result = model_log.read_model_log(scenario_folder)
    assert result["outcome"] == "success"
    assert result["crashed_step"] is None
    assert result["run_time"] == "001:42:56"


def test_marker_success_wins_over_earlier_crash_retries(tmp_path):
    """Any number of caught-and-retried crash checkpoints before the final
    MODEL RUN SUCCESSFUL line don't matter -- the marker alone decides."""
    text = (
        CRASHED_BLOCK
        + "\n    Boardings Report                   2026-08-06,  09:52:21,  000:01:10\n"
        + CRASHED_BLOCK
        + "\n    Highway Assignment                 2026-08-06,  10:26:00,  000:02:24\n"
        + MARKER_SUCCESS_BLOCK
    )
    scenario_folder = _write_log(tmp_path, text)
    result = model_log.read_model_log(scenario_folder)
    assert result["outcome"] == "success"


def test_marker_not_at_true_tail_falls_back(tmp_path):
    """A MODEL RUN SUCCESSFUL line followed by more content (shouldn't
    happen for a real run, since it's the last thing :ENDMODEL writes) isn't
    trusted -- falls back to the older heuristic instead of assuming it's
    still the final word."""
    text = MARKER_SUCCESS_BLOCK + "\nmore output after the marker\n"
    scenario_folder = _write_log(tmp_path, text)
    assert model_log.read_model_log(scenario_folder) is None
