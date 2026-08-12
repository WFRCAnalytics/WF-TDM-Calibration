"""Highway Assignment stage preprocessing -- extracted from
report/4-assignhwy.qmd so the expensive per-run parsing (Summary_SEGID(_Detailed)
CSVs, OMX skims) plus the shared CCS-station-to-network spatial join happen
once per tdmcalib run/import, not on every `quarto render`. See
report/preprocess/build_cache.py and report/README.md.

Static/shared reference data (TAZ/segment shapefiles, CCS counts, Google API
speeds) isn't run-specific, so it's duplicated here rather than shared with
the qmd file (which isn't itself importable) -- same pattern as the other
preprocess modules. Several loaders below need the same shared
spatial-join/merge result (df_bridge, df_merged_base, the Google-speeds base
table); each recomputes it independently rather than restructuring
build_cache.py's flat loader registry -- accepted redundant computation, same
tradeoff as report/preprocess/modechoice.py's _load_observed_data()."""

import glob
from pathlib import Path

import geopandas as gpd
import numpy as np
import openmatrix as omx
import pandas as pd
from shapely.geometry import Point

from report import _validation_scripts as vs

TAZ_SHP = Path("data/4-assignhwy/taz/WFv1000_TAZ.shp")
GEOJSON_FILE = Path("data/4-assignhwy/taz/tazv10.geojson")
PATH_IN_REGION = Path("data/4-assignhwy/RegionalBoundary.gpkg")
PATH_IN_SEGMENTS = Path("data/4-assignhwy/seg_shp/WFv1000_Segments.shp")
PATH_IN_CCS_COUNTS = Path("data/4-assignhwy/UDOT_VehicleClassificationCounts/JKLP_Length_WFRC_2023_Sept_Nov.csv")
PATH_IN_CCS_SPLIT_FACTORS = Path("data/4-assignhwy/UDOT_VehicleClassificationCounts/LT_MD_HV_Split_Factors_2025.csv")
PATH_IN_CCS_LOCATIONS = Path("data/4-assignhwy/UDOT_VehicleClassificationCounts/SiteData.csv")
GOOGLE_SPEEDS_MAG = Path("data/4-assignhwy/google-api-speeds/MAG/both_time_*_2023.csv")
GOOGLE_SPEEDS_WFRC = Path("data/4-assignhwy/google-api-speeds/WFRC/both_time_*_2023.csv")
PATH_IN_CCS_DAILY = Path("inputs/CCS_Observed_Counts_Raw.csv")

CRS_UTM = 26912
FIPS_MAP = {3: "Box Elder", 11: "Davis", 35: "Salt Lake", 49: "Utah", 57: "Weber"}
PERIODS = ["AM", "MD", "PM", "EV"]


