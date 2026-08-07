"""Loading, schema validation, and resolution of framework/calibration-run
config. This is the only place that knows how the two config layers (local
machine, calibration run) combine.

Unlike tdmruns (the sibling WF-TDM-Runs framework this was ported from),
there is no run_set/scenario nesting here -- one calibration run (e.g. C50)
is the whole unit, so the two-layer override merge collapses to a single
`overrides` dict per calibration run."""

import json
from pathlib import Path

import jsonschema
import yaml

from tdmcalib.exceptions import ConfigValidationError

SCHEMA_DIR_NAME = "schemas"


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise ConfigValidationError(f"Config file not found: {path}")
    with open(path, encoding="utf-8-sig") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ConfigValidationError(f"{path} must contain a YAML mapping at the top level.")
    return data


def _load_schema(repo_root: Path, name: str) -> dict:
    schema_path = repo_root / "config" / SCHEMA_DIR_NAME / name
    with open(schema_path) as f:
        return json.load(f)


def _validate(data: dict, schema: dict, context: str):
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        lines = [f"{context} failed schema validation:"]
        for e in errors:
            loc = "/".join(str(p) for p in e.path) or "(root)"
            lines.append(f"  - {loc}: {e.message}")
        raise ConfigValidationError("\n".join(lines))


def load_framework_config(repo_root: Path) -> dict:
    """Loads config/framework.yaml, then layers config/local.yaml on top if
    present (it is gitignored and machine-specific, so it may not exist)."""
    framework = load_yaml(repo_root / "config" / "framework.yaml")
    local_path = repo_root / "config" / "local.yaml"
    local = load_yaml(local_path) if local_path.is_file() else {}
    framework["_local"] = local
    return framework


def load_calibration_run(repo_root: Path, calib_run_id: str) -> dict:
    from tdmcalib.paths import calibration_run_file

    path = calibration_run_file(repo_root, calib_run_id)
    if not path.is_file():
        raise ConfigValidationError(f"No such calibration run '{calib_run_id}' (expected {path}).")
    data = load_yaml(path)
    schema = _load_schema(repo_root, "calibration_run.schema.json")
    _validate(data, schema, f"calibration run '{calib_run_id}'")
    if data["calib_run_id"] != calib_run_id:
        raise ConfigValidationError(
            f"{path} declares calib_run_id '{data['calib_run_id']}' but is named {calib_run_id}.yaml."
        )
    return data


def list_calibration_run_ids(repo_root: Path) -> list:
    from tdmcalib.paths import calibration_runs_dir

    d = calibration_runs_dir(repo_root)
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def resolved_driver_script(calib_run: dict) -> str:
    """Path to the calibration run's declared _HailMary.s driver script.
    driver_script is required by calibration_run.schema.json -- there is no
    framework-default fallback, so this is never None for a validated
    calibration run."""
    return calib_run["driver_script"]


def resolved_output_spec(framework: dict, calib_run: dict) -> dict:
    """Resolve a calibration run's effective output-curation spec.

    include/max_file_size_mb both fall back to config/framework.yaml's
    outputs section when a calibration run doesn't declare its own -- the
    default include list matches the raw TDM Scenario folder layout that a
    live `tdmcalib run` produces, so most calibration runs never need to
    declare their own. A run only needs its own `include` when its raw output
    lives at different paths (e.g. a manually-imported historical run whose
    archive used a different folder layout than the live TDM output).
    """
    spec = calib_run.get("outputs", {})
    max_mb = spec.get("max_file_size_mb", framework["outputs"]["max_file_size_mb"])
    if max_mb > framework["outputs"]["max_file_size_mb"]:
        raise ConfigValidationError(
            f"max_file_size_mb ({max_mb}) exceeds the framework-wide ceiling "
            f"({framework['outputs']['max_file_size_mb']}) set in config/framework.yaml."
        )
    include = spec.get("include", framework["outputs"].get("include", []))
    return {"include": include, "max_file_size_mb": max_mb}


def resolved_manual_run_folder(
    tdm_path: Path,
    framework: dict,
    calib_run_id: str,
    calib_run: dict,
) -> Path:
    """Resolves the raw folder a manually-run calibration run's outputs live
    in, relative to the TDM submodule root. Uses the run's declared
    manual_scenario_folder if present, otherwise falls back to the same
    scenario_folder_template convention used for CLI-driven runs."""
    rel = calib_run.get("manual_scenario_folder") or framework["scenario_folder_template"].format(
        calib_run_id=calib_run_id
    )
    return tdm_path / rel


def _resolve_input_files(calib_run_dir: Path, input_files: dict) -> dict:
    """Resolve relative paths in an input_files block to absolute paths
    anchored at calib_run_dir. Absolute paths are passed through unchanged."""
    resolved = {}
    for key, value in input_files.items():
        p = Path(value)
        resolved[key] = str((calib_run_dir / p).resolve() if not p.is_absolute() else p)
    return resolved


def resolved_overrides(calib_run: dict, calib_run_dir: Path) -> dict:
    """Control Center overrides for this calibration run, with input_files
    entries resolved to absolute paths and merged in as override keys (e.g.
    WFRC_SEFile pointing at an absolute CSV path)."""
    overrides = dict(calib_run.get("overrides", {}))
    input_files = calib_run.get("input_files", {})
    if input_files:
        overrides.update(_resolve_input_files(calib_run_dir, input_files))
    return overrides
