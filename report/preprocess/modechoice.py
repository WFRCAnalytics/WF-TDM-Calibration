"""Mode Choice stage preprocessing -- extracted from report/3-modechoice.qmd
so the expensive per-run parsing (RegionShares_*.csv,
transit_brding_summary_node.csv, skim/trip OMX matrices) happens once per
tdmcalib run/import, not on every `quarto render`. See
report/preprocess/build_cache.py and report/README.md.

Two of the four loaders here (load_boardings, load_crt_dist) need the
observed on-board-survey data (df_obs/df_obs_agg) that report/3-modechoice.qmd
builds once, non-run-specific, in its own "PHASE 2" cells -- duplicated here
via _load_observed_data() rather than shared with the qmd directly, matching
every other stage's self-contained report/preprocess/ module. load_boardings
also needs load_tdm_agg()'s own output for the same run, so it calls that
function directly rather than re-deriving it -- the only cross-loader
dependency among this session's migrated stages so far.
"""

from pathlib import Path

import numpy as np
import openmatrix as omx
import pandas as pd

from report import _validation_scripts as vs

# ==============================================================================
# Static config (mirrors report/3-modechoice.qmd's own CONFIGURATION cell --
# duplicated, not imported, since it's only defined inline in the qmd; keep
# in sync if that cell changes).
# ==============================================================================

CONFIG_HIERARCHY = {
    "mnm": "Motorized / Non-Motorized",
    "at": "Auto / Transit",
    "dasr": "Drive Alone / Shared Ride",
    "occ": "Shared Ride # of Occupants",
    "transit": "Transit Mode",
    "access": "Transit Access Mode",
}

CONFIG_OUTPUT = {
    "period": "Period",
    "purpose": "TripPurpose",
    "mode_group": "ModeGroup",
    "mode_detail": "Mode",
    "trips_model": "TripsModel",
    "trips_obs": "TripsObserved",
    "share_model": "ShareModel",
    "share_obs": "ShareObserved",
    "diff": "Difference",
    "pct_diff": "% Difference",
}

_MODES = [
    (4, "LCL", "Local Bus"),
    (5, "COR", "Core Bus"),
    (6, "EXP", "Express Bus"),
    (7, "LRT", "LRT"),
    (8, "CRT", "CRT"),
    (9, "BRT", "BRT"),
    (1, "MT", "Microtransit"),
]
_MODE_MAP = {k: n for c, a, n in _MODES for k in (c, a)}

CONFIG_OBS = {
    "col_map": {
        "ID": "id",
        "Purp5_text": "purpose",
        "PK_OK": "period",
        "Veh_Cat3p": "veh_own",
        "Ac_Mode2_Model": "access_mode",
        "Linked_Mode_txt": "transit_mode",
        "Mode_Fin": "boarding_mode",
        "trip_weight": "weight",
        "boarding_weight": "weight_board",
    },
    "filters": "transit_mode != 'MT' and DATE_TYPE == 'Weekday'",
    "mode_map": _MODE_MAP,
}

CONFIG_TDM_MAP = {
    "2) Non-Motorized": ["Non-Motorized", "", "", "", "", ""],
    "4) Auto 1 pers": ["Motorized", "Auto", "Drive Alone", "", "", ""],
    "4) Auto 2 pers": ["Motorized", "Auto", "Shared Ride", "Shared Ride 2 Occupants", "", ""],
    "4) Auto 3+pers": ["Motorized", "Auto", "Shared Ride", "Shared Ride 3+ Occupants", "", ""],
    "3) Transit": ["Motorized", "Transit", "", "", "", ""],
    "LCL Walk": ["", "", "", "", "Local Bus", "Walk"],
    "LCL Drive": ["", "", "", "", "Local Bus", "Drive"],
    "COR Walk": ["", "", "", "", "Core Bus", "Walk"],
    "COR Drive": ["", "", "", "", "Core Bus", "Drive"],
    "BRT Walk": ["", "", "", "", "BRT", "Walk"],
    "BRT Drive": ["", "", "", "", "BRT", "Drive"],
    "EXP Walk": ["", "", "", "", "Express Bus", "Walk"],
    "EXP Drive": ["", "", "", "", "Express Bus", "Drive"],
    "LRT Walk": ["", "", "", "", "LRT", "Walk"],
    "LRT Drive": ["", "", "", "", "LRT", "Drive"],
    "CRT Walk": ["", "", "", "", "CRT", "Walk"],
    "CRT Drive": ["", "", "", "", "CRT", "Drive"],
}

