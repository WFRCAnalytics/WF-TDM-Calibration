"""
CLI: builds runs/{calib_run_id}/cache/*.parquet for one calibration run, by
calling each migrated stage module's extracted loader(s) against that run's
curated outputs/. Invoked automatically by tdmcalib (see
src/tdmcalib/postprocess.py's build_report_cache(), shelled out to from
execution.py right after a run's outputs are curated, before the report
re-renders -- see report/README.md's "Report data caching" section).

Also runnable by hand from the repo root, e.g. while iterating on a report
locally without a full `tdmcalib run`:

    python -m report.preprocess.build_cache --run C50
"""

import argparse
import sys
from pathlib import Path

from report import _validation_scripts as vs
from report.preprocess import assignhwy, distribution, hhdisag, modechoice, modelresults, tripgen

# name -> loader(calib_run, outputs_dir, repo_root) -> DataFrame. Extend as
# more stages migrate off inline per-run loading (see report/README.md).
LOADERS = {
    "hhdisag": hhdisag.load_hhdisag,
    "vehown": hhdisag.load_vehown,
    "modeled_tripgen": tripgen.load_modeled_tripgen,
    "modeled_cvtripgen": tripgen.load_modeled_cvtripgen,
    "tdm_agg": modechoice.load_tdm_agg,
    "boardings": modechoice.load_boardings,
    "mod_boarding": modechoice.load_mod_boarding,
    "crt_dist": modechoice.load_crt_dist,
    "crt_model": modelresults.load_crt_model,
    "dist_gc_avg": distribution.load_dist_gc_avg,
    "dist_gc_tlf": distribution.load_dist_gc_tlf,
    "mod_intra": distribution.load_mod_intra,
    "master_trips": distribution.load_master_trips,
    "dist_sum_mod": distribution.load_dist_sum_mod,
    "mod_dist_hbw_sum": distribution.load_mod_dist_hbw_sum,
    "mod_distrib_hbw_sum": distribution.load_mod_distrib_hbw_sum,
    "mod_tidy": assignhwy.load_mod_tidy,
    "ccs_model_vol": assignhwy.load_ccs_model_vol,
    "sfac_cfac": assignhwy.load_sfac_cfac,
    "seg_detail": assignhwy.load_seg_detail,
    "xx": assignhwy.load_xx,
}

# name -> loader(repo_root) -> DataFrame. Calib_run-INdependent -- built once
# per build_global() call (below), not per run, and shared by every
# calibration run's report instead of frozen into one run's own cache (see
# report/preprocess/assignhwy.py's load_ccs_base()).
GLOBAL_LOADERS = {
    "ccs_base": assignhwy.load_ccs_base,
}


def build(repo_root: Path, calib_run_id: str) -> dict:
    """Builds every registered cache dataset for one calibration run, plus
    the shared/global datasets (build_global()) -- rebuilding the global
    side on every call, regardless of which run was asked for, is what lets
    editing a shared input (e.g. CCS station data) take effect everywhere
    without rebuilding every other run's own cache. Returns {name: "ok" or
    an error string} -- never raises for an individual dataset's failure,
    so one bad/changed dataset doesn't stop the others from building."""
    outputs_dir = vs.resolve_latest_run_outputs(repo_root, calib_run_id)
    cache_dir = repo_root / "runs" / calib_run_id / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    results = build_global(repo_root)
    for name, load_fn in LOADERS.items():
        try:
            df = load_fn(calib_run_id, outputs_dir, repo_root)
            df.to_parquet(cache_dir / f"{name}.parquet", index=False)
            results[name] = "ok"
        except Exception as e:  # noqa: BLE001 -- one dataset's failure shouldn't stop the rest
            results[name] = f"failed: {e}"
    return results


def build_global(repo_root: Path) -> dict:
    """Builds every registered calib_run-independent cache dataset
    (GLOBAL_LOADERS) once, shared by every calibration run's report. See
    build()'s docstring for why this runs on every build() call rather than
    needing its own separate trigger."""
    cache_dir = repo_root / "runs" / "_global" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for name, load_fn in GLOBAL_LOADERS.items():
        try:
            df = load_fn(repo_root)
            df.to_parquet(cache_dir / f"{name}.parquet", index=False)
            results[name] = "ok"
        except Exception as e:  # noqa: BLE001 -- one dataset's failure shouldn't stop the rest
            results[name] = f"failed: {e}"
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="Calibration run ID (e.g. C50)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    results = build(repo_root, args.run)

    had_error = False
    for name, status in results.items():
        marker = "OK  " if status == "ok" else "FAIL"
        print(f"[{marker}] {name}: {status}")
        if status != "ok":
            had_error = True
    sys.exit(1 if had_error else 0)


if __name__ == "__main__":
    main()
