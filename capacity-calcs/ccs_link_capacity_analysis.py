"""Compares observed CCS hourly volumes against the TDM's own spdcap capacity
assumptions, by facility type (FT).

For each CCS station, finds the max volume recorded in a single lane, single
direction, within the Sept 1 - Nov 15 (Tue-Thu) calibration window, from the
raw hourly-by-lane workbooks in data/. Matches each station to its nearest
link on the filtered TDM network (centroid connectors, ramps, and HOV links
excluded) to get that link's FT, lane count, and CAP1HR1LN (the model's
per-lane-per-hour capacity assumption, itself sourced from
tdm/1_Inputs/0_GlobalData/0_SpeedCap/Lookup_Speed_Capacity.csv by FT + lane
count). Flags stations inside a mountainous TAZ (MARGINAL=1).

Three station sets are excluded from the final tables (not from the raw
per-station output, which keeps everything for inspection):
  - OUTLIER_STATIONS: >150% of assumed capacity even within the calibration
    window -- implausible single-hour readings, likely sensor/data issues.
  - BANGERTER_EXPRESSWAY_STATIONS: Bangerter Hwy stations currently coded
    FT 13/15 (Expressway). Bangerter is being converted to freeway, so its
    current FT may not represent it well. -636 is already FT 32 (Freeway)
    and isn't in this list.
  - Stations inside a MARGINAL=1 TAZ (mountainous canyon zones) -- excluded
    dynamically via the spatial join below, not a hardcoded list.

Usage (from repo root):
    .venv/Scripts/python.exe capacity-calcs/ccs_link_capacity_analysis.py
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent / "output"

# Which run's scenario network to pull the link shapefile from. The link
# shapefile lives inside the gitignored tdm/Scenarios/{run}/ tree (per-run,
# not committed), so this must be a run still present on disk locally.
SCENARIO_RUN = "C74"

LINK_SHP = REPO_ROOT / "tdm" / "Scenarios" / SCENARIO_RUN / "0_InputProcessing" / "ScenarioNet" / "scenario - Link.shp"
TAZ_SHP = REPO_ROOT / "report" / "data" / "4-assignhwy" / "taz" / "WFv1000_TAZ.shp"
REGION_GPKG = REPO_ROOT / "report" / "data" / "4-assignhwy" / "RegionalBoundary.gpkg"
CCS_LOCATIONS = REPO_ROOT / "report" / "data" / "4-assignhwy" / "UDOT_VehicleClassificationCounts" / "SiteData.csv"
CCS_LOCATIONS_SUPPLEMENT = REPO_ROOT / "report" / "data" / "4-assignhwy" / "UDOT_VehicleClassificationCounts" / "SiteData_supplement.csv"
SPDCAP_LOOKUP = REPO_ROOT / "tdm" / "1_Inputs" / "0_GlobalData" / "0_SpeedCap" / "Lookup_Speed_Capacity.csv"
CCS_LANE_WORKBOOKS = [
    REPO_ROOT / "data" / "2023 Station 301-431.xlsx",
    REPO_ROOT / "data" / "2023 Station 501-733.xlsx",
]

CRS_UTM = 26912  # NAD83 / UTM zone 12N
HOUR_COLS = [f"H{str(h).zfill(2)}00" for h in range(24)]

# Same Sept 1 - Nov 15, Tue-Thu window report/4-assignhwy.qmd uses for its
# own CCS "Target" volumes -- keeps this analysis's calibration-window max
# directly comparable to what the report calls Target.
CALIB_WINDOW_START = "2023-09-01"
CALIB_WINDOW_END = "2023-11-15"
CALIB_WEEKDAYS = [1, 2, 3]  # Tue, Wed, Thu

# Stations manually dropped by -- see module docstring for why.
OUTLIER_STATIONS = ["-635", "-665", "-319", "-306", "-626"]
BANGERTER_EXPRESSWAY_STATIONS = ["-627", "-711", "-819", "-820"]

# Hand-removed from the CCS bridge elsewhere in this report's pipeline
# (ramp/interchange stations, not representative of a through-lane count).
DROP_SITES = ["-680", "-816", "-302"]


def load_ccs_site_locations() -> gpd.GeoDataFrame:
    df_sites = pd.read_csv(CCS_LOCATIONS)
    df_sites_supp = pd.read_csv(CCS_LOCATIONS_SUPPLEMENT)
    df_sites = pd.concat([df_sites, df_sites_supp], ignore_index=True).drop_duplicates(
        subset="SITE", keep="first"
    )

    gdf_region = (
        gpd.read_file(REGION_GPKG, layer="RegionalBoundaryComponents", where="PlanOrg IN ('MAG MPO', 'WFRC MPO')")
        .dissolve()
        .to_crs(CRS_UTM)
    )
    gdf_region["geometry"] = gdf_region.buffer(1).buffer(-1).buffer(16093.4)  # 10mi buffer

    gdf_ccs = (
        gpd.GeoDataFrame(df_sites, geometry=gpd.points_from_xy(df_sites.LONGITUDE, df_sites.LATITUDE), crs="EPSG:4326")
        .to_crs(CRS_UTM)
        .clip(gdf_region)
    )
    gdf_ccs["SITE"] = gdf_ccs["SITE"].astype(str)
    gdf_ccs = gdf_ccs[~gdf_ccs["SITE"].isin(DROP_SITES)].reset_index(drop=True)
    return gdf_ccs


def load_filtered_links() -> gpd.GeoDataFrame:
    """Network links with centroid connectors (FT 1), ramps (FT 28/29/41/42),
    and HOV links (STREET contains "HOV") removed."""
    gdf_links = gpd.read_file(LINK_SHP).to_crs(CRS_UTM)
    is_centroid_connector = gdf_links["FT"] == 1
    is_ramp = gdf_links["FT"].isin([28, 29, 41, 42])
    is_hov = gdf_links["STREET"].str.contains("HOV", case=False, na=False)
    return gdf_links[~is_centroid_connector & ~is_ramp & ~is_hov].reset_index(drop=True)


def match_stations_to_links(gdf_ccs: gpd.GeoDataFrame, gdf_links: gpd.GeoDataFrame) -> pd.DataFrame:
    """Nearest-link match by geometry -- the link shapefile has no clean
    route/milepost field to match on (unlike the HPMS segment shapefile), so
    this uses straight-line nearest distance instead."""
    matches = []
    for _, row in gdf_ccs.iterrows():
        nearest_idx = gdf_links.distance(row.geometry).idxmin()
        link = gdf_links.loc[nearest_idx]
        matches.append(
            {
                "SITE": row["SITE"],
                "SITE_DESCRIPTION": row.get("SITE_DESCRIPTION"),
                "LINK_STREET": link["STREET"],
                "LINKID": link["LINKID"],
                "LINK_FT": link["FT"],
                "LINK_FTCLASS": link["FTCLASS"],
                "LANES": link["LANES"],
                "CAP1HR1LN": link["CAP1HR1LN"],
                "DIST_M": row.geometry.distance(link.geometry),
            }
        )
    return pd.DataFrame(matches)


def flag_mountainous_stations(gdf_ccs: gpd.GeoDataFrame) -> pd.DataFrame:
    """Flags each station as inside a mountainous (MARGINAL=1) TAZ zone."""
    taz = gpd.read_file(TAZ_SHP)[["TAZID", "MARGINAL", "geometry"]]
    marginal_taz = taz[taz["MARGINAL"] == 1]
    joined = gpd.sjoin(gdf_ccs[["SITE", "geometry"]], marginal_taz, how="left", predicate="within")
    joined["IS_MARGINAL"] = joined["TAZID"].notna()
    return joined[["SITE", "IS_MARGINAL"]].drop_duplicates(subset="SITE")


def max_hourly_volume_by_station(sites: list[str]) -> pd.DataFrame:
    """Max volume in one lane, one direction, within the calibration window,
    per station -- from the raw hourly-by-lane workbooks."""
    results = []
    for workbook in CCS_LANE_WORKBOOKS:
        all_sheets = gpd_safe_read_excel_sheet_names(workbook)
        sheet_to_site = {s.lstrip("-").zfill(4): s for s in sites if s.lstrip("-").zfill(4) in all_sheets}
        if not sheet_to_site:
            continue
        loaded = pd.read_excel(workbook, sheet_name=list(sheet_to_site.keys()))
        for sheet, site in sheet_to_site.items():
            df = loaded[sheet].copy()
            df["DATE"] = pd.to_datetime(df["DATE"])
            mask_date = (df["DATE"] >= CALIB_WINDOW_START) & (df["DATE"] <= CALIB_WINDOW_END)
            mask_weekday = df["DATE"].dt.weekday.isin(CALIB_WEEKDAYS)
            df_window = df[mask_date & mask_weekday]
            if df_window.empty:
                results.append({"SITE": site, "MAX_HOURLY_VOL": None, "LANE": None, "DIRECTION": None, "DATE": None, "HOUR": None})
                continue
            long = df_window.melt(id_vars=["STATION", "DATE", "ROUTE", "MP", "LANE"], value_vars=HOUR_COLS, var_name="HOUR", value_name="VOL")
            best = long.loc[long["VOL"].idxmax()]
            results.append(
                {
                    "SITE": site,
                    "MAX_HOURLY_VOL": best["VOL"],
                    "LANE": best["LANE"],
                    "DIRECTION": "N" if best["LANE"][0] == "N" else "P",
                    "DATE": best["DATE"].strftime("%Y-%m-%d"),
                    "HOUR": best["HOUR"],
                }
            )
    return pd.DataFrame(results)


def gpd_safe_read_excel_sheet_names(workbook: Path) -> list[str]:
    import openpyxl

    wb = openpyxl.load_workbook(workbook, read_only=True)
    try:
        return wb.sheetnames
    finally:
        wb.close()


def spdcap_lookup_table() -> pd.DataFrame:
    lut = pd.read_csv(SPDCAP_LOOKUP)
    lut.columns = [c.lstrip(";") for c in lut.columns]
    return lut


def build_final_table() -> pd.DataFrame:
    gdf_ccs = load_ccs_site_locations()
    gdf_links = load_filtered_links()

    link_match = match_stations_to_links(gdf_ccs, gdf_links)
    marginal_flag = flag_mountainous_stations(gdf_ccs)
    volumes = max_hourly_volume_by_station(gdf_ccs["SITE"].tolist())

    df = link_match.merge(marginal_flag, on="SITE", how="left").merge(volumes, on="SITE", how="left")
    df["PCT_OF_CAP"] = (df["MAX_HOURLY_VOL"] / df["CAP1HR1LN"] * 100).round(0)
    return df


def apply_exclusions(df: pd.DataFrame) -> pd.DataFrame:
    excluded = OUTLIER_STATIONS + BANGERTER_EXPRESSWAY_STATIONS
    out = df[~df["SITE"].isin(excluded) & ~df["IS_MARGINAL"].fillna(False)].copy()
    return out.sort_values(["LINK_FT", "SITE"]).reset_index(drop=True)


def ft_summary(df: pd.DataFrame) -> pd.DataFrame:
    lut = spdcap_lookup_table()
    cap_cols = [c for c in lut.columns if c.startswith("CAPLN")]
    lut_slim = lut[["FT"] + cap_cols]

    grp = df.groupby(["LINK_FT", "LINK_FTCLASS"]).agg(
        n_stations=("SITE", "count"),
        n_with_volume=("MAX_HOURLY_VOL", lambda s: s.notna().sum()),
        max_of_max=("MAX_HOURLY_VOL", "max"),
        avg_of_max=("MAX_HOURLY_VOL", "mean"),
    ).reset_index()
    grp["avg_of_max"] = grp["avg_of_max"].round(0)
    return grp.merge(lut_slim, left_on="LINK_FT", right_on="FT", how="left").drop(columns=["FT"])


def lane_breakdown_for_ft(df: pd.DataFrame, ft: int) -> pd.DataFrame:
    """Same max/avg-of-max breakdown as ft_summary(), but split out by lane
    count within one FT -- useful for seeing whether the model's
    lane-count-dependent capacity actually tracks observed volume by lane."""
    lut = spdcap_lookup_table()
    cap_row = lut[lut["FT"] == ft].iloc[0]

    subset = df[df["LINK_FT"] == ft]
    grp = subset.groupby("LANES").agg(
        n_stations=("SITE", "count"),
        n_with_volume=("MAX_HOURLY_VOL", lambda s: s.notna().sum()),
        max_of_max=("MAX_HOURLY_VOL", "max"),
        avg_of_max=("MAX_HOURLY_VOL", "mean"),
    ).reset_index()
    grp["avg_of_max"] = grp["avg_of_max"].round(0)
    grp["model_cap_per_lane"] = grp["LANES"].apply(lambda lanes: cap_row[f"CAPLN{min(int(lanes), 7)}"])
    grp["pct_of_cap_at_max"] = (grp["max_of_max"] / grp["model_cap_per_lane"] * 100).round(0)
    grp["pct_of_cap_at_avg"] = (grp["avg_of_max"] / grp["model_cap_per_lane"] * 100).round(0)
    return grp


def main():
    OUT_DIR.mkdir(exist_ok=True)

    raw = build_final_table()
    raw.to_csv(OUT_DIR / "ccs_station_link_capacity_raw.csv", index=False)

    final = apply_exclusions(raw)
    final.to_csv(OUT_DIR / "ccs_station_link_capacity_final.csv", index=False)

    summary = ft_summary(final)
    summary.to_csv(OUT_DIR / "ft_summary.csv", index=False)

    arterial_by_lane = lane_breakdown_for_ft(final, ft=2)
    arterial_by_lane.to_csv(OUT_DIR / "ft2_principal_arterial_by_lane.csv", index=False)

    print(f"{len(raw)} CCS stations matched, {len(final)} remaining after exclusions")
    print()
    print(summary.to_string(index=False))
    print()
    print("FT 2 (Principal Arterial) by lane count:")
    print(arterial_by_lane.to_string(index=False))


if __name__ == "__main__":
    main()
