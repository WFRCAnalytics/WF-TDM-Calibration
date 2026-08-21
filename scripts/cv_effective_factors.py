"""Effective LT/MD/HV commercial-vehicle calibration factors, by vehicle
type and vocation, for a calibration run.

tdm/2_ModelScripts/2_TripGen/2_TripGen_CV.s multiplies each zone's raw
trip-rate-model CV production by a "CoAdjFac" -- a county x vehicle-type
(x vocation, for MD/HV) factor built from three layers: a regional default
(<TYPE>_<VOC>_AdjFac), a county multiplier (<CO>_<TYPE>_<VOC>_AdjFac), and
this calibration run's own calibFac_<TYPE>_<CO> knob (LT has no vocation
split -- one calibFac_LT_<CO> per county, applied uniformly across all six
of its vocations). The multiply happens in place, so the pre-factor value
is never written to any output file -- there is no "before" to read back.
It is a simple scalar per (zone -> county, type, vocation) though, so it is
exactly invertible: unfactored = factored / CoAdjFac.

This script reconstructs that CoAdjFac for a given run (baseline
GeneralParameters.block values layered with the run's own
_GeneralParametersOverrides.block, same last-assignment-wins semantics Cube
Voyager itself uses), applies it to the run's pa_cv.csv productions to
recover the unfactored values, and reports the "effective" factor --
factored / unfactored production, summed over zones -- by vehicle type and
vocation, both region-wide and per county. Region-wide numbers are a
production-weighted average of the underlying county factors, so they can
differ from a simple average across counties.

pa_cv.csv is only ever the current attempt's raw output in tdm/'s own
working tree (tdm/Scenarios/{calib_run_id}/2_TripGen/pa_cv.csv) -- it is not
part of this repo's curated runs/ outputs, so this script reads it there
directly (read-only; nothing under tdm/ is written).
"""

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from tdmcalib import controlcenter as cc  # noqa: E402
from tdmcalib import general_parameters as gp  # noqa: E402
from tdmcalib.config import load_framework_config  # noqa: E402

# Relative to tdm/ -- not exposed in config/framework.yaml (that only tracks
# paths tdmcalib itself writes to), so hardcoded here same as the model
# scripts' own relative references.
TAZ_DBF_PATH = "1_Inputs/1_TAZ/WFv1000_TAZ.dbf"

# CO_FIPS -> the prefix 2_TripGen_CV.s uses for that county's parameter keys.
# The mapping itself (BeCoFips=3, etc.) is read from GeneralParameters.block
# below, not hardcoded, since it's config data the TDM owns.
COUNTY_PREFIXES = ["BE", "DA", "SL", "UT", "WE"]
COUNTY_FIPS_KEY = {"BE": "BeCoFips", "DA": "DaCoFips", "SL": "SlCoFips", "UT": "UtCoFips", "WE": "WeCoFips"}

# Vocation spelling as it appears in GeneralParameters.block's *_AdjFac keys
# vs. pa_cv.csv's IIP_<TYPE>_<VOC> columns (all-caps) -- both map to the
# same canonical label used for reporting.
VOCATIONS = ["D2D", "HnS", "Lcl", "Reg", "LHl", "Unk"]


def latest_run_with_tripgen(tdm_path: Path) -> str:
    scenarios_dir = tdm_path / "Scenarios"
    candidates = [
        d.name
        for d in scenarios_dir.iterdir()
        if d.is_dir() and (d / "2_TripGen" / "pa_cv.csv").is_file()
    ]
    if not candidates:
        raise SystemExit(f"No calibration run under {scenarios_dir} has a 2_TripGen/pa_cv.csv yet.")
    return sorted(candidates)[-1]


def load_general_params(tdm_path: Path, general_parameters_path: str, scenario_dir: Path) -> dict:
    baseline = gp.load_baseline(tdm_path, general_parameters_path)
    override_path = scenario_dir / gp.OVERRIDE_FILENAME
    overrides = {}
    if override_path.is_file():
        overrides = cc.load_baseline(override_path.parent, "", override_path.name)
    return {**baseline, **overrides}


def coadjfac(params: dict, prefix: str, veh: str, voc: str) -> float:
    """Replicates 2_TripGen_CV.s's per-(county, type, vocation) CoAdjFac
    computation exactly for a single combination -- LT ignores voc (one
    undifferentiated calibFac_LT_<CO> applies to all six of its vocations)."""
    if veh == "LT":
        return float(params[f"calibFac_LT_{prefix}"])
    regional = float(params[f"{veh}_{voc}_AdjFac"])
    county = float(params[f"{prefix}_{veh}_{voc}_AdjFac"])
    calib = float(params[f"calibFac_{veh}_{prefix}"])
    return regional * county * calib


