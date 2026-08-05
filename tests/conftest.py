"""Shared fixtures. Each test gets its own throwaway repo layout under
tmp_path, so tests never touch the real tdm/ submodule or calibration_runs/.

Reduced scope vs. WF-TDM-Runs' own test suite (see repo README /
report/README.md): this ports controlcenter.py/config.py/outputs.py
coverage only, not a full git-backed execution.run() end-to-end test."""
import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# A real Cube Voyager block-format baseline (not YAML) -- this is the format
# tdmcalib.controlcenter actually parses. Deliberately includes a
# semicolon-in-quotes value, a comment on an overridden line, and a
# non-assignment control-flow line, to exercise write_block_file()'s
# preserve-everything-else behavior.
BASELINE_BLOCK_TEXT = """\
;****************************************************************************************
; Test baseline
;****************************************************************************************

;User identification
    UserName    = ''
    UserCompany = ''

    ModelVersion   = 'TestModel'  ; for validation runs, use -C01, -C02, etc.
    ScenarioName   = 'BY'
    RunYear        = 2023
    RunDescription = 'Base Year test scenario'

    ParentDir   = 'placeholder'
    ScenarioDir = 'placeholder'

    CalibrationCode   = 'C08'
    Run_Documentation = 1  ;1:run, 0:do not run

    WFRC_SEFile = 'SE_2023.csv'

    AddNodeFields = ';'

    HOT_Toll_Min = 25
    HOT_Toll_Max = 200

    if (Run_Documentation=1)
        DummyStep = 1
    endif
"""


@pytest.fixture
def repo_root(tmp_path):
    """A throwaway repo laid out like WF-TDM-Calibration: config/ + schemas
    (copied from the real project) + a fake tdm/Scenarios/_default/ baseline
    (no actual git submodule -- controlcenter/outputs tests don't need one)."""
    repo = tmp_path / "calib-repo"
    (repo / "config" / "schemas").mkdir(parents=True)
    (repo / "tdm" / "Scenarios" / "_default").mkdir(parents=True)
    (repo / "calibration_runs").mkdir(parents=True)

    shutil.copytree(
        REPO_ROOT / "config" / "schemas", repo / "config" / "schemas", dirs_exist_ok=True
    )

    (repo / "tdm" / "Scenarios" / "_default" / "TestBaseline.block").write_text(
        BASELINE_BLOCK_TEXT, encoding="utf-8"
    )

    framework_yaml = {
        "tdm_submodule_path": "tdm",
        "control_center_defaults_dir": "Scenarios/_default",
        "scenario_folder_template": "Scenarios/{calib_run_id}",
        "default_driver_script": "TestBaseline.block",  # unused by these tests
        "execution": {
            "entry_point": "bin/RunModel.bat",
            "args": ["{control_center_path}", "{scenario_folder}"],
            "timeout_seconds": 30,
        },
        "outputs": {"max_file_size_mb": 25},
        "run_metadata_schema_version": 1,
    }
    import yaml

    with open(repo / "config" / "framework.yaml", "w") as f:
        yaml.safe_dump(framework_yaml, f, sort_keys=False)

    return repo


@pytest.fixture
def baseline_path(repo_root):
    return repo_root / "tdm" / "Scenarios" / "_default" / "TestBaseline.block"
