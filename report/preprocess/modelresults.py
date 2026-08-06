"""Compare Model Results stage preprocessing -- extracted from
report/7-modelresults.qmd so the expensive per-run parsing
(transit_rider_summary_link.csv) happens once per tdmcalib run/import, not
on every `quarto render`. See report/preprocess/build_cache.py and
report/README.md."""

from pathlib import Path

import pandas as pd

from report import _validation_scripts as vs

# FrontRunner stops (northbound direction) -- static reference data, not
# run-specific. Duplicated from report/7-modelresults.qmd's df_station_master
# (also used there for the observed side, which stays inline).
_STATION_NODES = [
    50024, 50029, 50030, 50035, 50040,
    10008, 10010, 10016, 10019, 10021, 10025, 10031, 10035, 10036, 10042, 10046,
]
_UTA_STOPS = [
    "Provo Central Station", "Orem Central Station", "Vineyard Station",
    "American Fork Station", "Lehi Station", "Draper Station",
    "South Jordan Station", "Murray Central Station", "Salt Lake Central Station",
    "North Temple Station", "Woods Cross Station", "Farmington Station",
    "Layton Station", "Clearfield Station", "Roy Station", "Ogden Central Station",
]
_NODE_MAP = dict(zip(_STATION_NODES, _UTA_STOPS))


def load_crt_model(calib_run: str, outputs_dir: Path, repo_root: Path) -> pd.DataFrame:
    """CRT (commuter rail) access mode/distance/time by station, for one
    calibration run."""
    in_rider_summary = vs.find_one(outputs_dir, "*transit_rider_summary_link.csv")
    df_rider_summary = pd.read_csv(in_rider_summary).query(
        "Mode.isin([11, 12, 80]) and A < 10000 and B in @_STATION_NODES"
    )

    df_model_plot = (
        df_rider_summary.assign(Stop_Name=lambda x: x["B"].map(_NODE_MAP))
        .query("FromSkim_CRT > 0")
        .dropna(subset=["Stop_Name"])
        .rename(
            columns={
                "Distance": "access_dist",
                "Time": "access_time",
                "FromSkim_CRT": "boarding_weight",
                "AccessMode": "Ac_Mode2_Model",
            }
        )
        .assign(
            Ac_Mode2_Model=lambda x: x["Ac_Mode2_Model"].str.title(),
            access_dist=lambda x: pd.to_numeric(x["access_dist"], errors="coerce"),
            access_time=lambda x: pd.to_numeric(x["access_time"], errors="coerce"),
            # If your data is x100 (e.g. 1500 = 15 trips), uncomment the line below:
            # boarding_weight = lambda x: x['boarding_weight'] / 100
        )
    )
    return df_model_plot[
        ["Stop_Name", "access_dist", "access_time", "boarding_weight", "Ac_Mode2_Model"]
    ]