HIER_COLS = list(CONFIG_HIERARCHY.values())

SKIM_COLS = [
    "Board_FromSkim_LCL",
    "Board_FromSkim_COR",
    "Board_FromSkim_EXP",
    "Board_FromSkim_BRT",
    "Board_FromSkim_LRT",
    "Board_FromSkim_CRT",
]

# Mode Label | Skim Code (Col) | Mode ID (Row)
VALIDATION_CONFIG = [
    ("Local Bus", "LCL", 4),
    ("Core Bus", "COR", 5),
    ("Express Bus", "EXP", 6),
    ("BRT", "BRT", 9),
    ("LRT", "LRT", 7),
    ("CRT", "CRT", 8),
]

_STATION_STOP_NAMES = [
    "Provo Central", "Orem Central", "Vineyard", "American Fork", "Lehi", "Draper",
    "South Jordan", "Murray Central", "Salt Lake Central", "North Temple",
    "Woods Cross", "Farmington", "Layton", "Clearfield", "Roy", "Ogden Central",
]
_STATION_MODEL_N = [
    50024, 50029, 50030, 50035, 50040,
    10008, 10010, 10016, 10019, 10021, 10025, 10031, 10035, 10036, 10042, 10046,
]
DF_STATION_MASTER = pd.DataFrame(
    {"Stop_Name": _STATION_STOP_NAMES, "Model_N": _STATION_MODEL_N}
)

OBS_CSV = Path("inputs/UTA_OBS_2024_Linked_FactorAdjusted.csv")


def _load_observed_data(repo_root: Path):
    """df_obs (trip-level, with the Microtransit->Local Bus boarding_mode
    reclassification already applied -- report/3-modechoice.qmd applies
    this in place, later, before its own loaders run, so it must be applied
    here too to match) and df_obs_agg (period x purpose x hierarchy
    summary). Not run-specific -- same for every calibration run."""
    df_obs = pd.read_csv(repo_root / OBS_CSV, low_memory=False)
    df_obs = df_obs.rename(columns=CONFIG_OBS["col_map"])
    df_obs = df_obs.query(CONFIG_OBS["filters"])

    df_obs["transit_mode"] = df_obs["transit_mode"].map(CONFIG_OBS["mode_map"])
    df_obs["boarding_mode"] = df_obs["boarding_mode"].map(CONFIG_OBS["mode_map"])
    df_obs["purpose"] = df_obs["purpose"].replace({"HBSch": "HBO"})
    df_obs.loc[df_obs["purpose"] == "HBC", "period"] = "PK"

    # Detail rows: specific transit mode, blank high-level columns
    df_obs_detail = df_obs.groupby(
        ["period", "purpose", "transit_mode", "access_mode"], as_index=False
    )["weight"].sum()
    df_obs_detail = df_obs_detail.rename(
        columns={
            "transit_mode": CONFIG_HIERARCHY["transit"],
            "access_mode": CONFIG_HIERARCHY["access"],
        }
    )
    for col in [
        CONFIG_HIERARCHY["mnm"], CONFIG_HIERARCHY["at"],
        CONFIG_HIERARCHY["dasr"], CONFIG_HIERARCHY["occ"],
    ]:
        df_obs_detail[col] = ""

    # Summary rows: high-level columns, blank transit mode
    df_obs_summary = df_obs.groupby(["period", "purpose"], as_index=False)["weight"].sum()
    df_obs_summary[CONFIG_HIERARCHY["mnm"]] = "Motorized"
    df_obs_summary[CONFIG_HIERARCHY["at"]] = "Transit"
    for col in [
        CONFIG_HIERARCHY["dasr"], CONFIG_HIERARCHY["occ"],
        CONFIG_HIERARCHY["transit"], CONFIG_HIERARCHY["access"],
    ]:
        df_obs_summary[col] = ""

    df_obs_agg = pd.concat([df_obs_detail, df_obs_summary], ignore_index=True)
    df_obs_agg = df_obs_agg.rename(columns={"weight": CONFIG_OUTPUT["trips_obs"]})

    # CRITICAL FIX (matches report/3-modechoice.qmd's PHASE 5 cell): treat
    # surveyed Microtransit (Mode 1) as "Local Bus" for boardings validation
    # only, applied to df_obs itself, after df_obs_agg is already built above
    # (df_obs_agg's own transit_mode values are untouched by this).
    df_obs["boarding_mode"] = df_obs["boarding_mode"].replace("Microtransit", "Local Bus")

    return df_obs, df_obs_agg