def _build_bridge(repo_root: Path) -> pd.DataFrame:
    """CCS station -> nearest network SEGID match, plus manual overrides.
    Shared/not run-specific -- duplicated from 4-assignhwy.qmd's
    ccs-region/ccs-segments/ccs-locations/ccs-spatial-join/ccs-manual-override
    cells."""
    report_dir = repo_root / "report"

    gdf_region = (
        gpd.read_file(
            report_dir / PATH_IN_REGION,
            layer="RegionalBoundaryComponents",
            where="PlanOrg IN ('MAG MPO', 'WFRC MPO')",
        )
        .dissolve()
        .to_crs(CRS_UTM)
    )
    gdf_region["geometry"] = gdf_region.buffer(1).buffer(-1).buffer(16093.4)

    gdf_segments = gpd.read_file(report_dir / PATH_IN_SEGMENTS).to_crs(CRS_UTM)
    gdf_segments["SEGID"] = gdf_segments["SEGID"].astype(str)
    temp_route = gdf_segments["SEGID"].str.split("_").str[0]
    gdf_segments["MODEL_ROUTE"] = pd.to_numeric(temp_route, errors="coerce")
    gdf_segments["MODEL_MP"] = gdf_segments["SEGID"].str.split("_").str[1].astype(float)

    gdf_network_clean = gdf_segments.dropna(subset=["MODEL_ROUTE", "MODEL_MP"]).copy()
    gdf_network_clean["MODEL_ROUTE"] = gdf_network_clean["MODEL_ROUTE"].astype(int)

    df_sites = pd.read_csv(report_dir / PATH_IN_CCS_LOCATIONS)
    gdf_ccs_locations = (
        gpd.GeoDataFrame(
            df_sites,
            geometry=gpd.points_from_xy(df_sites.LONGITUDE, df_sites.LATITUDE),
            crs="EPSG:4326",
        )
        .to_crs(CRS_UTM)
        .clip(gdf_region)
    )
    gdf_ccs_locations["SITE"] = gdf_ccs_locations["SITE"].astype(str)
    gdf_ccs_locations["ROUTE"] = (
        pd.to_numeric(gdf_ccs_locations["ROUTE"], errors="coerce").fillna(0).astype(int)
    )
    gdf_ccs_locations["MILEPOST"] = pd.to_numeric(gdf_ccs_locations["MILEPOST"], errors="coerce")

    gdf_net_join = gdf_network_clean.copy()
    gdf_net_join["MODEL_ROUTE"] = (
        pd.to_numeric(gdf_net_join["MODEL_ROUTE"], errors="coerce").fillna(0).astype(int)
    )
    gdf_net_join["BMP"] = pd.to_numeric(gdf_net_join["BMP"], errors="coerce")
    gdf_net_join["EMP"] = pd.to_numeric(gdf_net_join["EMP"], errors="coerce")

    match_results = []
    for _, row in gdf_ccs_locations.iterrows():
        site_id = row["SITE"]
        route = row["ROUTE"]
        mp = row["MILEPOST"]
        geom = row["geometry"]

        matched_segid = None
        match_type = "None"

        if route > 0:
            route_segs = gdf_net_join[gdf_net_join["MODEL_ROUTE"] == route]
        else:
            route_segs = pd.DataFrame()

        if not route_segs.empty:
            mp_match = route_segs[
                (route_segs["BMP"] <= mp + 0.001) & (route_segs["EMP"] >= mp - 0.001)
            ]
            if not mp_match.empty:
                matched_segid = mp_match.loc[mp_match.distance(geom).idxmin(), "SEGID"]
                match_type = "1. Route + MP Match"
            elif matched_segid is None:
                matched_segid = gdf_net_join.loc[gdf_net_join.distance(geom).idxmin(), "SEGID"]
                match_type = "3. Global Nearest (Fallback)"
        elif matched_segid is None:
            matched_segid = route_segs.loc[route_segs.distance(geom).idxmin(), "SEGID"]
            match_type = "3. Global Nearest (Fallback)"

        match_results.append(
            {"SITE": site_id, "MATCHED_SEGID": matched_segid, "MATCH_TYPE": match_type}
        )

    df_bridge = pd.DataFrame(match_results)
    df_bridge = df_bridge.merge(
        gdf_network_clean[["SEGID", "CO_FIPS"]].assign(
            COUNTY_NAME=lambda x: x["CO_FIPS"].map(FIPS_MAP).fillna("Other")
        ),
        left_on="MATCHED_SEGID",
        right_on="SEGID",
        how="left",
    ).drop(columns=["SEGID", "CO_FIPS"])

    df_bridge = df_bridge[~df_bridge["SITE"].isin(["-680"])]
    df_bridge = df_bridge[~df_bridge["SITE"].isin(["-816", "-302"])]
    df_bridge = df_bridge[~df_bridge["SITE"].isin(["-664"])]
    return df_bridge


def _build_seg_shp(repo_root: Path) -> gpd.GeoDataFrame:
    return gpd.read_file(
        repo_root / "report" / PATH_IN_SEGMENTS,
        include_fields=[
            "SEGID", "DISTANCE", "AADT2023", "FAC_WDAVG", "SUTRUCKS", "CUTRUCKS",
            "CO_FIPS", "FTCLASS", "geometry",
        ],
    )


