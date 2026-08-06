"""Trip Distribution & HBW Destination Choice stage preprocessing --
extracted from report/2-distribution.qmd so the expensive per-run parsing
(OMX skims/trip matrices, DBF household-disaggregation files) happens once
per tdmcalib run/import, not on every `quarto render`. See
report/preprocess/build_cache.py and report/README.md.

Static/shared reference data (TAZ shapefile, HTS survey CSVs) isn't
run-specific, so it's duplicated here rather than shared with the qmd file
(which isn't itself importable) -- same pattern as the other preprocess
modules. See report/preprocess/modechoice.py's _load_observed_data() for the
precedent."""

from functools import reduce
from pathlib import Path

import geopandas as gpd
import numpy as np
import openmatrix as omx
import pandas as pd
from dbfread import DBF

TAZ_SHP = Path("data/4-assignhwy/taz/WFv1000_TAZ.shp")
HTS_TRIPS_CSV = Path("inputs/UT_HTS_2023_Linked_Trips.csv")
HTS_HH_CSV = Path("inputs/UT_HTS_2023_Households.csv")
SKM_OBS_OMX = Path("inputs/trips_output_CVM_PVM.omx")

# ------------------------------------------------------------------ #
# Static purpose/matrix-name maps -- duplicated from 2-distribution.qmd's
# "CONFIGURATION"/"1. Define Standardization Maps" cells
# ------------------------------------------------------------------ #
PURP_MATS = ["HBW", "HBShp", "HBOth", "HBSch_Pr", "HBSch_Sc", "HBC", "NHBW", "NHBNW"]
TRUCK_MATS = [
    "II_LT", "II_MD", "II_HV",
    "II_LT_D2D", "II_LT_HnS", "II_LT_Lcl", "II_LT_Reg", "II_LT_LHl", "II_LT_Unk",
    "II_MD_D2D", "II_MD_HnS", "II_MD_Lcl", "II_MD_Reg", "II_MD_LHl", "II_MD_Unk", "II_MD_Adj",
    "II_HV_D2D", "II_HV_HnS", "II_HV_Lcl", "II_HV_Reg", "II_HV_LHl", "II_HV_Unk", "II_HV_Adj",
]
EXT_MATS = ["IX", "XI", "IX_MD", "XI_MD", "IX_HV", "XI_HV"]

PURP_MATS_OBS = ["HBW", "HBSHP", "HBOTH", "HBSCH_PR", "HBSCH_SC", "HBC", "NHBW", "NHBNW"]
TRUCK_MATS_OBS = [mat for mat in TRUCK_MATS if mat not in ["II_LT", "II_MD", "II_HV"]]
EXT_MATS_OBS = ["IX", "XI", "IX_MD", "XI_MD", "IX_HV", "XI_HV"]

PURP_MATS_SKIM = ["HBW", "HBShp", "HBOth", "NHBW", "NHBNW", "HBS", "LT", "MD", "HV", "Ext"]

MOD_TRIP_MAP = {"II_LT": "LT", "II_MD": "MD", "II_HV": "HV"}
OBS_TRIP_MAP = {
    "HBSHP": "HBShp", "HBOTH": "HBOth", "HBSCH_PR": "HBSch_Pr", "HBSCH_SC": "HBSch_Sc",
}
SKIM_JOIN_MAP = {
    "IX": "Ext", "XI": "Ext", "IX_MD": "Ext", "XI_MD": "Ext", "IX_HV": "Ext", "XI_HV": "Ext",
    "HBSch_Pr": "HBS", "HBSch_Sc": "HBS",
    "II_LT_D2D": "LT", "II_LT_HnS": "LT", "II_LT_Lcl": "LT", "II_LT_Reg": "LT",
    "II_LT_LHl": "LT", "II_LT_Unk": "LT",
    "II_MD_D2D": "MD", "II_MD_HnS": "MD", "II_MD_Lcl": "MD", "II_MD_Reg": "MD",
    "II_MD_LHl": "MD", "II_MD_Unk": "MD", "II_MD_Adj": "MD",
    "II_HV_D2D": "HV", "II_HV_HnS": "HV", "II_HV_Lcl": "HV", "II_HV_Reg": "HV",
    "II_HV_LHl": "HV", "II_HV_Unk": "HV", "II_HV_Adj": "HV",
}