def build_coadjfac_table(params: dict) -> pd.DataFrame:
    """Tabulates coadjfac() over every (county_prefix, vehicle_type,
    vocation) combination."""
    rows = [
        {"county": prefix, "vehicle_type": veh, "vocation": voc, "coadjfac": coadjfac(params, prefix, veh, voc)}
        for prefix in COUNTY_PREFIXES
        for veh in ("LT", "MD", "HV")
        for voc in VOCATIONS
    ]
    return pd.DataFrame(rows)


def load_zone_county(tdm_path: Path) -> pd.DataFrame:
    gdf = gpd.read_file(tdm_path / TAZ_DBF_PATH)
    zones = gdf[["TAZID", "CO_FIPS"]].copy()
    zones["TAZID"] = zones["TAZID"].astype(int)
    zones["CO_FIPS"] = zones["CO_FIPS"].astype(int)
    return zones


def load_pa_cv_long(scenario_dir: Path, zones: pd.DataFrame, county_fips: dict) -> pd.DataFrame:
    pa_cv = pd.read_csv(scenario_dir / "2_TripGen" / "pa_cv.csv")
    pa_cv = pa_cv.rename(columns={"TAZID": "TAZID"})
    pa_cv["TAZID"] = pa_cv["TAZID"].astype(int)

    fips_to_prefix = {fips: prefix for prefix, fips in county_fips.items()}

    records = []
    for veh in ("LT", "MD", "HV"):
        for voc in VOCATIONS:
            col = f"IIP_{veh}_{voc}".upper()
            if col not in pa_cv.columns:
                raise SystemExit(f"Expected column {col} not found in pa_cv.csv -- has the TDM's CVM output layout changed?")
            records.append(
                pa_cv[["TAZID", col]].rename(columns={col: "factored"}).assign(vehicle_type=veh, vocation=voc)
            )
    long_df = pd.concat(records, ignore_index=True)
    long_df = long_df.merge(zones, on="TAZID", how="left")
    long_df["county"] = long_df["CO_FIPS"].map(fips_to_prefix)

    unmapped = long_df["county"].isna().sum()
    if unmapped:
        print(f"Warning: {unmapped} zone-rows fall outside the 5 WFRC/MAG counties tracked by "
              "GeneralParameters.block's CoAdjFac logic and are excluded.", file=sys.stderr)
    return long_df.dropna(subset=["county"])


def compute_effective_factors(long_df: pd.DataFrame, coadjfac_table: pd.DataFrame) -> pd.DataFrame:
    merged = long_df.merge(coadjfac_table, on=["county", "vehicle_type", "vocation"], how="left")
    merged["unfactored"] = merged["factored"] / merged["coadjfac"]

    def summarize(group_cols):
        g = merged.groupby(group_cols)[["factored", "unfactored"]].sum().reset_index()
        g["effective_factor"] = g["factored"] / g["unfactored"]
        return g

    by_county = summarize(["county", "vehicle_type", "vocation"])
    by_county.insert(0, "scope", "county")

    regional = summarize(["vehicle_type", "vocation"])
    regional.insert(0, "county", "All")
    regional.insert(0, "scope", "region")

    by_type_only = summarize(["vehicle_type"])
    by_type_only.insert(0, "vocation", "All")
    by_type_only.insert(0, "county", "All")
    by_type_only.insert(0, "scope", "region")

    result = pd.concat([regional, by_type_only, by_county], ignore_index=True)
    return result[["scope", "county", "vehicle_type", "vocation", "unfactored", "factored", "effective_factor"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", help="Calibration run id (e.g. C67). Defaults to the most recent run under tdm/Scenarios/ with a 2_TripGen/pa_cv.csv.")
    parser.add_argument("--out", type=Path, help="Optional path to also write the full result table as CSV.")
    args = parser.parse_args()

    framework = load_framework_config(REPO_ROOT)
    tdm_path = REPO_ROOT / "tdm"

    run_id = args.run or latest_run_with_tripgen(tdm_path)
    scenario_dir = tdm_path / "Scenarios" / run_id
    if not (scenario_dir / "2_TripGen" / "pa_cv.csv").is_file():
        raise SystemExit(f"{scenario_dir / '2_TripGen' / 'pa_cv.csv'} not found -- has run {run_id} reached trip generation yet?")

    params = load_general_params(tdm_path, framework["general_parameters_path"], scenario_dir)
    county_fips = {prefix: int(params[key]) for prefix, key in COUNTY_FIPS_KEY.items()}

    coadjfac_table = build_coadjfac_table(params)
    zones = load_zone_county(tdm_path)
    long_df = load_pa_cv_long(scenario_dir, zones, county_fips)
    result = compute_effective_factors(long_df, coadjfac_table)

    print(f"Effective CV calibration factors -- run {run_id}\n")
    region_view = result[result["scope"] == "region"].drop(columns=["scope", "county"])
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(region_view.to_string(index=False))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(args.out, index=False)
        print(f"\nFull region + per-county table written to {args.out}")


if __name__ == "__main__":
    main()
