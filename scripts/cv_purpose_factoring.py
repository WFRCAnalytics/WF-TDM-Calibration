"""Commercial-vehicle trip generation & VMT, decomposed into "base model"
vs. "calibration adjustment", by vehicle type and purpose (II vocation, or
IX/XI/XX), for a calibration run.

Produces the data behind report/cvm-update.qmd. Two calibration mechanisms
feed into this, and they're handled separately:

- II (internal-internal) trips: tdm/2_ModelScripts/2_TripGen/2_TripGen_CV.s
  multiplies each zone's raw trip-rate-model production by a "CoAdjFac" --
  county x vehicle-type (x vocation, for MD/HV; LT has one county-wide
  factor only) -- see cv_effective_factors.py's module docstring for the
  full mechanism. Exactly invertible per zone: unfactored = factored /
  CoAdjFac.
- IX/XI/XX (any external-station-involved trip): NOT part of the CVM rate
  model at all -- these come from a linear extrapolation of UDOT volume
  trend counts (trip generation) and the Utah Statewide TDM (distribution
  pattern); see tdm/2_ModelScripts/0_InputProcessing/d_TripTable/
  2_ExternalTripTable.s. The only calibration applied is a per-station,
  vocation-blind calibFac_Ext_<MD|HV>_<station> multiplier scaling that
  station's whole truck volume before it's split into IX/XI/XX shares --
  also exactly invertible, just at the station level instead of the zone
  level, and with no vocation dimension.

VMT unfactoring uses a single-sided approximation (divide by the
*production*-zone's factor for II and XI, the *destination*-zone's factor
for IX, one side only for XX) -- see report/cvm-update.qmd's methodology
note for why this is an approximation, not an exact re-run of distribution.

Requires Voyager (to convert the raw PA_AllPurp_GRAVITY.mtx trip table --
its II/IX/XI/XX CV tabs aren't part of this repo's curated runs/ outputs,
see config/framework.yaml's outputs.include). Not part of the report's
normal render path -- run manually and commit the resulting CSV under
report/data/cvm-update/, same as any other static report input.
"""

import argparse
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import openmatrix as omx
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tdmcalib import matrix_utils as mu  # noqa: E402
from tdmcalib.config import load_framework_config  # noqa: E402

import cv_effective_factors as cef  # noqa: E402

VOCATIONS = cef.VOCATIONS
ZONES = 3629


def ext_fac(params: dict, veh: str, taz: int) -> float:
    key = f"calibFac_Ext_{veh}_{taz}"
    return float(params[key]) if key in params else 1.0


def compute_ii_trip_gen(pa_cv: pd.DataFrame, zones: pd.DataFrame, county_fips: dict, params: dict) -> pd.DataFrame:
    fips_to_prefix = {f: p for p, f in county_fips.items()}
    zone_prefix = dict(zip(zones["TAZID"], zones["CO_FIPS"].map(fips_to_prefix)))

    rows = []
    for veh in ("LT", "MD", "HV"):
        for voc in VOCATIONS:
            col = f"IIP_{veh}_{voc}".upper()
            factored = unfactored = 0.0
            for taz, val in zip(pa_cv["TAZID"], pa_cv[col]):
                pfx = zone_prefix.get(taz)
                if not pfx or val == 0:
                    continue
                cf = cef.coadjfac(params, pfx, veh, voc)
                factored += val
                unfactored += val / cf
            rows.append(dict(vehicle_type=veh, component=voc, metric="trips", factored=factored, unfactored=unfactored))
    return pd.DataFrame(rows)


def compute_ext_trip_gen(ext: pd.DataFrame, params: dict) -> pd.DataFrame:
    rows = []
    for veh in ("MD", "HV"):
        totals = {"IX": [0.0, 0.0], "XI": [0.0, 0.0], "XX": [0.0, 0.0]}
        for _, row in ext.iterrows():
            taz = int(row["TAZID"])
            cf = ext_fac(params, veh, taz)
            a_ix, p_xi = row[f"A_IX_{veh}"], row[f"P_XI_{veh}"]
            p_xx, a_xx = row[f"P_XX_{veh}"], row[f"A_XX_{veh}"]
            totals["IX"][0] += a_ix
            totals["IX"][1] += a_ix / cf
            totals["XI"][0] += p_xi
            totals["XI"][1] += p_xi / cf
            totals["XX"][0] += (p_xx + a_xx) / 2
            totals["XX"][1] += (p_xx / cf + a_xx / cf) / 2
        for comp, (f, u) in totals.items():
            rows.append(dict(vehicle_type=veh, component=comp, metric="trips", factored=f, unfactored=u))
    for comp in ("IX", "XI", "XX"):
        rows.append(dict(vehicle_type="LT", component=comp, metric="trips", factored=0.0, unfactored=0.0))
    return pd.DataFrame(rows)


def compute_ii_vmt(pa_omx_path: Path, skims: dict, zones: pd.DataFrame, county_fips: dict, params: dict) -> pd.DataFrame:
    fips_to_prefix = {f: p for p, f in county_fips.items()}
    zone_prefix = [None] * (ZONES + 1)
    for taz, fips in zip(zones["TAZID"], zones["CO_FIPS"]):
        if 1 <= taz <= ZONES:
            zone_prefix[taz] = fips_to_prefix.get(fips)

    pa = omx.open_file(str(pa_omx_path), "r")
    rows = []
    for veh in ("LT", "MD", "HV"):
        dist = skims[veh]
        for voc in VOCATIONS:
            mat = np.array(pa[f"II_{veh}_{voc}"])
            cvec = np.ones(ZONES)
            for taz in range(1, ZONES + 1):
                pfx = zone_prefix[taz]
                if pfx:
                    cvec[taz - 1] = cef.coadjfac(params, pfx, veh, voc)
            unfactored_mat = mat / cvec[:, None]  # production-zone-only unfactoring
            factored_vmt = float((mat * dist).sum())
            unfactored_vmt = float((unfactored_mat * dist).sum())
            rows.append(dict(vehicle_type=veh, component=voc, metric="vmt", factored=factored_vmt, unfactored=unfactored_vmt))
    pa.close()
    return pd.DataFrame(rows)