_HBW_VEH_FILES = [
    "pa_HBW_0veh_hi.omx",
    "pa_HBW_0veh_lo.omx",
    "pa_HBW_1veh_hi.omx",
    "pa_HBW_1veh_lo.omx",
    "pa_HBW_2veh_hi_noXI.omx",
    "pa_HBW_2veh_lo_noXI.omx",
]


def _load_taz(repo_root: Path) -> gpd.GeoDataFrame:
    """No .to_crs() -- matches 2-distribution.qmd's own (unprojected) read."""
    return gpd.read_file(repo_root / "report" / TAZ_SHP, low_memory=False)


def _extract_omx_to_df(omx_path, matrix_names, val_col_name, rename_dict=None, optional_missing=None):
    df_list = []
    taz_ids = np.arange(1, 3630)
    rename_lookup = {k.upper(): v for k, v in (rename_dict or {}).items()}
    optional_missing = {m.upper() for m in (optional_missing or [])}

    with omx.open_file(omx_path, "r") as f:
        matrix_lookup = {mat.upper(): mat for mat in f.list_matrices()}

        for mat_name in matrix_names:
            mat_key = mat_name.upper()
            actual_mat_name = matrix_lookup.get(mat_key)

            if actual_mat_name is None:
                if mat_key not in optional_missing:
                    print(f"Warning: {mat_name} not found in OMX")
                continue

            mat = np.array(f[actual_mat_name]).astype(float)
            ii, jj = np.nonzero(mat)
            std_purpose = rename_lookup.get(mat_key, mat_name)

            df_list.append(pd.DataFrame({
                "i": taz_ids[ii],
                "j": taz_ids[jj],
                val_col_name: mat[ii, jj],
                "Purpose": std_purpose,
            }))

    if df_list:
        return pd.concat(df_list, ignore_index=True)
    return pd.DataFrame(columns=["i", "j", val_col_name, "Purpose"])


