import glob
import json
from pathlib import Path

import numpy as np


def resolve_latest_run_outputs(repo_root: Path, calib_run: str) -> Path:
    """Finds this calibration run's curated outputs/ dir
    (runs/{calib_run}/outputs/) -- mirrors
    tdmcalib.metadata.latest_successful_run() without importing the package,
    since these reports may be rendered in an environment that doesn't have
    it installed (e.g. the "reports" Jupyter kernel vs. the "dev" venv).
    Only the latest attempt is ever kept on disk for a calib_run_id, so a
    failed re-run makes this raise even if an earlier attempt once
    succeeded."""
    calib_run_dir = repo_root / "runs" / calib_run
    metadata_path = calib_run_dir / "run_metadata.json"
    if metadata_path.is_file():
        with open(metadata_path) as f:
            metadata = json.load(f)
        if metadata.get("status") == "success":
            return calib_run_dir / "outputs"
    raise FileNotFoundError(
        f"No successful tdmcalib run found under {calib_run_dir} -- "
        f"run `tdmcalib run --run {calib_run}` (or import-manual-run) first."
    )


def find_one(outputs_dir: Path, pattern: str) -> str:
    """Resolves a single curated output file matching a glob pattern inside
    outputs_dir -- for filenames that may or may not carry a Cube-generated
    `___{runId}___` prefix (see calibration_runs/*.yaml's outputs.include
    comments), depending on whether the run was executed through tdmcalib
    (prefix intact, since curation preserves the original filename) or
    imported from an archived source that was already de-prefixed. Callers
    pass a prefix-agnostic pattern (e.g. "*RegionShares_Pk.csv") so either
    case matches. Raises if zero or more than one file matches."""
    matches = sorted(outputs_dir.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No file matching '{pattern}' in {outputs_dir}")
    if len(matches) > 1:
        raise FileNotFoundError(f"Multiple files matching '{pattern}' in {outputs_dir}: {matches}")
    return str(matches[0])


def list_available_runs(repo_root: Path) -> list:
    """All calib_run_ids under runs/ that have at least one successful
    tdmcalib run, sorted. Reports are no longer one-per-calibration-run (see
    report/README.md) -- each stage report loads every available run's
    output at render time and lets an in-page OJS selector pick which one to
    view against observed data, so this is how each report's Python cell
    discovers what's available instead of reading a single config.json's
    calib_run."""
    runs_dir = repo_root / "runs"
    if not runs_dir.is_dir():
        return []
    available = []
    for calib_dir in sorted(runs_dir.iterdir()):
        if not calib_dir.is_dir():
            continue
        try:
            resolve_latest_run_outputs(repo_root, calib_dir.name)
            available.append(calib_dir.name)
        except FileNotFoundError:
            continue
    return available


def load_per_run(repo_root: Path, load_fn):
    """Calls load_fn(calib_run, outputs_dir) for every available calibration
    run (see list_available_runs()) and concatenates the results, each
    tagged with a 'calib_run' column, into one combined pandas DataFrame --
    the standard shape every report's modeled-side loader uses so an OJS
    selector can filter by calib_run client-side. load_fn should return a
    DataFrame (without a calib_run column; this adds it) or None to skip a
    run (e.g. a required file isn't in that run's outputs.include yet).
    Raises only if EVERY available run fails to load -- one run's missing
    file shouldn't blank out reports for every other run."""
    import pandas as pd

    frames = []
    errors = []
    for calib_run in list_available_runs(repo_root):
        outputs_dir = resolve_latest_run_outputs(repo_root, calib_run)
        try:
            df = load_fn(calib_run, outputs_dir)
        except Exception as e:  # noqa: BLE001 -- one run's bad/missing file shouldn't blank the report
            errors.append(f"{calib_run}: {e}")
            continue
        if df is None:
            continue
        df = df.copy()
        df["calib_run"] = calib_run
        frames.append(df)
    if not frames:
        detail = "; ".join(errors) if errors else "no calibration runs have output yet"
        raise FileNotFoundError(f"No calibration run could be loaded ({detail}).")
    return pd.concat(frames, ignore_index=True)


def load_cached_per_run(repo_root: Path, name: str):
    """Like load_per_run(), but reads pre-built per-run cache files
    (runs/{calib_run}/cache/{name}.parquet, written by
    report/preprocess/build_cache.py) instead of recomputing from raw
    outputs -- the expensive OMX/DBF/CSV parsing already happened once,
    when that run was curated (see tdmcalib's
    postprocess.build_report_cache()), not on every render. Tags each
    result with a 'calib_run' column and concatenates, same contract as
    load_per_run(). Raises if every available run's cache for `name` is
    missing -- run `python -m report.preprocess.build_cache --run <id>`
    (from the repo root) to (re)build it."""
    import pandas as pd

    frames = []
    missing = []
    for calib_run in list_available_runs(repo_root):
        cache_path = repo_root / "runs" / calib_run / "cache" / f"{name}.parquet"
        if not cache_path.is_file():
            missing.append(calib_run)
            continue
        df = pd.read_parquet(cache_path)
        df["calib_run"] = calib_run
        frames.append(df)
    if not frames:
        detail = f"missing for: {', '.join(missing)}" if missing else "no calibration runs have output yet"
        raise FileNotFoundError(
            f"No cached '{name}' dataset could be loaded ({detail}). Run "
            f"`python -m report.preprocess.build_cache --run <id>` (from the repo root) first."
        )
    return pd.concat(frames, ignore_index=True)


def plot_volume_diff(dfFiltered, varVehType, segShp):
    # Local imports: contextily/matplotlib are report-render-only
    # dependencies (the "reports" Jupyter kernel, not tdmcalib's own dev
    # venv) -- module-level imports here would make report/preprocess/'s
    # build_cache.py (which only needs this module's lightweight
    # run-discovery helpers, invoked from tdmcalib itself) require them too.
    import contextily as ctx
    import matplotlib.pyplot as plt

    dfFiltered["diff"] = round(dfFiltered["AWDT_Mod"] - dfFiltered["AWDT_Obs"], 1)

    dfShp = segShp.merge(dfFiltered, on="SEGID")

    conditions = [
        (dfShp["diff"].lt(-10000)),
        (dfShp["diff"].ge(-10000) & dfShp["diff"].lt(-3000)),
        (dfShp["diff"].ge(-3000) & dfShp["diff"].lt(-1000)),
        (dfShp["diff"].ge(-1000) & dfShp["diff"].lt(1000)),
        (dfShp["diff"].ge(1000) & dfShp["diff"].lt(3000)),
        (dfShp["diff"].ge(3000) & dfShp["diff"].le(10000)),
        (dfShp["diff"].gt(10000)),
    ]
    choices = [2.4, 2, 1.7, 1.7, 1.7, 2, 2.4]
    dfShp["lw"] = np.select(conditions, choices)
    dfShp["lwf"] = np.where(
        dfShp["FTCLASS"] == "Freeway", dfShp["lw"], dfShp["lw"] - 1.6
    )

    # Create the figure and axis
    fig, ax = plt.subplots(figsize=(6, 12), dpi=300)

    # Check and set CRS if necessary
    if dfShp.crs is None:
        # Assuming your original df is in EPSG:4326 (WGS84)
        dfShp.set_crs(epsg=26912, inplace=True)

    # Check if we need to reproject to Web Mercator
    if dfShp.crs.to_string() != "EPSG:3857":
        dfShp = dfShp.to_crs(epsg=3857)

    bin1 = [-15000, -7500, -2500, 0, 2500, 7500, 15000]
    bin2 = [-5000, -1500, -500, 0, 500, 1500, 5000]

    if varVehType == "All":
        bin = bin1
        titleName = "All Vehicles"
    elif varVehType == "PCLT":
        bin = bin2
        titleName = "Cars + Light CV"
    elif varVehType == "MD":
        bin = bin2
        titleName = "Medium CV"
    elif varVehType == "HV":
        bin = bin2
        titleName = "Heavy CV"
    else:
        bin = bin2
        titleName = varVehType

    # Plot your geospatial df
    dfShp.plot(
        column="diff",
        cmap="RdBu_r",
        scheme="userdefined",
        legend=True,
        classification_kwds=dict(bins=bin),
        linewidth=dfShp["lwf"],
        ax=ax,
        antialiased=True,
    )

    # Add basemap using contextily with OpenStreetMap
    ctx.add_basemap(ax, source=ctx.providers.CartoDB.PositronNoLabels, alpha=1)

    # Adjust the margins and axis
    ax.margins(0.1)
    ax.axis("off")

    # Adjust the x-axis limits to cut off the right side of the map
    xlim = ax.get_xlim()  # Get current x-axis limits
    cutoff_value = (
        xlim[1] - 65000
    )  # Define how much you want to cut off (adjust value as needed)
    ax.set_xlim(xlim[0], cutoff_value)  # Set new x-axis limits

    # Adjust legend size
    leg = ax.get_legend()  # Get the current legend
    leg.set_bbox_to_anchor((1, 1))  # Move the legend outside the plot area if necessary
    leg.set_title("Difference Scale", prop={"size": 12})  # Adjust the title size
    for text in leg.get_texts():
        text.set_fontsize(12)  # Adjust the size of the legend text

    # Set the title using the varVehType variable
    ax.set_title(f"Volume Diff.: {titleName}", loc="center", fontsize=14, pad=20)

    # Show the plot
    # plt.rcParams["figure.figsize"]=6,12
    plt.tight_layout()
    plt.savefig(
        f"_pictures/vol-diff-{varVehType}.png",
        dpi=300,
        bbox_inches="tight",
        pad_inches=0.05,
    )
    plt.close(fig)
