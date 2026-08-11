"""Driver script staging -- RESUME POINT rewriting and the
GeneralParameters.block override READ FILE insertion (see
general_parameters.py for why an extra READ FILE, not a rendered copy, is
how those overrides get applied)."""
import pytest

from tdmcalib import driver_script as ds
from tdmcalib.exceptions import DriverScriptError


def _calib_run(**overrides):
    return {
        "driver_script": "TestDriverScript.s",
        "start_at_label": "STEP0",
        **overrides,
    }


def _stage(repo_root, calib_run, run_folder):
    return ds.stage(
        repo_root / "calibration_runs",
        repo_root / "tdm",
        "Scenarios/_default",
        calib_run,
        run_folder,
    )


def test_stage_copies_verbatim_with_no_resume_or_general_parameter_overrides(repo_root, tmp_path):
    run_folder = tmp_path / "run"
    run_folder.mkdir()
    source_text = (repo_root / "tdm" / "Scenarios" / "_default" / "TestDriverScript.s").read_text()

    _stage(repo_root, _calib_run(), run_folder)

    dest_text = (run_folder / "TestDriverScript.s").read_text()
    assert dest_text == source_text
    assert "_GeneralParametersOverrides.block" not in dest_text


def test_stage_rewrites_resume_point_when_start_at_label_set(repo_root, tmp_path):
    run_folder = tmp_path / "run"
    run_folder.mkdir()

    _stage(repo_root, _calib_run(start_at_label="STEP0"), run_folder)
    text = (run_folder / "TestDriverScript.s").read_text()
    assert "GOTO STEP0" in text


def test_stage_inserts_general_parameters_override_read_after_the_real_one(repo_root, tmp_path):
    run_folder = tmp_path / "run"
    run_folder.mkdir()

    _stage(repo_root, _calib_run(general_parameter_overrides={"calibFac_LT_BE": 1.2}), run_folder)
    text = (run_folder / "TestDriverScript.s").read_text()

    real_idx = text.index("GeneralParameters.block")
    override_idx = text.index("_GeneralParametersOverrides.block")
    assert real_idx < override_idx  # inserted after, not before

    # Indentation matches the line it was inserted after.
    inserted_line = next(
        line for line in text.splitlines() if "_GeneralParametersOverrides.block" in line
    )
    real_line = next(line for line in text.splitlines() if "GeneralParameters.block'" in line)
    real_indent = real_line[: len(real_line) - len(real_line.lstrip())]
    assert inserted_line.startswith(real_indent)


def test_stage_omits_general_parameters_override_read_when_not_declared(repo_root, tmp_path):
    run_folder = tmp_path / "run"
    run_folder.mkdir()

    _stage(repo_root, _calib_run(general_parameter_overrides={}), run_folder)
    text = (run_folder / "TestDriverScript.s").read_text()
    assert "_GeneralParametersOverrides.block" not in text


def test_stage_raises_when_general_parameter_overrides_set_but_no_read_file_marker(
    repo_root, tmp_path
):
    script_path = repo_root / "tdm" / "Scenarios" / "_default" / "NoGeneralParams.s"
    script_path.write_text(":BEGINMODEL\n    READ FILE = '_ControlCenter.block'\n")
    run_folder = tmp_path / "run"
    run_folder.mkdir()

    calib_run = _calib_run(
        driver_script="NoGeneralParams.s",
        general_parameter_overrides={"calibFac_LT_BE": 1.2},
    )
    with pytest.raises(DriverScriptError, match="GeneralParameters.block"):
        _stage(repo_root, calib_run, run_folder)


def test_stage_deletes_stale_s_files_before_copying(repo_root, tmp_path):
    run_folder = tmp_path / "run"
    run_folder.mkdir()
    (run_folder / "stale_from_earlier_attempt.s").write_text("old content")

    _stage(repo_root, _calib_run(), run_folder)

    remaining = sorted(p.name for p in run_folder.glob("*.s"))
    assert remaining == ["TestDriverScript.s"]