def load_mod_trips_dist_gc(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Modeled trips joined to observed trips (shared HTS-derived skim) plus
    distance/generalized-cost skims, for one calibration run."""
    obs_trips = _extract_omx_to_df(
        repo_root / SKM_OBS_OMX,
        PURP_MATS_OBS + TRUCK_MATS_OBS + EXT_MATS_OBS,
        "Trips_Obs",
        rename_dict=OBS_TRIP_MAP,
    )

    mod_trips = _extract_omx_to_df(
        outputs_dir / "PA_AllPurp_GRAVITY.omx",
        PURP_MATS + TRUCK_MATS + EXT_MATS,
        "Trips_Mod",
        rename_dict=MOD_TRIP_MAP,
    )
    mod_dist = _extract_omx_to_df(outputs_dir / "skm_DY_Dist.omx", PURP_MATS_SKIM, "Dist")
    mod_gc = _extract_omx_to_df(outputs_dir / "skm_DY_GC.omx", PURP_MATS_SKIM, "GC")

    df = pd.merge(mod_trips, obs_trips, on=["i", "j", "Purpose"], how="outer")
    df["Trips_Mod"] = df["Trips_Mod"].fillna(0)
    df["Trips_Obs"] = df["Trips_Obs"].fillna(0)

    df["Skim_Purpose"] = df["Purpose"].apply(lambda x: SKIM_JOIN_MAP.get(x, x))
    mod_dist = mod_dist.rename(columns={"Purpose": "Skim_Purpose"})
    mod_gc = mod_gc.rename(columns={"Purpose": "Skim_Purpose"})

    df = pd.merge(df, mod_dist, on=["i", "j", "Skim_Purpose"], how="left")
    df = pd.merge(df, mod_gc, on=["i", "j", "Skim_Purpose"], how="left")
    df = df.drop(columns=["Skim_Purpose"])
    df["Dist"] = df["Dist"].fillna(0)
    df["GC"] = df["GC"].fillna(0)
    return df


def load_mod_intra(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Modeled intrazonal trip percentage by purpose, for one calibration run."""
    results = []
    with omx.open_file(outputs_dir / "PA_AllPurp_GRAVITY.omx", "r") as f:
        for mat_name in PURP_MATS:
            if mat_name not in f.list_matrices():
                print(f"Warning: {mat_name} not found in OMX")
                continue
            mat = f[mat_name][:].astype(float)
            total_trips = mat.sum()
            intra_trips = np.trace(mat)
            results.append({
                "PURP": mat_name,
                "total_trips": total_trips,
                "intra_trips": intra_trips,
                "pct_intrazonal": 100 * intra_trips / total_trips,
            })
    return pd.DataFrame(results)[["PURP", "pct_intrazonal"]]


def load_master_trips(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Modeled trips by purpose, summarized to District and County
    geographies, for one calibration run. (Observed-side summarization
    stays inline in the qmd -- it's shared/not run-specific.)"""
    tazv10 = _load_taz(repo_root)
    taz_ids = np.arange(1, 3630)

    od_results = []
    with omx.open_file(outputs_dir / "PA_AllPurp_GRAVITY.omx", "r") as f:
        for mat_name in PURP_MATS:
            if mat_name not in f.list_matrices():
                print(f"Warning: {mat_name} not found in OMX")
                continue
            mat = f[mat_name][:].astype(float)
            ii, jj = np.nonzero(mat)
            od_results.extend(
                {"i": taz_ids[i], "j": taz_ids[j], "trips": mat[i, j], "purpose": mat_name}
                for i, j in zip(ii, jj)
            )

    mod_trips = pd.DataFrame(od_results)
    mod_trips = mod_trips.merge(tazv10[["TAZID", "DISTLRG", "CO_FIPS"]], how="left", left_on="i", right_on="TAZID")
    mod_trips = mod_trips.rename(columns={"DISTLRG": "p_DistLrg", "CO_FIPS": "p_CO_FIPS"}).drop(columns={"TAZID"})
    mod_trips = mod_trips.merge(tazv10[["TAZID", "DISTLRG", "CO_FIPS"]], how="left", left_on="j", right_on="TAZID")
    mod_trips = mod_trips.rename(columns={"DISTLRG": "a_DistLrg", "CO_FIPS": "a_CO_FIPS"}).drop(columns={"TAZID"})
    mod_trips = mod_trips.rename(columns={"purpose": "PURP"})

    mod_trips_dist = mod_trips.groupby(["PURP", "p_DistLrg", "a_DistLrg"], as_index=False).agg(trips=("trips", "sum"))
    mod_trips_co = mod_trips.groupby(["PURP", "p_CO_FIPS", "a_CO_FIPS"], as_index=False).agg(trips=("trips", "sum"))
    mod_trips_dist["Geo"] = "District"
    mod_trips_co["Geo"] = "County"
    mod_trips_dist = mod_trips_dist.rename(columns={"p_DistLrg": "p_Loc", "a_DistLrg": "a_Loc", "trips": "mod"})
    mod_trips_co = mod_trips_co.rename(columns={"p_CO_FIPS": "p_Loc", "a_CO_FIPS": "a_Loc", "trips": "mod"})
    return pd.concat([mod_trips_dist, mod_trips_co], ignore_index=True)


def load_dist_sum_mod(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """HBW trips by District, from both the Destination Choice and Gravity
    models, for one calibration run. Pure function of outputs_dir -- no
    shared/reference data needed."""
    dist_sum_mod_mc = pd.read_csv(outputs_dir / "DISTLRG_PA_AllPurp.csv", low_memory=False)[
        ["I", "J", "HBW", "HBO", "NHB", "HBSch", "HBC"]
    ]
    dist_sum_mod_mc = dist_sum_mod_mc.rename(columns={"I": "p_DistLrg", "J": "a_DistLrg"})
    dist_sum_mod_mc = dist_sum_mod_mc.melt(
        id_vars=["p_DistLrg", "a_DistLrg"],
        value_vars=["HBW", "HBO", "NHB", "HBSch", "HBC"],
        var_name="PURP5_t",
        value_name="total_trips",
    )
    dist_sum_mod_mc["Source"] = "Destination Choice"

    dist_sum_mod_db = pd.read_csv(outputs_dir / "DISTLRG_PA_Gravity_AllPurp.csv", low_memory=False)
    dist_sum_mod_db["HBO"] = dist_sum_mod_db["HBOth"] + dist_sum_mod_db["HBShp"]
    dist_sum_mod_db["HBSch"] = dist_sum_mod_db["HBSch_Pr"] + dist_sum_mod_db["HBSch_Sc"]
    dist_sum_mod_db["NHB"] = dist_sum_mod_db["NHBW"] + dist_sum_mod_db["NHBNW"]
    dist_sum_mod_db = dist_sum_mod_db[["I", "J", "HBW", "HBO", "NHB", "HBSch", "HBC"]]
    dist_sum_mod_db = dist_sum_mod_db.rename(columns={"I": "p_DistLrg", "J": "a_DistLrg"})
    dist_sum_mod_db = dist_sum_mod_db.melt(
        id_vars=["p_DistLrg", "a_DistLrg"],
        value_vars=["HBW", "HBO", "NHB", "HBSch", "HBC"],
        var_name="PURP5_t",
        value_name="total_trips",
    )
    dist_sum_mod_db["Source"] = "Gravity"

    dist_sum_mod = pd.concat([dist_sum_mod_mc, dist_sum_mod_db], ignore_index=True)
    dist_sum_mod = dist_sum_mod[dist_sum_mod["PURP5_t"] == "HBW"]
    return dist_sum_mod[["Source", "p_DistLrg", "a_DistLrg", "total_trips"]]


def _parse_veh_inc(fname: str) -> str:
    base = fname.rsplit(".", 1)[0]
    base = base.replace("pa_", "")
    base = base.replace("_noXI", "")
    return base


def load_mod_dist_hbw_sum(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """HBW trips by District x vehicle-ownership/income segment, for one
    calibration run."""
    tazv10_wf = _load_taz(repo_root)[["TAZID", "DISTLRG"]]

    dfs = []
    for f in _HBW_VEH_FILES:
        with omx.open_file(outputs_dir / f, "r") as omx_file:
            mat = omx_file["trips"][:]
        df = (
            pd.DataFrame(mat)
            .reset_index()
            .melt(id_vars="index", var_name="a_taz", value_name="trips")
            .rename(columns={"index": "p_taz"})
        )
        df["p_taz"] += 1
        df["a_taz"] += 1
        df["veh_inc"] = _parse_veh_inc(f)
        dfs.append(df)
    mod_taz_hbw_0 = pd.concat(dfs, ignore_index=True)

    mod_taz_hbw_1 = mod_taz_hbw_0.merge(tazv10_wf, how="left", left_on="p_taz", right_on="TAZID")
    mod_taz_hbw_1 = mod_taz_hbw_1.rename(columns={"DISTLRG": "p_DistLrg"}).drop(columns={"TAZID"})
    mod_taz_hbw_2 = mod_taz_hbw_1.merge(tazv10_wf, how="left", left_on="a_taz", right_on="TAZID")
    mod_taz_hbw_2 = mod_taz_hbw_2.rename(columns={"DISTLRG": "a_DistLrg"}).drop(columns={"TAZID"})

    return (
        mod_taz_hbw_2[["veh_inc", "p_DistLrg", "a_DistLrg", "trips"]]
        .groupby(["veh_inc", "p_DistLrg", "a_DistLrg"], as_index=False)
        .agg(total_trips=("trips", "sum"))
    )


def load_mod_distrib_hbw_sum(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """HBW gravity-model trips by District x vehicle-ownership/income
    segment (derived from the household-disaggregation share breakdown, not
    separate OMX files like load_mod_dist_hbw_sum), for one calibration
    run."""
    tazv10_wf = _load_taz(repo_root)[["TAZID", "DISTLRG"]]

    hhdisag_dfs = {
        s: pd.DataFrame(DBF(outputs_dir / f"VO_HH{s}_IncLoHi_Worker_VehOwn.dbf", load=True))
        for s in range(1, 7)
    }

    for s, df in hhdisag_dfs.items():
        for inc in ["L", "H"]:
            for v in range(4):
                cols = [f"S{s}I{inc}W{w}V{v}" for w in range(4)]
                df[f"S{s}I{inc}V{v}"] = df[cols].sum(axis=1)

    Z_COLS = ["Z"]
    dfs_list = [hhdisag_dfs[s] for s in range(1, 7)]
    df_merged = reduce(lambda left, right: pd.merge(left, right, on=Z_COLS, how="left"), dfs_list)

    final_hhdisag_vals = df_merged[Z_COLS].copy()
    for inc in ["L", "H"]:
        for v in range(4):
            cols = [f"S{s}I{inc}V{v}" for s in range(1, 7)]
            final_hhdisag_vals[f"I{inc}V{v}"] = df_merged[cols].sum(axis=1)

    final_hhdisag_vals = final_hhdisag_vals[Z_COLS + [c for c in final_hhdisag_vals.columns if c.startswith("I")]]

    for inc in ["L", "H"]:
        final_hhdisag_vals[f"I{inc}V2"] = final_hhdisag_vals[f"I{inc}V2"] + final_hhdisag_vals[f"I{inc}V3"]
    final_hhdisag_vals = final_hhdisag_vals.drop(columns=[f"I{inc}V3" for inc in ["L", "H"]])

    final_hhdisag_pct = final_hhdisag_vals.copy()
    row_totals = final_hhdisag_pct.drop(columns=Z_COLS).sum(axis=1)
    final_hhdisag_pct.loc[:, final_hhdisag_pct.columns.difference(Z_COLS)] = (
        final_hhdisag_pct.drop(columns=Z_COLS).div(row_totals, axis=0)
    )
    final_hhdisag_pct.loc[:, final_hhdisag_pct.columns.difference(Z_COLS)] = (
        final_hhdisag_pct.loc[:, final_hhdisag_pct.columns.difference(Z_COLS)].round(4)
    )
    final_hhdisag_pct = final_hhdisag_pct.fillna(0)

    taz_ids = list(range(1, 3630))
    with omx.open_file(outputs_dir / "PA_AllPurp_GRAVITY.omx", "r") as f:
        mat = f["HBW"][:].astype(float)

    df = pd.DataFrame(mat, index=taz_ids, columns=taz_ids)
    hbw_distrib_trips = df.stack().reset_index()
    hbw_distrib_trips.columns = ["i", "j", "trips"]

    mod_distrib_hbw = hbw_distrib_trips.merge(final_hhdisag_pct, left_on="i", right_on="Z", how="left").drop(columns=["Z"])
    mod_distrib_hbw["HBW_0veh_lo"] = mod_distrib_hbw["ILV0"] * mod_distrib_hbw["trips"]
    mod_distrib_hbw["HBW_0veh_hi"] = mod_distrib_hbw["IHV0"] * mod_distrib_hbw["trips"]
    mod_distrib_hbw["HBW_1veh_lo"] = mod_distrib_hbw["ILV1"] * mod_distrib_hbw["trips"]
    mod_distrib_hbw["HBW_1veh_hi"] = mod_distrib_hbw["IHV1"] * mod_distrib_hbw["trips"]
    mod_distrib_hbw["HBW_2veh_lo"] = mod_distrib_hbw["ILV2"] * mod_distrib_hbw["trips"]
    mod_distrib_hbw["HBW_2veh_hi"] = mod_distrib_hbw["IHV2"] * mod_distrib_hbw["trips"]

    hbw_cols = ["HBW_0veh_lo", "HBW_0veh_hi", "HBW_1veh_lo", "HBW_1veh_hi", "HBW_2veh_lo", "HBW_2veh_hi"]
    mod_distrib_hbw_long = mod_distrib_hbw.melt(
        id_vars=["i", "j"], value_vars=hbw_cols, var_name="veh_inc", value_name="hbw_trips"
    )
    mod_distrib_hbw_long = mod_distrib_hbw_long.rename(columns={"hbw_trips": "trips"})

    mod_distrib_hbw_1 = mod_distrib_hbw_long.merge(tazv10_wf, how="left", left_on="i", right_on="TAZID")
    mod_distrib_hbw_1 = mod_distrib_hbw_1.rename(columns={"DISTLRG": "p_DistLrg"}).drop(columns={"TAZID"})
    mod_distrib_hbw_2 = mod_distrib_hbw_1.merge(tazv10_wf, how="left", left_on="j", right_on="TAZID")
    mod_distrib_hbw_2 = mod_distrib_hbw_2.rename(columns={"DISTLRG": "a_DistLrg"}).drop(columns={"TAZID"})

    return (
        mod_distrib_hbw_2[["veh_inc", "p_DistLrg", "a_DistLrg", "trips"]]
        .groupby(["veh_inc", "p_DistLrg", "a_DistLrg"], as_index=False)
        .agg(total_trips=("trips", "sum"))
    )