def compute_ext_vmt(pa_omx_path: Path, skims: dict, params: dict) -> pd.DataFrame:
    ext_vec = {veh: np.ones(ZONES) for veh in ("MD", "HV")}
    for veh in ("MD", "HV"):
        for taz in range(3601, 3630):
            ext_vec[veh][taz - 1] = ext_fac(params, veh, taz)

    pa = omx.open_file(str(pa_omx_path), "r")
    rows = []
    for veh in ("MD", "HV"):
        dist = skims[veh]
        cvec = ext_vec[veh]
        for comp, tab, axis in [("IX", f"IX_{veh}", "col"), ("XI", f"XI_{veh}", "row"), ("XX", f"XX_{veh}", "row")]:
            mat = np.array(pa[tab])
            unfac_mat = mat / cvec[None, :] if axis == "col" else mat / cvec[:, None]
            factored_vmt = float((mat * dist).sum())
            unfactored_vmt = float((unfac_mat * dist).sum())
            rows.append(dict(vehicle_type=veh, component=comp, metric="vmt", factored=factored_vmt, unfactored=unfactored_vmt))
    for comp in ("IX", "XI", "XX"):
        rows.append(dict(vehicle_type="LT", component=comp, metric="vmt", factored=0.0, unfactored=0.0))
    pa.close()
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", help="Calibration run id (e.g. C67). Defaults to the most recent run with a 2_TripGen/pa_cv.csv.")
    parser.add_argument("--out", type=Path, help="Defaults to report/data/cvm-update/purpose_factoring_<run>.csv -- one file per run, so report/cvm-update.qmd's calibration-run selector can pick between them.")
    args = parser.parse_args()

    framework = load_framework_config(REPO_ROOT)
    tdm_path = REPO_ROOT / "tdm"
    local_layer = framework.get("_local", {})
    voyager_exe = local_layer.get("Voyager_EXE")
    if not voyager_exe:
        import yaml
        local_yaml = REPO_ROOT / "config" / "local.yaml"
        if local_yaml.is_file():
            with open(local_yaml) as f:
                voyager_exe = (yaml.safe_load(f) or {}).get("Voyager_EXE")
    if not voyager_exe:
        raise SystemExit("Voyager_EXE not found in config/local.yaml -- needed to convert PA_AllPurp_GRAVITY.mtx.")

    run_id = args.run or cef.latest_run_with_tripgen(tdm_path)
    scenario_dir = tdm_path / "Scenarios" / run_id
    run_dir = REPO_ROOT / "runs" / run_id
    out_path = args.out or REPO_ROOT / "report" / "data" / "cvm-update" / f"purpose_factoring_{run_id}.csv"

    params = cef.load_general_params(tdm_path, framework["general_parameters_path"], scenario_dir)
    county_fips = {prefix: int(params[key]) for prefix, key in cef.COUNTY_FIPS_KEY.items()}
    zones = cef.load_zone_county(tdm_path)

    pa_cv = pd.read_csv(scenario_dir / "2_TripGen" / "pa_cv.csv")
    pa_cv["TAZID"] = pa_cv["TAZID"].astype(int)
    ext = gpd.read_file(scenario_dir / "0_InputProcessing" / "External_TripEnds_2023.dbf").drop(columns=["geometry"], errors="ignore")
    ext["TAZID"] = ext["TAZID"].astype(int)

    skims = {}
    for veh in ("LT", "MD", "HV"):
        f = omx.open_file(str(run_dir / f"skm_DY_Dist__{veh}.omx"), "r")
        skims[veh] = np.array(f[veh])
        f.close()

    with tempfile.TemporaryDirectory(prefix="cv_purpose_factoring_") as tmp:
        pa_mtx = scenario_dir / "3_Distribute" / "PA_AllPurp_GRAVITY.mtx"
        pa_omx = Path(tmp) / "PA_AllPurp_GRAVITY.omx"
        print(f"Converting {pa_mtx} via Voyager (this can take a few minutes)...")
        mu.convert_mtx_to_omx(pa_mtx, pa_omx, voyager_exe)

        tg = pd.concat([
            compute_ii_trip_gen(pa_cv, zones, county_fips, params),
            compute_ext_trip_gen(ext, params),
        ], ignore_index=True)
        vmt = pd.concat([
            compute_ii_vmt(pa_omx, skims, zones, county_fips, params),
            compute_ext_vmt(pa_omx, skims, params),
        ], ignore_index=True)

    df = pd.concat([tg, vmt], ignore_index=True)
    df["effective_factor"] = df["factored"] / df["unfactored"]

    # % of each vehicle type's own grand total (II all vocations + IX+XI+XX), per metric
    df["vehicle_grand_total"] = df.groupby(["vehicle_type", "metric"])["factored"].transform("sum")
    df["model_pct_of_total"] = df["unfactored"] / df["vehicle_grand_total"] * 100
    df["adj_pct_of_total"] = (df["factored"] - df["unfactored"]) / df["vehicle_grand_total"] * 100

    df.insert(0, "calib_run", run_id)
    voc_order = {v: i for i, v in enumerate(VOCATIONS + ["IX", "XI", "XX"])}
    df = df.sort_values(["metric", "vehicle_type", "component"], key=lambda s: s.map(voc_order) if s.name == "component" else s)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()
