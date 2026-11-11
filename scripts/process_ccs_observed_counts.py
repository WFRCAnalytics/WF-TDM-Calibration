"""Converts raw UDOT CCS (Continuous Count Station) hourly-by-lane workbooks
into inputs/CCS_Observed_Counts_Raw.csv's row shape, and appends the result.

Source workbooks (e.g. "2023 Station 301-431.xlsx", "2024 Station 301-513.xlsx")
carry one sheet per station, each sheet one row per date x lane with hourly
columns H0000..H2300 plus a per-lane daily TOTAL -- see
report/4-assignhwy.qmd's "HOT Lane Validation" section, which reads these same
workbooks (via config_paths["ccs_lanes1"/"ccs_lanes2"]) for its own,
HOT-lane-only purpose. This script instead sums *every* lane (all directions)
for a station/date into one daily total, split into the same AM
(06:00-08:00) / MD (09:00-14:00) / PM (15:00-17:00) / EV (18:00-23:00 +
00:00-05:00) period buckets used throughout this report -- the exact
aggregation already used to build the existing 2023 rows in
inputs/CCS_Observed_Counts_Raw.csv (verified by reproducing station -302's
2023-01-02 row from "2023 Station 301-431.xlsx" byte-for-byte before writing
this script).

Appends (not replaces) inputs/CCS_Observed_Counts_Raw.csv -- a single,
growing, multi-year raw extract is simpler to keep in sync than one file per
year, and matches the "raw observed counts" framing already in its name. Run
again safely: de-dupes on (STATION, DATE_ONLY), keeping the newly-processed
version of any row that already existed.

A few stations have no 2023 coverage at all (e.g. -316) -- for those,
report/preprocess/assignhwy.py's _build_merged_base() picks a different
year's rows via inputs/ccs_year_overrides.csv, a separate, hand-maintained
file this script does not touch.

Usage (from repo root):
    python scripts/process_ccs_observed_counts.py "C:\\path\\to\\2024 Station 601-851.xlsx" "C:\\path\\to\\2024 Station 301-513.xlsx"
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

OUT_PATH = REPO_ROOT / "inputs" / "CCS_Observed_Counts_Raw.csv"

HOUR_COLS = [f"H{str(h).zfill(2)}00" for h in range(24)]
AM_COLS = [f"H{str(h).zfill(2)}00" for h in range(6, 9)]
MD_COLS = [f"H{str(h).zfill(2)}00" for h in range(9, 15)]
PM_COLS = [f"H{str(h).zfill(2)}00" for h in range(15, 18)]
EV_COLS = [f"H{str(h).zfill(2)}00" for h in list(range(0, 6)) + list(range(18, 24))]


def aggregate_workbook(path: Path) -> pd.DataFrame:
    """One row per STATION x DATE (every lane/direction summed), matching
    inputs/CCS_Observed_Counts_Raw.csv's columns."""
    all_sheets = pd.read_excel(path, sheet_name=None)
    all_sheets.pop("2023 CCS Hourly Volume Data", None)  # a non-data cover sheet some workbooks carry
    all_sheets.pop("2024 CCS Hourly Volume Data", None)
    df = pd.concat(all_sheets.values(), ignore_index=True)

    df["STATION"] = df["STATION"].astype(str)
    df["DATE"] = pd.to_datetime(df["DATE"])

    period_sums = df.groupby(["STATION", "DATE"])[HOUR_COLS].sum()
    out = pd.DataFrame({
        "STATION": [s for s, _ in period_sums.index],
        "DATE_ONLY": [d for _, d in period_sums.index],
        "AM_VOL": period_sums[AM_COLS].sum(axis=1).to_numpy(),
        "MD_VOL": period_sums[MD_COLS].sum(axis=1).to_numpy(),
        "PM_VOL": period_sums[PM_COLS].sum(axis=1).to_numpy(),
        "EV_VOL": period_sums[EV_COLS].sum(axis=1).to_numpy(),
    })
    out["TOTAL_VOL"] = out[["AM_VOL", "MD_VOL", "PM_VOL", "EV_VOL"]].sum(axis=1)
    out["DATE_ONLY"] = out["DATE_ONLY"].dt.strftime("%Y-%m-%d")
    for col in ["AM_VOL", "MD_VOL", "PM_VOL", "EV_VOL", "TOTAL_VOL"]:
        out[col] = out[col].round().astype(int)
    return out.sort_values(["STATION", "DATE_ONLY"]).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workbooks", nargs="+", type=Path, help="One or more raw 'Station xxx-xxx.xlsx' workbooks to process.")
    parser.add_argument("--out", type=Path, default=OUT_PATH, help=f"Defaults to {OUT_PATH.relative_to(REPO_ROOT)}.")
    parser.add_argument("--dry-run", action="store_true", help="Process and report row counts without writing the output file.")
    args = parser.parse_args()

    new_frames = []
    for wb in args.workbooks:
        print(f"Processing {wb} ...")
        df = aggregate_workbook(wb)
        print(f"  {df['STATION'].nunique()} station(s), {len(df)} station-day rows")
        new_frames.append(df)
    new_rows = pd.concat(new_frames, ignore_index=True)

    if args.out.exists():
        existing = pd.read_csv(args.out, dtype={"STATION": str})
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows
    before = len(combined)
    combined = combined.drop_duplicates(subset=["STATION", "DATE_ONLY"], keep="last")
    combined = combined.sort_values(["STATION", "DATE_ONLY"]).reset_index(drop=True)
    dupes_dropped = before - len(combined)

    print(f"Combined: {len(combined)} rows ({len(new_rows)} newly processed, {dupes_dropped} duplicate date(s) replaced)")
    if args.dry_run:
        print("(--dry-run: not writing)")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
