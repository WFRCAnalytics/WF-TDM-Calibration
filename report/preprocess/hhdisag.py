"""Household Disaggregation & Vehicle Ownership stage preprocessing --
extracted from report/0-hhdisag-autoown.qmd so the expensive per-run
parsing (Joint_HHSize_Income_Worker.dbf, VO_HHSize_VehOwn.dbf) happens once
per tdmcalib run/import, not on every `quarto render`. See
report/preprocess/build_cache.py and report/README.md."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from dbfread import DBF

TAZ_SHP = Path("data/4-assignhwy/taz/WFv1000_TAZ.shp")
PROJECT_CRS = "EPSG:26912"

_GEO_COLS = [
    "TAZID",
    "DISTSUPER", "DSUP_NAME",
    "DISTLRG", "DLRG_NAME",
    "DISTMED", "DMED_NAME",
    "DISTSML", "DSML_NAME",
]


def load_hhdisag(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Household counts by TAZ x household size x income x workers, for one
    calibration run. Pure function of outputs_dir -- no shared/reference
    data needed."""
    hhdis_df = pd.DataFrame(DBF(outputs_dir / "Joint_HHSize_Income_Worker.dbf", load=True))

    value_vars = [col for col in hhdis_df.columns if col.startswith("S") and col[1].isdigit()]
    id_vars = ["Z", "CO_FIPS"]

    df = hhdis_df.melt(
        id_vars=id_vars, value_vars=value_vars, var_name="Variable", value_name="COUNT"
    )
    df["HHSIZE"] = df["Variable"].str[1].astype(int)
    df["INC"] = (
        df["Variable"]
        .str[3]
        .map({"1": "<$50k", "2": "$50k–$100k", "3": "$100k–$150k", "4": ">$150k"})
    )
    df["WRKS"] = df["Variable"].str[5]
    return df[["Z", "CO_FIPS", "HHSIZE", "INC", "WRKS", "COUNT"]]


def load_vehown(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Household counts by TAZ x household size x vehicle ownership, joined
    to TAZ geography columns (no geometry -- _GEO_COLS is attribute columns
    only, so this stays a plain, parquet-cacheable DataFrame), for one
    calibration run."""
    taz_shp = gpd.read_file(repo_root / "report" / TAZ_SHP).to_crs(PROJECT_CRS)
    taz_shp["TAZID"] = taz_shp["TAZID"].astype(int)

    df_mod_vehown = pd.DataFrame(
        DBF(outputs_dir / "VO_HHSize_VehOwn.dbf", load=True, encoding="utf-8")
    )
    df_mod_vehown["Z"] = df_mod_vehown["Z"].astype(int)

    sv_cols = [col for col in df_mod_vehown.columns if col.startswith("S") and "V" in col]
    df_subset = df_mod_vehown[["Z"] + sv_cols]

    df_melted = df_subset.melt(id_vars="Z", var_name="Category", value_name="Households")

    df_melted["HHSize_Num"] = df_melted["Category"].str.extract(r"S(\d+)")[0].astype(int)
    df_melted["VehOwn_Num"] = df_melted["Category"].str.extract(r"V(\d+)")[0].astype(int)

    df_melted["HHSize"] = np.where(
        df_melted["HHSize_Num"] >= 4, "4+", df_melted["HHSize_Num"].astype(str)
    )
    df_melted["VehOwn"] = np.where(
        df_melted["VehOwn_Num"] >= 3, "3+", df_melted["VehOwn_Num"].astype(str)
    )

    df_mod_long = df_melted.groupby(["Z", "HHSize", "VehOwn"])["Households"].sum().reset_index()
    df_mod_long = df_mod_long.rename(columns={"Z": "TAZID"})

    return df_mod_long.merge(taz_shp[_GEO_COLS], on="TAZID", how="left")
