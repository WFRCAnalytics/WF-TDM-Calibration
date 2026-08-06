"""Trip Generation stage preprocessing -- extracted from report/1-tripgen.qmd
so the expensive per-run parsing (pa_final.csv, SE_File.dbf) happens once
per tdmcalib run/import, not on every `quarto render`. See
report/preprocess/build_cache.py and report/README.md."""

from pathlib import Path

import pandas as pd
from dbfread import DBF

TAZ_DBF = Path("data/0-hhdisag-autoown/WFv1000_TAZ.dbf")


def load_modeled_tripgen(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Trip-end productions by county x purpose, plus a 'Region' total row
    (CO_FIPS left as None on that row), for one calibration run. County
    *names* and the 'Data Source' label are deliberately left for
    report/1-tripgen.qmd to add after loading from cache -- keeps this
    preprocessing step free of the BigQuery dependency the qmd's
    counties_df otherwise needs (cheap, shared, non-run-specific reference
    data, out of scope for per-run caching -- see the plan's "what does not
    move" note)."""
    taz_df = pd.DataFrame(DBF(repo_root / "report" / TAZ_DBF, load=True))

    # from tdm 2_TripGen output
    mod_pa_wide_df = pd.read_csv(outputs_dir / "pa_final.csv")

    # from tdm 0_InputProcessing output
    mod_se_df = pd.DataFrame(DBF(outputs_dir / "SE_File.dbf", load=True))
    mod_se_df = mod_se_df[["Z", "TOTHH", "HHPOP"]].rename(columns={"Z": "TAZID"})
    mod_se_county_df = (
        mod_se_df.merge(taz_df[["TAZID", "CO_FIPS"]], on="TAZID")
        .groupby(["CO_FIPS"], as_index=False)
        .agg(TOTHH=("TOTHH", "sum"), HHPOP=("HHPOP", "sum"))
    )

    # calculate the total number of trip end productions for the modeled data
    mod_p_wide_df = mod_pa_wide_df.filter(regex="^(TAZID|.*_P)$").copy()
    mod_p_wide_df["HBSCH_P"] = mod_p_wide_df["HBSCHPR_P"] + mod_p_wide_df["HBSCHSC_P"]

    # filter to only columns to compare here, including removing college which is not part of trip gen
    mod_p_wide_df = mod_p_wide_df[
        ["TAZID", "HBW_P", "HBSHP_P", "HBOTH_P", "HBSCH_P", "NHBW_P", "NHBNW_P", "IX_P"]
    ]
    mod_p_wide_df = mod_p_wide_df.rename(columns=lambda x: x.rstrip("_P"))
    mod_p_wide_df = mod_p_wide_df.rename(columns={"HBSH": "HBShp", "HBOTH": "HBOth", "HBSCH": "HBSch"})

    # make the data long
    mod_p_df = mod_p_wide_df.melt(id_vars=["TAZID"], var_name="Purpose", value_name="Trips")

    # summarize by county
    mod_p_county_df = (
        mod_p_df.merge(taz_df[["TAZID", "CO_FIPS"]], on="TAZID")
        .groupby(["CO_FIPS", "Purpose"], as_index=False)
        .agg(Trips=("Trips", "sum"))
    )
    mod_p_se_county_df = mod_p_county_df.merge(mod_se_county_df, on="CO_FIPS")

    # add total row for all counties (region) -- CO_FIPS=None marks it, so
    # 1-tripgen.qmd's post-load county-name merge can turn it into 'Region'
    totals_by_year = (
        mod_p_se_county_df.groupby(["Purpose"], as_index=False)[["Trips", "TOTHH", "HHPOP"]].sum()
    )
    totals_by_year["CO_FIPS"] = None
    mod_p_se_county_reg_df = pd.concat([mod_p_se_county_df, totals_by_year], ignore_index=True)
    # pd.concat of an int column against an all-None column produces object
    # dtype (mixed Python ints and None), not a clean numeric column with
    # NaN -- normalize explicitly so the cached parquet (and the qmd's
    # post-load merge against counties_df, which BigQuery already returns
    # as nullable Int64) both get one consistent dtype.
    mod_p_se_county_reg_df["CO_FIPS"] = mod_p_se_county_reg_df["CO_FIPS"].astype("Int64")

    mod_p_se_county_reg_df["Trips per Person"] = (
        mod_p_se_county_reg_df["Trips"] / mod_p_se_county_reg_df["HHPOP"]
    )
    mod_p_se_county_reg_df["Trips per Household"] = (
        mod_p_se_county_reg_df["Trips"] / mod_p_se_county_reg_df["TOTHH"]
    )

    return mod_p_se_county_reg_df.drop(columns=["Trips", "TOTHH", "HHPOP"])
