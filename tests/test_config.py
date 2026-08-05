"""Calibration-run config loading, schema validation, and resolution."""
import pytest
import yaml

from tdmcalib import config as cfg
from tdmcalib.exceptions import ConfigValidationError


def _write_calib_run(repo_root, calib_run_id, data=None):
    payload = {
        "calib_run_id": calib_run_id,
        "tdm_ref": "calib/C50-start",
        "baseline_control_center": "TestBaseline.block",
        **(data or {}),
    }
    path = repo_root / "calibration_runs" / f"{calib_run_id}.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(payload, f, sort_keys=False)
    return path


def test_load_calibration_run_roundtrip(repo_root):
    _write_calib_run(repo_root, "C50", {"overrides": {"CalibrationCode": "C50"}})
    data = cfg.load_calibration_run(repo_root, "C50")
    assert data["tdm_ref"] == "calib/C50-start"
    assert data["overrides"]["CalibrationCode"] == "C50"


def test_load_calibration_run_id_mismatch_raises(repo_root):
    # File named C50.yaml but declares a different calib_run_id inside.
    path = repo_root / "calibration_runs" / "C50.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(
            {
                "calib_run_id": "C51",
                "tdm_ref": "x",
                "baseline_control_center": "TestBaseline.block",
            },
            f,
        )
    with pytest.raises(ConfigValidationError, match="C51"):
        cfg.load_calibration_run(repo_root, "C50")


def test_load_calibration_run_missing_required_field_raises(repo_root):
    path = repo_root / "calibration_runs" / "C50.yaml"
    with open(path, "w") as f:
        yaml.safe_dump({"calib_run_id": "C50"}, f)  # missing tdm_ref, baseline_control_center
    with pytest.raises(ConfigValidationError):
        cfg.load_calibration_run(repo_root, "C50")


def test_load_calibration_run_rejects_unknown_top_level_key(repo_root):
    _write_calib_run(repo_root, "C50", {"totally_made_up_field": True})
    with pytest.raises(ConfigValidationError):
        cfg.load_calibration_run(repo_root, "C50")


def test_load_calibration_run_id_pattern_enforced(repo_root):
    # calib_run_id must match ^C[0-9]{2,3}$
    path = repo_root / "calibration_runs" / "fifty.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(
            {
                "calib_run_id": "fifty",
                "tdm_ref": "x",
                "baseline_control_center": "TestBaseline.block",
            },
            f,
        )
    with pytest.raises(ConfigValidationError):
        cfg.load_calibration_run(repo_root, "fifty")


def test_list_calibration_run_ids_sorted(repo_root):
    _write_calib_run(repo_root, "C51")
    _write_calib_run(repo_root, "C50")
    assert cfg.list_calibration_run_ids(repo_root) == ["C50", "C51"]


def test_resolved_output_spec_defaults_to_framework_ceiling(repo_root):
    framework = cfg.load_framework_config(repo_root)
    calib_run = {"outputs": {"include": []}}
    spec = cfg.resolved_output_spec(framework, calib_run)
    assert spec["max_file_size_mb"] == 25  # from the fixture's framework.yaml


def test_resolved_output_spec_rejects_ceiling_above_framework_max(repo_root):
    framework = cfg.load_framework_config(repo_root)
    calib_run = {"outputs": {"include": [], "max_file_size_mb": 999}}
    with pytest.raises(ConfigValidationError):
        cfg.resolved_output_spec(framework, calib_run)


def test_resolved_overrides_resolves_input_files_to_absolute_paths(repo_root):
    calib_run_dir = repo_root / "calibration_runs"
    (calib_run_dir / "inputs").mkdir()
    (calib_run_dir / "inputs" / "SE_2050.csv").write_text("a,b\n1,2\n")

    calib_run = {
        "overrides": {"RunYear": 2050},
        "input_files": {"WFRC_SEFile": "inputs/SE_2050.csv"},
    }
    resolved = cfg.resolved_overrides(calib_run, calib_run_dir)
    assert resolved["RunYear"] == 2050
    assert resolved["WFRC_SEFile"].endswith("SE_2050.csv")
    from pathlib import Path

    assert Path(resolved["WFRC_SEFile"]).is_absolute()
