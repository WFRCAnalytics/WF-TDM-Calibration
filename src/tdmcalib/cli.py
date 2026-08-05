"""Command-line interface. Run `tdmcalib --help` from anywhere inside the repo.

Ported from WF-TDM-Runs' src/tdmruns/cli.py. Commands lose their "-scenario"/
"-set" framing since there's no run_set/scenario nesting here -- each command
operates on one calibration run (--run C50) or all of them (run-all).
Retirement (snapshot-run-set/purge-run-set-outputs) is not ported in this
version -- calibration runs don't obviously need the same many-GB-then-purge
lifecycle a multi-scenario sensitivity study does; revisit once runs/
actually accumulates enough volume to matter."""

import sys
from pathlib import Path

import click

from tdmcalib import config as cfg
from tdmcalib import execution as ex
from tdmcalib import metadata as md
from tdmcalib import prep
from tdmcalib import submodule as sub
from tdmcalib.exceptions import tdmcalibError
from tdmcalib.paths import find_repo_root


@click.group()
@click.pass_context
def main(ctx):
    """TDM calibration run framework."""
    try:
        ctx.obj = {"repo_root": find_repo_root()}
    except tdmcalibError as e:
        click.echo(str(e), err=True)
        sys.exit(2)


@main.command("validate-config")
@click.option("--run", "calib_run_id", default=None, help="Validate only this calibration run.")
@click.pass_context
def validate_config(ctx, calib_run_id):
    """Validate calibration run configs against schema, and check every
    declared override key exists in its baseline Control Center file."""
    repo_root = ctx.obj["repo_root"]
    calib_run_ids = [calib_run_id] if calib_run_id else cfg.list_calibration_run_ids(repo_root)
    if not calib_run_ids:
        click.echo("No calibration runs found under calibration_runs/.")
        return
    framework = cfg.load_framework_config(repo_root)
    tdm_path = repo_root / framework["tdm_submodule_path"]
    had_error = False
    for crid in calib_run_ids:
        try:
            from tdmcalib import controlcenter as cc

            calib_run = cfg.load_calibration_run(repo_root, crid)
            baseline_filename = calib_run["baseline_control_center"]
            baseline = cc.load_baseline(
                tdm_path, framework["control_center_defaults_dir"], baseline_filename
            )
            cr_dir = repo_root / "calibration_runs"
            overrides = cfg.resolved_overrides(calib_run, cr_dir)
            cc.validate_overrides(baseline, overrides, f"calibration run '{crid}'.overrides")
            cfg.resolved_output_spec(framework, calib_run)
            click.echo(f"[OK]   {crid}")
        except tdmcalibError as e:
            click.echo(f"[FAIL] {crid}: {e}", err=True)
            had_error = True
    sys.exit(1 if had_error else 0)


@main.command("sync-tdm")
@click.option("--run", "calib_run_id", required=True)
def sync_tdm_cmd(calib_run_id):
    """Make the TDM submodule match the tag/branch/commit declared in the
    calibration run's tdm_ref -- a git checkout under the hood, so it
    mutates the submodule's working tree. Refuses on a dirty tree before and
    after checkout, same as a real run, but does not render a Control Center
    or execute the model."""
    repo_root = find_repo_root()
    try:
        framework = cfg.load_framework_config(repo_root)
        calib_run = cfg.load_calibration_run(repo_root, calib_run_id)
        ref = calib_run["tdm_ref"]
        tdm_path = repo_root / framework["tdm_submodule_path"]
        state = sub.resolve_version(repo_root, tdm_path, ref)
    except tdmcalibError as e:
        click.echo(f"[FAIL] {calib_run_id}: {e}", err=True)
        sys.exit(1)
    click.echo(f"[OK] {calib_run_id}: TDM synced to '{ref}'")
    for k, v in state.as_dict().items():
        click.echo(f"  {k}: {v}")


@main.command("run")
@click.option("--run", "calib_run_id", required=True)
@click.option("--force", is_flag=True, help="Run even if a successful run already exists.")
def run_cmd(calib_run_id, force):
    """Run a single calibration run end to end."""
    repo_root = find_repo_root()
    try:
        result = ex.run(repo_root, calib_run_id, force=force)
    except tdmcalibError as e:
        click.echo(f"[FAIL] {calib_run_id}: {e}", err=True)
        sys.exit(1)
    click.echo(f"[{result['status'].upper()}] {calib_run_id} run {result['run_id']}")
    if result["status"] != "success":
        click.echo(f"  {result.get('error')}", err=True)
        sys.exit(1)