def load_mod_tidy(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Modeled volume by SEGID x period x vehicle type, filtered to CCS-matched
    segments, for one calibration run."""
    df_bridge = _build_bridge(repo_root)

    df_mod_summary = pd.read_csv(vs.find_one(outputs_dir, "*Summary_SEGID.csv"))
    df_mod_clean = df_mod_summary[
        (df_mod_summary["DIRECTION"] == "Both")
        & (df_mod_summary["FUNCGROUP"] == "Total")
        & (df_mod_summary["SEGID"].isin(df_bridge["MATCHED_SEGID"].unique()))
    ].copy()
    df_mod_clean["SEGID"] = df_mod_clean["SEGID"].astype(str)

    melt_vars = []
    for p in PERIODS:
        df_mod_clean[f"{p}_Vol_Auto"] = df_mod_clean[f"{p}_Vol_PC"] + df_mod_clean[f"{p}_Vol_LT"]
        df_mod_clean[f"{p}_Vol_SUT"] = df_mod_clean[f"{p}_Vol_MD"]
        df_mod_clean[f"{p}_Vol_CUT"] = df_mod_clean[f"{p}_Vol_HV"]
        melt_vars.extend([f"{p}_Vol_Auto", f"{p}_Vol_SUT", f"{p}_Vol_CUT"])

    df_tidy = df_mod_clean.melt(
        id_vars=["SEGID", "FTCLASS", "ATYPENAME"],
        value_vars=melt_vars,
        var_name="Metric",
        value_name="MODELED",
    )
    df_tidy[["PERIOD", "_", "VEHICLE_TYPE"]] = df_tidy["Metric"].str.split("_", expand=True)
    return df_tidy.drop(columns=["Metric", "_"])


def _build_merged_base(repo_root: Path) -> pd.DataFrame:
    """Daily CCS counts joined to matched-segment metadata (AADT2023,
    FTCLASS, ATYPENAME). Shared/not run-specific -- duplicated from
    4-assignhwy.qmd's ccs-daily-prep cell (steps 1-2)."""
    df_bridge = _build_bridge(repo_root)
    seg_shp = _build_seg_shp(repo_root)

    df_raw_daily = pd.read_csv(repo_root / PATH_IN_CCS_DAILY)
    df_raw_daily["DATE_ONLY"] = pd.to_datetime(df_raw_daily["DATE_ONLY"])

    df_2023 = df_raw_daily[df_raw_daily["DATE_ONLY"].dt.year == 2023].copy()
    df_2023 = df_2023.rename(columns={"TOTAL_VOL": "DAILY_VOL", "STATION": "SITE"})
    df_2023["SITE"] = df_2023["SITE"].astype(str)

    df_merged_base = df_2023.merge(
        df_bridge[["SITE", "MATCHED_SEGID", "COUNTY_NAME"]], on="SITE", how="inner"
    )
    df_merged_base = df_merged_base.merge(
        seg_shp[["SEGID", "AADT2023"]], left_on="MATCHED_SEGID", right_on="SEGID", how="left"
    )
    return df_merged_base


def load_ccs_daily(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Daily CCS volume vs. modeled DY volume, by station, for one
    calibration run."""
    df_merged_base = _build_merged_base(repo_root)

    mod_df_wide = pd.read_csv(vs.find_one(outputs_dir, "*Summary_SEGID.csv"))
    if "DY_Vol" not in mod_df_wide.columns:
        mod_df_wide["DY_Vol"] = (
            mod_df_wide["DY_Vol_PC"]
            + mod_df_wide["DY_Vol_LT"]
            + mod_df_wide["DY_Vol_MD"]
            + mod_df_wide["DY_Vol_HV"]
        )

    df_merged = df_merged_base.merge(
        mod_df_wide[["SEGID", "DY_Vol", "FTCLASS", "ATYPENAME"]], on="SEGID", how="left"
    )

    df = df_merged[
        ["SITE", "DATE_ONLY", "DAILY_VOL", "COUNTY_NAME", "FTCLASS", "ATYPENAME", "AADT2023", "DY_Vol"]
    ].copy()
    df.rename(columns={"AADT2023": "HPMS_AADT", "DY_Vol": "MODEL_VOL"}, inplace=True)
    df["DATE_STR"] = df["DATE_ONLY"].dt.strftime("%Y-%m-%d")
    df = df.fillna(0)
    # FTCLASS/ATYPENAME are categorical strings, but unmatched rows get the
    # same blanket fillna(0) as the numeric columns above (matching
    # 4-assignhwy.qmd's own .fillna(0) exactly) -- cast to str so the column
    # stays a single dtype (mixed str/int object columns aren't
    # parquet-writable, unlike the in-memory-only pre-cache version).
    df["FTCLASS"] = df["FTCLASS"].astype(str)
    df["ATYPENAME"] = df["ATYPENAME"].astype(str)
    return df


def load_seg_detail(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Modeled managed-lane volume by SEGID x direction x period, for one
    calibration run. Pure function of outputs_dir -- no shared/reference
    data needed."""
    df = pd.read_csv(vs.find_one(outputs_dir, "*Summary_SEGID_Detailed.csv"))

    df = df[df["FUNCGROUP"] == "Managed"]
    df = df[df["DIRECTION"].isin(["D1", "D2"])]
    df = df[["SEGID", "DIRECTION", "DIRECTION_NAME", "AM_Vol", "MD_Vol", "PM_Vol", "EV_Vol"]]
    df["DY_Vol"] = df["AM_Vol"] + df["MD_Vol"] + df["PM_Vol"] + df["EV_Vol"]

    df = df.melt(
        id_vars=["SEGID", "DIRECTION", "DIRECTION_NAME"],
        value_vars=["AM_Vol", "MD_Vol", "PM_Vol", "EV_Vol", "DY_Vol"],
        var_name="Period",
        value_name="Mod_Vol",
    )
    df["Period"] = df["Period"].str.replace("_Vol", "", regex=False)

    df_both = df.groupby(["SEGID", "Period"])["Mod_Vol"].sum().reset_index()
    df_both["DIRECTION"] = "Both"
    df_both["DIRECTION_NAME"] = "Both"
    df = pd.concat([df, df_both], ignore_index=True)

    period_hours = {"AM": 3, "MD": 6, "PM": 3, "EV": 12, "DY": 24}
    df["Mod_Vph"] = df.apply(lambda row: row["Mod_Vol"] / period_hours[row["Period"]], axis=1)
    return df


def _build_base_xx(repo_root: Path) -> pd.DataFrame:
    """Observed median travel time by O/D TAZ x period, from the Google API
    speed extracts. Shared/not run-specific -- duplicated from
    4-assignhwy.qmd's Average-Travel-Time section (the cells building df1,
    dfa/dfb, and the base `xx` pivot, before the per-run OMX columns are
    added)."""
    report_dir = repo_root / "report"

    all_files = (
        glob.glob(str(report_dir / GOOGLE_SPEEDS_MAG)) + glob.glob(str(report_dir / GOOGLE_SPEEDS_WFRC))
    )
    files = pd.DataFrame([Path(p) for p in all_files], columns=["fullpath"])
    files["filename"] = files["fullpath"].apply(lambda p: p.name)
    files["fullpath"] = files["fullpath"].astype(str)

    df1 = pd.DataFrame()
    for f in files["filename"].unique():
        paths = files[files["filename"] == f]["fullpath"]
        dfs = [pd.read_csv(path) for path in paths]
        concat_df = pd.concat(dfs)

        if any(field in f for field in ["both_time_6", "both_time_7", "both_time_8", "both_time_9"]):
            concat_df["Period"] = "obsAM"
        if any(field in f for field in ["both_time_11", "both_time_12", "both_time_13"]):
            concat_df["Period"] = "obsMD"
        if any(field in f for field in ["both_time_16", "both_time_17", "both_time_18", "both_time_15"]):
            concat_df["Period"] = "obsPM"
        if any(field in f for field in ["both_time_5"]):
            concat_df["Period"] = "obsEV"

        df1 = pd.concat([df1, concat_df[pd.notnull(concat_df[" DODistance"])]])

    df1["O_Coordinate"] = df1[" O_Coordinate"].astype(str)
    df1["D_Coordinate"] = df1[" D_Coordinate"].astype(str)
    df1[["O_Coordinate_X", "O_Coordinate_Y"]] = (
        df1["O_Coordinate"].str.strip("()").str.split(",", expand=True).astype(float)
    )
    df1[["D_Coordinate_X", "D_Coordinate_Y"]] = (
        df1["D_Coordinate"].str.strip("()").str.split(",", expand=True).astype(float)
    )
    df1 = df1.drop(columns=["O_Coordinate", " O_Coordinate", "D_Coordinate", " D_Coordinate", "O_TAZID", " D_TAZID"])

    gdf_polygons = gpd.read_file(report_dir / GEOJSON_FILE)

    geometry_o = [Point(xy[::-1]) for xy in zip(df1["O_Coordinate_X"], df1["O_Coordinate_Y"])]
    gdf_o = gpd.GeoDataFrame(df1, geometry=geometry_o)
    df1["O_TAZID"] = gpd.sjoin(gdf_o, gdf_polygons, how="left", predicate="within")["TAZID"]

    geometry_d = [Point(xy[::-1]) for xy in zip(df1["D_Coordinate_X"], df1["D_Coordinate_Y"])]
    gdf_d = gpd.GeoDataFrame(df1, geometry=geometry_d)
    df1[" D_TAZID"] = gpd.sjoin(gdf_d, gdf_polygons, how="left", predicate="within")["TAZID"]

    dfa = df1[["O_TAZID", " D_TAZID", "Period", " ODDistance", " ODTime"]].copy()
    dfb = df1[["O_TAZID", " D_TAZID", "Period", " DODistance", " DOTime"]].copy()
    dfb.rename(
        columns={"O_TAZID": " D_TAZID", " D_TAZID": "O_TAZID", " DODistance": " ODDistance", " DOTime": " ODTime"},
        inplace=True,
    )
    dfa = pd.concat([dfa, dfb])
    dfx = dfa[["O_TAZID", " D_TAZID", "Period", " ODTime", " ODDistance"]]
    dfx = dfx.rename(columns={" ODTime": "Time", " D_TAZID": "D_TAZID", " ODDistance": "Distance"})
    dfx["Time"] = dfx["Time"] / 60
    dfx["Distance"] = dfx["Distance"] / 1609.344  # meters -> miles

    grouped = dfx.groupby(["O_TAZID", "D_TAZID", "Period"]).agg({"Time": "median", "Distance": "median"}).unstack()
    # Time columns keep their existing obsAM/obsMD/... names (unchanged
    # contract for callers); Distance columns get an inserted "Dist" so the
    # two metrics don't collide, e.g. obsDistAM alongside obsAM.
    grouped.columns = [
        period if metric == "Time" else f"{period[:3]}Dist{period[3:]}" for metric, period in grouped.columns
    ]
    return grouped.reset_index()


_XX_OMX_FILES = ["Skm_AM.omx", "Skm_MD.omx", "Skm_PM.omx", "Skm_EV.omx"]
_XX_COLUMNS = ["modAM", "modMD", "modPM", "modEV"]
_XX_DIST_COLUMNS = ["modDistAM", "modDistMD", "modDistPM", "modDistEV"]


def _extract_skim_from_omx(omx_file_path, tab_name, column_name, base_df):
    with omx.open_file(omx_file_path, "r") as f:
        matrix = f[tab_name][:]

    o_idx = base_df["O_TAZID"].to_numpy(dtype=int) - 1
    d_idx = base_df["D_TAZID"].to_numpy(dtype=int) - 1

    base_df[column_name] = matrix[o_idx, d_idx]
    return base_df


def load_xx(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Observed (Google API) vs. modeled (GP_IVT/GP_Dist skims) median travel
    time and distance by O/D TAZ x period, for one calibration run. Distance
    is each source's own: observed road distance from the Google data,
    modeled path distance (GP_Dist, already in miles) from the same skim
    file GP_IVT comes from -- so Model speed = model time over the model's
    own path, not the Google route."""
    df_run = _build_base_xx(repo_root)
    for omx_file, column_name in zip(_XX_OMX_FILES, _XX_COLUMNS):
        df_run = _extract_skim_from_omx(outputs_dir / omx_file, "GP_IVT", column_name, df_run)
    for omx_file, column_name in zip(_XX_OMX_FILES, _XX_DIST_COLUMNS):
        df_run = _extract_skim_from_omx(outputs_dir / omx_file, "GP_Dist", column_name, df_run)
    return df_run
