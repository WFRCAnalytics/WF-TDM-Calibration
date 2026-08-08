import os
import time

from tdmcalib import prn_log

# Real crash text (see prn_log.py's module docstring for provenance).
FATAL_BLOCK = (
    r"F(004): Problems opening ..\..\..\2_ModelScripts\2_Tripgen\1_TripGen_vizTool.s (err=2)"
    "\n"
    "F(004): OS reports: The system cannot find the file specified.\n"
)

# Real non-fatal example already present in this repo's own PRN output
# (tdm/Scenarios/C51/TPPL0017.PRN) -- must not be mistaken for a fatal error.
MEMORY_LINE = "M(792): ARRAY NEIGHBORS requires 80 bytes.\n"


def test_find_latest_prn_none_when_empty(tmp_path):
    assert prn_log.find_latest_prn(tmp_path) is None


def test_find_latest_prn_picks_newest_by_mtime(tmp_path):
    older = tmp_path / "TPPL0001.PRN"
    newer = tmp_path / "TPPL0002.PRN"
    older.write_text("old", encoding="utf-8")
    newer.write_text("new", encoding="utf-8")
    time.sleep(0.01)
    os.utime(newer, None)
    assert prn_log.find_latest_prn(tmp_path) == newer


def test_find_latest_prn_ignores_nested_subfolders(tmp_path):
    (tmp_path / "Temp" / "4_ModeChoice").mkdir(parents=True)
    (tmp_path / "Temp" / "4_ModeChoice" / "TPPL0001.PRN").write_text("nested", encoding="utf-8")
    assert prn_log.find_latest_prn(tmp_path) is None


def test_extract_fatal_errors_finds_f_lines(tmp_path):
    prn = tmp_path / "TPPL0017.PRN"
    prn.write_text(FATAL_BLOCK, encoding="utf-8")
    errors = prn_log.extract_fatal_errors(prn)
    assert errors == [
        r"F(004): Problems opening ..\..\..\2_ModelScripts\2_Tripgen\1_TripGen_vizTool.s (err=2)",
        "F(004): OS reports: The system cannot find the file specified.",
    ]


def test_extract_fatal_errors_ignores_memory_lines(tmp_path):
    prn = tmp_path / "TPPL0017.PRN"
    prn.write_text(MEMORY_LINE, encoding="utf-8")
    assert prn_log.extract_fatal_errors(prn) == []


def test_extract_fatal_errors_ignores_inline_function_reference(tmp_path):
    """F(x) also appears as an ordinary PILOT function/field reference --
    only a line-start `F(NNN):` is a real Voyager message, so an expression
    using it mid-line must not be mistaken for a fatal error."""
    prn = tmp_path / "TPPL0017.PRN"
    prn.write_text("    RO.VALUE = F(2) + 1\n", encoding="utf-8")
    assert prn_log.extract_fatal_errors(prn) == []


def test_extract_fatal_errors_empty_file(tmp_path):
    prn = tmp_path / "TPPL0017.PRN"
    prn.write_text("", encoding="utf-8")
    assert prn_log.extract_fatal_errors(prn) == []


def test_latest_fatal_errors_no_prn_file(tmp_path):
    prn_path, errors = prn_log.latest_fatal_errors(tmp_path)
    assert prn_path is None
    assert errors == []


def test_latest_fatal_errors_reads_newest_prn(tmp_path):
    (tmp_path / "TPPL0001.PRN").write_text(MEMORY_LINE, encoding="utf-8")
    newest = tmp_path / "TPPL0002.PRN"
    newest.write_text(FATAL_BLOCK, encoding="utf-8")
    time.sleep(0.01)
    os.utime(newest, None)
    prn_path, errors = prn_log.latest_fatal_errors(tmp_path)
    assert prn_path == newest
    assert len(errors) == 2
