"""Cube .block parse/render/write round-trip -- the module ported closest to
verbatim from WF-TDM-Runs, so its correctness matters most here."""
import pytest

from tdmcalib import controlcenter as cc
from tdmcalib.exceptions import ControlCenterError


def test_load_baseline_reads_all_assignments(baseline_path):
    baseline = cc.load_baseline(baseline_path.parent, "", baseline_path.name)
    assert baseline["ModelVersion"] == "'TestModel'"
    assert baseline["RunYear"] == "2023"
    assert baseline["CalibrationCode"] == "'C08'"
    assert baseline["AddNodeFields"] == "';'"  # semicolon-in-quotes not mistaken for a comment


def test_load_baseline_missing_file_raises(tmp_path):
    with pytest.raises(ControlCenterError):
        cc.load_baseline(tmp_path, "", "does-not-exist.block")


def test_validate_overrides_rejects_unknown_key(baseline_path):
    baseline = cc.load_baseline(baseline_path.parent, "", baseline_path.name)
    with pytest.raises(ControlCenterError, match="NotARealKey"):
        cc.validate_overrides(baseline, {"NotARealKey": 1}, "test")


def test_validate_overrides_accepts_known_keys(baseline_path):
    baseline = cc.load_baseline(baseline_path.parent, "", baseline_path.name)
    cc.validate_overrides(baseline, {"CalibrationCode": "C50", "RunYear": 2023}, "test")


def test_render_precedence_identity_fields_always_win():
    rendered = cc.render(
        overrides={"RunYear": 2023, "ScenarioName": "should-lose"},
        local_layer={"RunYear": 2024},
        identity_fields={"ScenarioName": "C50"},
    )
    assert rendered["RunYear"] == 2024  # local layer beats overrides
    assert rendered["ScenarioName"] == "C50"  # identity fields always win


def test_write_block_file_only_touches_overridden_lines(baseline_path, tmp_path):
    output_path = tmp_path / "_ControlCenter.block"
    cc.write_block_file(
        baseline_path,
        {"CalibrationCode": "C50", "RunYear": 2050},
        output_path,
    )
    text = output_path.read_text(encoding="utf-8")

    assert "CalibrationCode = 'C50'" in text
    assert "RunYear = 2050" in text

    # Untouched assignment, comment, and control-flow lines survive verbatim.
    assert "WFRC_SEFile = 'SE_2023.csv'" in text
    assert "; for validation runs, use -C01, -C02, etc." in text
    assert "if (Run_Documentation=1)" in text
    assert "AddNodeFields = ';'" in text

    # CRLF line endings (Cube/Windows convention). read_text() with default
    # universal-newline translation would hide this, so read raw bytes.
    assert b"\r\n" in output_path.read_bytes()


def test_write_block_file_appends_unknown_extra_keys(baseline_path, tmp_path):
    output_path = tmp_path / "_ControlCenter.block"
    cc.write_block_file(baseline_path, {"BrandNewKey": "hello"}, output_path)
    text = output_path.read_text(encoding="utf-8")
    assert "keys set by the orchestrator" in text
    assert "BrandNewKey = 'hello'" in text


def test_format_cube_value_rejects_embedded_quote():
    with pytest.raises(ControlCenterError):
        cc._format_cube_value("has a ' quote")
