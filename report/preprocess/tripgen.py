"""Trip Generation stage preprocessing -- extracted from report/1-tripgen.qmd
so the expensive per-run parsing (pa_final.csv, SE_File.dbf) happens once
per tdmcalib run/import, not on every `quarto render`. See
report/preprocess/build_cache.py and report/README.md."""

from pathlib import Path

import numpy as np
import openmatrix as omx
import pandas as pd
from dbfread import DBF

TAZ_DBF = Path("data/0-hhdisag-autoown/WFv1000_TAZ.dbf")
CV_MATS = ["II_LT", "II_MD", "II_HV"]


def _iter_omx_sources(omx_path: Path):
    """Yields every physical OMX file backing omx_path -- normally just
    omx_path itself, but tdmcalib's output curation splits an oversized
    multi-tab matrix into one file per tab instead (see
    src/tdmcalib/outputs.py's _split_omx_by_tab()), named
    "<stem>__<tab>.omx" and left as siblings of where the combined file
    would have been. Raises if neither the combined file nor any split
    sibling exists, so a genuinely missing output still fails loudly. Same
    helper as report/preprocess/distribution.py's -- duplicated rather than
    shared, matching this package's per-module convention (see this
    module's own docstring)."""
    if omx_path.exists():
        yield omx_path
        return
    split_paths = sorted(omx_path.parent.glob(f"{omx_path.stem}__*{omx_path.suffix}"))
    if not split_paths:
        raise FileNotFoundError(
            f"{omx_path} not found (and no split '{omx_path.stem}__*{omx_path.suffix}' siblings either)"
        )
    yield from split_paths


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


def load_modeled_cvtripgen(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Daily commercial-vehicle trips (production end) by county and vehicle
    type (LT/MD/HV) -- both the raw total and a rate per job (TOTEMP, from
    SE_File.dbf -- CV trip generation is employment-driven, unlike person
    trip generation's household/population rates) -- plus a 'Region' total
    row (CO_FIPS left as None, same convention as load_modeled_tripgen), for
    one calibration run.

    Unlike person trip generation, there's no independent household-survey
    equivalent for commercial vehicles (see cvm-update.qmd's own "About the
    LOCUS Data" note and report/2-distribution.qmd's trip-length-frequency
    note) -- so this is a plain model summary, not a Model-vs-Target
    comparison."""
    taz_df = pd.DataFrame(DBF(repo_root / "report" / TAZ_DBF, load=True))[["TAZID", "CO_FIPS"]]
    taz_ids = np.arange(1, 3630)

    se_df = pd.DataFrame(DBF(outputs_dir / "SE_File.dbf", load=True))[["Z", "TOTEMP"]].rename(columns={"Z": "TAZID"})
    emp_county_df = (
        se_df.merge(taz_df, on="TAZID")
        .groupby("CO_FIPS", as_index=False)
        .agg(TOTEMP=("TOTEMP", "sum"))
    )
    emp_region_row = pd.DataFrame([{"CO_FIPS": None, "TOTEMP": emp_county_df["TOTEMP"].sum()}])
    emp_with_region = pd.concat([emp_county_df, emp_region_row], ignore_index=True)
    emp_with_region["CO_FIPS"] = emp_with_region["CO_FIPS"].astype("Int64")

    records = []
    for path in _iter_omx_sources(outputs_dir / "PA_AllPurp_GRAVITY.omx"):
        with omx.open_file(path, "r") as f:
            matrix_lookup = {mat.upper(): mat for mat in f.list_matrices()}
            for mat_name in CV_MATS:
                actual_mat_name = matrix_lookup.get(mat_name.upper())
                if actual_mat_name is None:
                    continue
                mat = np.array(f[actual_mat_name]).astype(float)
                records.append(pd.DataFrame({
                    "TAZID": taz_ids,
                    "Trips": mat.sum(axis=1),  # production-end total
                    "Vehicle Type": mat_name.removeprefix("II_"),
                }))

    mod_cv_df = pd.concat(records, ignore_index=True)
    mod_cv_county_df = (
        mod_cv_df.merge(taz_df, on="TAZID")
        .groupby(["CO_FIPS", "Vehicle Type"], as_index=False)
        .agg(Trips=("Trips", "sum"))
    )

    # add total row for all counties (region) -- CO_FIPS=None marks it, same
    # convention as load_modeled_tripgen
    totals_by_veh = mod_cv_county_df.groupby(["Vehicle Type"], as_index=False)["Trips"].sum()
    totals_by_veh["CO_FIPS"] = None
    mod_cv_county_reg_df = pd.concat([mod_cv_county_df, totals_by_veh], ignore_index=True)
    mod_cv_county_reg_df["CO_FIPS"] = mod_cv_county_reg_df["CO_FIPS"].astype("Int64")

    mod_cv_county_reg_df = mod_cv_county_reg_df.merge(emp_with_region, on="CO_FIPS", how="left")
    mod_cv_county_reg_df["Trips per Job"] = mod_cv_county_reg_df["Trips"] / mod_cv_county_reg_df["TOTEMP"]

    return mod_cv_county_reg_df.drop(columns=["TOTEMP"])