@main.command("run-all")
@click.option("--only", "only", default=None, help="Comma-separated calibration run IDs to run.")
@click.option(
    "--force", is_flag=True, help="Re-run even if a successful run already exists."
)
def run_all_cmd(only, force):
    """Run every calibration run declared under calibration_runs/
    sequentially. A failed run does not stop the rest."""
    repo_root = find_repo_root()
    only_list = only.split(",") if only else None
    results = ex.run_all(repo_root, only=only_list, force=force)
    n_ok = sum(1 for r in results if r["status"] == "success")
    n_fail = sum(1 for r in results if r["status"] != "success")
    for r in results:
        click.echo(f"[{r['status'].upper():7s}] {r['calib_run_id']}  run={r.get('run_id')}")
    click.echo(f"\n{n_ok} succeeded, {n_fail} failed.")
    sys.exit(1 if n_fail else 0)


@main.command("import-manual-run")
@click.option("--run", "calib_run_id", required=True)
@click.option(
    "--scenario-folder", "scenario_folder",
    default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help=(
        "Raw output folder from a run outside the CLI (e.g. Cube Voyager invoked "
        "directly). Defaults to the calibration run's manual_scenario_folder in its "
        "YAML, or, if undeclared, Scenarios/<calib-run-id> (the same convention "
        "CLI-driven runs use)."
    ),
)
@click.pass_context
def import_manual_run_cmd(ctx, calib_run_id, scenario_folder):
    """Curate outputs for a calibration run that was run manually, outside
    `run`/`run-all`. Applies the run's outputs.include glob selection and
    size ceiling exactly as a CLI-driven run would, copies the result into
    runs/<calib-run-id>/<run-id>/outputs/, and records run_metadata.json
    with execution_mode "manual". Does not touch the TDM submodule. Always
    creates a new timestamped run."""
    repo_root = ctx.obj["repo_root"]
    try:
        result = ex.import_manual_run(repo_root, calib_run_id, scenario_folder)
    except tdmcalibError as e:
        click.echo(f"[FAIL] {calib_run_id}: {e}", err=True)
        sys.exit(1)
    click.echo(f"[{result['status'].upper()}] {calib_run_id} run {result['run_id']} (manual)")
    n_curated = len(result["outputs"]["curated"])
    click.echo(f"  {n_curated} file(s) curated to runs/{calib_run_id}/{result['run_id']}/outputs/")
    if result["status"] != "success":
        click.echo(f"  {result.get('error')}", err=True)
        sys.exit(1)


@main.command("import-manual-run-all")
@click.option("--only", "only", default=None, help="Comma-separated calibration run IDs to import.")
def import_manual_run_all_cmd(only):
    """Curate outputs for every calibration run that was run manually, using
    each run's declared manual_scenario_folder, or, if undeclared,
    Scenarios/<calib-run-id>. A failed run does not stop the rest."""
    repo_root = find_repo_root()
    only_list = only.split(",") if only else None
    results = ex.import_manual_run_all(repo_root, only=only_list)
    n_ok = sum(1 for r in results if r["status"] == "success")
    n_fail = sum(1 for r in results if r["status"] != "success")
    for r in results:
        click.echo(f"[{r['status'].upper():7s}] {r['calib_run_id']}  run={r.get('run_id')}")
        if r["status"] != "success" and r.get("error"):
            click.echo(f"    {r['error']}", err=True)
    click.echo(f"\n{n_ok} succeeded, {n_fail} failed.")
    sys.exit(1 if n_fail else 0)


@main.command("prep")
@click.option("--run", "calib_run_id", required=True)
@click.pass_context
def prep_cmd(ctx, calib_run_id):
    """Run the prep script for a single calibration run without executing
    the model."""
    repo_root = ctx.obj["repo_root"]
    try:
        calib_run = cfg.load_calibration_run(repo_root, calib_run_id)
        cr_dir = repo_root / "calibration_runs"
        prep.run_prep_scripts(calib_run, cr_dir, calib_run_id)
    except tdmcalibError as e:
        click.echo(f"[FAIL] {calib_run_id}: {e}", err=True)
        sys.exit(1)
    click.echo(f"[OK]   {calib_run_id} prep complete")


@main.command("status")
@click.option("--run", "calib_run_id", default=None)
def status_cmd(calib_run_id):
    """Show the latest known run status for each calibration run."""
    repo_root = find_repo_root()
    runs = md.list_runs(repo_root, calib_run_id)
    seen = set()
    for r in runs:
        key = r["calib_run_id"]
        if key in seen:
            continue
        seen.add(key)
        click.echo(f"{r['calib_run_id']}: {r['status']} (run {r['run_id']}, {r['started_at']})")
    if not runs:
        click.echo("No runs recorded yet.")


if __name__ == "__main__":
    main()