def load_tdm_agg(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Modeled trips by period x purpose x hierarchy, for one calibration
    run. Pure function of outputs_dir -- no shared/reference data needed
    (also called directly by load_boardings() for the same run, not just
    registered standalone in build_cache.py's LOADERS)."""
    tdm_dfs = []
    for period_key, period_label in [("RegionShares_Pk.csv", "PK"), ("RegionShares_Ok.csv", "OK")]:
        df_t = pd.read_csv(vs.find_one(outputs_dir, f"*{period_key}"))
        df_t["period"] = period_label
        tdm_dfs.append(df_t)

    df_tdm_raw = pd.concat(tdm_dfs)

    df_tdm_long = pd.melt(
        df_tdm_raw,
        id_vars=["period", "TripCategory"],
        value_vars=["HBCtrip", "HBOtrip", "HBWtrip", "NHBtrip"],
        var_name="purpose",
        value_name="trips",
    )
    df_tdm_long["purpose"] = df_tdm_long["purpose"].str.replace("trip", "")
    df_tdm_long["TripCategory"] = df_tdm_long["TripCategory"].str.strip()
    df_tdm_long["trips"] = pd.to_numeric(df_tdm_long["trips"], errors="coerce").fillna(0)

    df_tdm_long = df_tdm_long[df_tdm_long["TripCategory"].isin(CONFIG_TDM_MAP.keys())].copy()

    for i, col_name in enumerate(HIER_COLS):
        df_tdm_long[col_name] = df_tdm_long["TripCategory"].map(
            lambda x: CONFIG_TDM_MAP.get(x, [""] * 6)[i]
        )

    df_agg = df_tdm_long.groupby(["period", "purpose"] + HIER_COLS, as_index=False)["trips"].sum()
    return df_agg.rename(columns={"trips": CONFIG_OUTPUT["trips_model"]})


def load_boardings(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """Boardings/trips validation views (by hierarchical mode, by mode
    surveyed, transfer ratio), for one calibration run."""
    df_obs, df_obs_agg = _load_observed_data(repo_root)
    df_tdm_agg_run = load_tdm_agg(calib_run, outputs_dir, repo_root)

    df_tdm_brd_raw = pd.read_csv(vs.find_one(outputs_dir, "*transit_brding_summary_node.csv"))

    def get_tdm_hier_boardings(skim_code):
        target_col = f"Board_FromSkim_{skim_code}"
        if target_col in df_tdm_brd_raw.columns:
            return df_tdm_brd_raw[target_col].sum()
        return 0

    def get_tdm_surv_boardings(mode_id):
        subset = df_tdm_brd_raw[df_tdm_brd_raw["Mode"] == mode_id]
        return subset[SKIM_COLS].sum().sum()

    validation_rows = []
    for mode_label, skim_code, mode_id in VALIDATION_CONFIG:
        trips_mod = df_tdm_agg_run[df_tdm_agg_run[CONFIG_HIERARCHY["transit"]] == mode_label][
            CONFIG_OUTPUT["trips_model"]
        ].sum()
        trips_obs = df_obs_agg[df_obs_agg[CONFIG_HIERARCHY["transit"]] == mode_label][
            CONFIG_OUTPUT["trips_obs"]
        ].sum()
        brd_mod_hier = get_tdm_hier_boardings(skim_code)
        brd_obs_hier = df_obs[df_obs["transit_mode"] == mode_label]["weight_board"].sum()
        brd_mod_surv = get_tdm_surv_boardings(mode_id)
        brd_obs_surv = df_obs[df_obs["boarding_mode"] == mode_label]["weight_board"].sum()
        validation_rows.append(
            {
                "Mode": mode_label,
                "Trips_Mod": trips_mod,
                "Trips_Obs": trips_obs,
                "Board_Mod": brd_mod_hier,
                "Board_Obs": brd_obs_hier,
                "Board_Surv_Mod": brd_mod_surv,
                "Board_Surv_Obs": brd_obs_surv,
            }
        )

    df_val = pd.DataFrame(validation_rows)

    system_trips_obs = df_obs["weight"].sum()
    system_board_obs = df_obs["weight_board"].sum()
    system_board_mod = df_val["Board_Mod"].sum()
    total_row = {
        "Mode": "All",
        "Trips_Mod": df_val["Trips_Mod"].sum(),
        "Trips_Obs": system_trips_obs,
        "Board_Mod": system_board_mod,
        "Board_Obs": system_board_obs,
        "Board_Surv_Mod": system_board_mod,
        "Board_Surv_Obs": system_board_obs,
    }
    df_val = pd.concat([df_val, pd.DataFrame([total_row])], ignore_index=True)

    def make_view_df(title, col_mod, col_obs):
        df = df_val[["Mode", col_mod, col_obs]].copy()
        df.columns = ["Mode", "Model", "Observed"]
        df["Title"] = title
        df["Difference"] = df["Model"] - df["Observed"]
        df["% Difference"] = (df["Difference"] / df["Observed"]).fillna(0)
        return df

    df_v1 = make_view_df("Trips by Hierarchical Mode", "Trips_Mod", "Trips_Obs")
    df_v2 = make_view_df("Boardings by Hierarchical Mode", "Board_Mod", "Board_Obs")
    df_v3 = make_view_df("Boardings by Mode Surveyed", "Board_Surv_Mod", "Board_Surv_Obs")

    df_v4 = df_val[["Mode"]].copy()
    df_v4["Model"] = df_val["Board_Mod"] / df_val["Trips_Mod"].replace(0, np.nan)
    df_v4["Observed"] = df_val["Board_Obs"] / df_val["Trips_Obs"].replace(0, np.nan)
    df_v4["Title"] = "Transfer Ratio"
    df_v4["Difference"] = df_v4["Model"] - df_v4["Observed"]
    df_v4["% Difference"] = (df_v4["Difference"] / df_v4["Observed"]).fillna(0)

    return pd.concat([df_v1, df_v2, df_v3, df_v4], ignore_index=True)


def load_mod_boarding(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """CRT boardings/alightings by station (averaged), for one calibration
    run."""
    df = (
        pd.read_csv(vs.find_one(outputs_dir, "*transit_brding_summary_node.csv"))
        .query("Mode == 8")
        .groupby(["N", "AccessMode"])[["Board", "Alight"]]
        .sum()
        .mean(axis=1)
        .reset_index(name="Boardings")
    )
    df = df.merge(
        DF_STATION_MASTER[["Stop_Name", "Model_N"]], left_on="N", right_on="Model_N", how="left"
    )
    df["Access_Type"] = df["AccessMode"].str.title()
    df["Source"] = "Modeled"
    return df


def _load_skm(outputs_dir: Path, filename: str):
    with omx.open_file(outputs_dir / filename) as f:
        return np.array(f["D8"])


def _load_trips(outputs_dir: Path, filename: str, matrix: str):
    # values are trips x 100, so divide
    with omx.open_file(outputs_dir / filename) as f:
        return np.array(f[matrix]) / 100.0


def load_crt_dist(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """CRT trip distance frequency (modeled + observed, distance looked up
    from the modeled skim in both cases), for one calibration run."""
    df_obs, _df_obs_agg = _load_observed_data(repo_root)

    skm_w8_pk = _load_skm(outputs_dir, "skm_w8_Pk.omx")
    skm_w8_ok = _load_skm(outputs_dir, "skm_w8_Ok.omx")
    skm_d8_pk = _load_skm(outputs_dir, "skm_d8_Pk.omx")
    skm_d8_ok = _load_skm(outputs_dir, "skm_d8_Ok.omx")

    trp_w8_pk = _load_trips(outputs_dir, "AllTrips_Pk.omx", "wCRT")
    trp_w8_ok = _load_trips(outputs_dir, "AllTrips_Ok.omx", "wCRT")
    trp_d8_pk = _load_trips(outputs_dir, "AllTrips_Pk.omx", "dCRT")
    trp_d8_ok = _load_trips(outputs_dir, "AllTrips_Ok.omx", "dCRT")

    _model_chunks = []
    for trips, skm, period, access in [
        (trp_w8_pk, skm_w8_pk, "PK", "Walk"),
        (trp_w8_ok, skm_w8_ok, "OK", "Walk"),
        (trp_d8_pk, skm_d8_pk, "PK", "Drive"),
        (trp_d8_ok, skm_d8_ok, "OK", "Drive"),
    ]:
        mask = trips > 0
        _model_chunks.append(
            pd.DataFrame(
                {
                    "Distance": skm[mask],
                    "Trips": trips[mask],
                    "Period": period,
                    "AccessMode": access,
                    "Source": "Modeled",
                }
            )
        )
    df_crt_model = pd.concat(_model_chunks, ignore_index=True)

    df_crt_obs_raw = df_obs[df_obs["transit_mode"] == "CRT"].copy()

    _skim_map = {
        ("PK", "Walk"): skm_w8_pk,
        ("PK", "Drive"): skm_d8_pk,
        ("OK", "Walk"): skm_w8_ok,
        ("OK", "Drive"): skm_d8_ok,
    }

    _obs_chunks = []
    for (period, access), grp in df_crt_obs_raw.groupby(["period", "access_mode"]):
        skm = _skim_map.get((period, access))
        if skm is None:
            continue
        grp = grp.dropna(subset=["p_TAZID", "a_TAZID"])
        if grp.empty:
            continue
        r = grp["p_TAZID"].astype(int).values - 1
        c = grp["a_TAZID"].astype(int).values - 1
        valid = (r >= 0) & (r < skm.shape[0]) & (c >= 0) & (c < skm.shape[1])
        _obs_chunks.append(
            pd.DataFrame(
                {
                    "Distance": skm[r[valid], c[valid]],
                    "Trips": grp["weight"].values[valid],
                    "Period": period,
                    "AccessMode": access,
                    "Source": "Observed",
                }
            )
        )

    df_crt_obs = (
        pd.concat(_obs_chunks, ignore_index=True)
        if _obs_chunks
        else pd.DataFrame(columns=["Distance", "Trips", "Period", "AccessMode", "Source"])
    )

    df_all = (
        pd.concat([df_crt_model, df_crt_obs], ignore_index=True)
        .query("Distance > 0 and Distance < 200")  # guard against skim fill-values
    )
    # Raw skim/trip-matrix rows are one per non-zero OD cell (millions of
    # rows, most with near-zero trip weight) -- the chart only ever needs
    # total trips per distance value (client-side binning in 3-modechoice.qmd
    # sums Trips within each bucket), so collapse OD pairs sharing the same
    # rounded distance before this ever reaches ojs_define(). Non-lossy for
    # the chart, ~2000x smaller payload.
    df_all["Distance"] = df_all["Distance"].round(2)
    return (
        df_all.groupby(["Distance", "Period", "AccessMode", "Source"], as_index=False)["Trips"]
        .sum()
        .round({"Trips": 4})
    )
