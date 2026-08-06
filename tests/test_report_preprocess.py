"""report/preprocess/ -- per-run report data extraction (see the
"Extract report data-loading into a preprocessing step" plan). Runs against
the real runs/C33/outputs/ fixture already on disk (imported from an
archived calibration run earlier this session) rather than a synthetic
mock, since the point is to catch a genuine extraction/round-trip
regression, not just exercise the code path. Skipped if that fixture isn't
present (e.g. a fresh clone that hasn't imported C33 yet)."""

from pathlib import Path

import pandas as pd
import pytest

from report import _validation_scripts as vs
from report.preprocess import tripgen

REPO_ROOT = Path(__file__).resolve().parents[1]

try:
    C33_OUTPUTS_DIR = vs.resolve_latest_run_outputs(REPO_ROOT, "C33")
except FileNotFoundError:
    C33_OUTPUTS_DIR = None

pytestmark = pytest.mark.skipif(
    C33_OUTPUTS_DIR is None, reason="runs/C33/outputs/ fixture not present"
)


def test_load_modeled_tripgen_shape():
    df = tripgen.load_modeled_tripgen("C33", C33_OUTPUTS_DIR, REPO_ROOT)
    assert list(df.columns) == ["CO_FIPS", "Purpose", "Trips per Person", "Trips per Household"]
    assert len(df) > 0
    # one CO_FIPS-null "Region" row per purpose, alongside the real counties
    assert df["CO_FIPS"].isna().sum() == df["Purpose"].nunique()


def test_load_modeled_tripgen_values_are_finite_and_positive():
    df = tripgen.load_modeled_tripgen("C33", C33_OUTPUTS_DIR, REPO_ROOT)
    for col in ["Trips per Person", "Trips per Household"]:
        assert df[col].notna().all()
        assert (df[col] > 0).all()


def test_load_modeled_tripgen_survives_parquet_round_trip(tmp_path):
    df = tripgen.load_modeled_tripgen("C33", C33_OUTPUTS_DIR, REPO_ROOT)
    cache_path = tmp_path / "modeled_tripgen.parquet"
    df.to_parquet(cache_path, index=False)
    df_reloaded = pd.read_parquet(cache_path)
    pd.testing.assert_frame_equal(df.reset_index(drop=True), df_reloaded.reset_index(drop=True))
