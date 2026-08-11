"""GeneralParameters.block override loading/writing -- see
src/tdmcalib/general_parameters.py for why this is a separate mechanism from
controlcenter.py's per-run rendered copy."""
import pytest

from tdmcalib import controlcenter as cc
from tdmcalib import general_parameters as gp
from tdmcalib.exceptions import ControlCenterError


def test_load_baseline_reads_real_general_parameters_keys(repo_root):
    baseline = gp.load_baseline(repo_root / "tdm", "1_Inputs/0_GlobalData/GeneralParameters.block")
    assert baseline["calibFac_LT_BE"] == "1.00"
    assert baseline["DA_FwyTruckCostFac"] == "1.00"


def test_load_baseline_missing_file_raises(repo_root):
    with pytest.raises(ControlCenterError):
        gp.load_baseline(repo_root / "tdm", "1_Inputs/0_GlobalData/does-not-exist.block")


def test_validate_overrides_rejects_key_not_in_general_parameters(repo_root):
    baseline = gp.load_baseline(repo_root / "tdm", "1_Inputs/0_GlobalData/GeneralParameters.block")
    with pytest.raises(ControlCenterError, match="NotARealKey"):
        cc.validate_overrides(baseline, {"NotARealKey": 1}, "test")


def test_validate_overrides_accepts_known_general_parameters_keys(repo_root):
    baseline = gp.load_baseline(repo_root / "tdm", "1_Inputs/0_GlobalData/GeneralParameters.block")
    cc.validate_overrides(baseline, {"calibFac_LT_BE": 1.20, "DA_FwyTruckCostFac": 1.30}, "test")


def test_write_override_file_contains_only_overridden_keys(tmp_path):
    output_path = tmp_path / gp.OVERRIDE_FILENAME
    gp.write_override_file({"calibFac_LT_BE": 1.20, "DA_FwyTruckCostFac": 1.30}, output_path)
    text = output_path.read_text(encoding="utf-8")

    assert "calibFac_LT_BE = 1.2" in text
    assert "DA_FwyTruckCostFac = 1.3" in text
    assert "General Parameter overrides" in text

    # Not a copy of the real file -- unrelated baseline keys never appear.
    assert "calibFac_MD_BE" not in text

    # CRLF line endings (Cube/Windows convention), same as Control Center.
    assert b"\r\n" in output_path.read_bytes()


def test_write_override_file_creates_parent_dirs(tmp_path):
    output_path = tmp_path / "nested" / "folder" / gp.OVERRIDE_FILENAME
    gp.write_override_file({"calibFac_LT_BE": 1.20}, output_path)
    assert output_path.is_file()
