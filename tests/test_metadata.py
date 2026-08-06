"""Run metadata: every attempt gets its own permanent file under
run_info/{run_id}.json, and "latest" resolution relies on run_id sorting
chronologically -- these tests exercise that contract directly rather than
trusting it by inspection."""
from tdmcalib import metadata as md


def _minimal(calib_run_id, run_id, status="success"):
    return md.build(
        schema_version=1,
        calib_run_id=calib_run_id,
        run_id=run_id,
        status=status,
        started_at="2026-01-01T00:00:00+00:00",
        framework_commit_sha="abc123",
        tdm_state={},
        baseline_file="baseline.block",
        overrides={},
    )


def test_write_creates_run_info_file_named_by_run_id(tmp_path):
    run_dir = tmp_path / "C50"
    md.write(run_dir, _minimal("C50", "20260101-000000-aaaa"))
    assert (run_dir / "run_info" / "20260101-000000-aaaa.json").is_file()
    assert not (run_dir / "run_metadata.json").exists()


def test_write_does_not_delete_earlier_attempts(tmp_path):
    run_dir = tmp_path / "C50"
    md.write(run_dir, _minimal("C50", "20260101-000000-aaaa"))
    md.write(run_dir, _minimal("C50", "20260102-000000-bbbb"))
    attempts = sorted(p.name for p in (run_dir / "run_info").glob("*.json"))
    assert attempts == ["20260101-000000-aaaa.json", "20260102-000000-bbbb.json"]


def test_read_without_run_id_returns_latest_attempt(tmp_path):
    run_dir = tmp_path / "C50"
    md.write(run_dir, _minimal("C50", "20260101-000000-aaaa", status="failed"))
    md.write(run_dir, _minimal("C50", "20260102-000000-bbbb", status="success"))
    assert md.read(run_dir)["run_id"] == "20260102-000000-bbbb"


def test_read_with_run_id_returns_that_specific_attempt(tmp_path):
    run_dir = tmp_path / "C50"
    md.write(run_dir, _minimal("C50", "20260101-000000-aaaa", status="failed"))
    md.write(run_dir, _minimal("C50", "20260102-000000-bbbb", status="success"))
    assert md.read(run_dir, run_id="20260101-000000-aaaa")["status"] == "failed"


def test_latest_run_returns_none_when_nothing_recorded(tmp_path):
    assert md.latest_run(tmp_path, "C99") is None


def test_latest_run_picks_most_recent_run_id(tmp_path):
    repo_root = tmp_path
    run_dir = repo_root / "runs" / "C50"
    md.write(run_dir, _minimal("C50", "20260101-000000-aaaa"))
    md.write(run_dir, _minimal("C50", "20260102-000000-bbbb"))
    assert md.latest_run(repo_root, "C50")["run_id"] == "20260102-000000-bbbb"


def test_list_runs_returns_only_latest_per_calib_run_id(tmp_path):
    repo_root = tmp_path
    md.write(repo_root / "runs" / "C50", _minimal("C50", "20260101-000000-aaaa"))
    md.write(repo_root / "runs" / "C50", _minimal("C50", "20260102-000000-bbbb"))
    md.write(repo_root / "runs" / "C33", _minimal("C33", "20260101-000000-cccc"))
    runs = md.list_runs(repo_root)
    by_calib_run = {r["calib_run_id"]: r["run_id"] for r in runs}
    assert by_calib_run == {"C50": "20260102-000000-bbbb", "C33": "20260101-000000-cccc"}


def test_list_attempts_returns_full_history_oldest_first(tmp_path):
    repo_root = tmp_path
    run_dir = repo_root / "runs" / "C50"
    md.write(run_dir, _minimal("C50", "20260102-000000-bbbb"))
    md.write(run_dir, _minimal("C50", "20260101-000000-aaaa"))
    run_ids = [r["run_id"] for r in md.list_attempts(repo_root, "C50")]
    assert run_ids == ["20260101-000000-aaaa", "20260102-000000-bbbb"]


def test_latest_successful_run_skips_a_failed_latest_attempt(tmp_path):
    repo_root = tmp_path
    run_dir = repo_root / "runs" / "C50"
    md.write(run_dir, _minimal("C50", "20260101-000000-aaaa", status="success"))
    md.write(run_dir, _minimal("C50", "20260102-000000-bbbb", status="failed"))
    assert md.latest_successful_run(repo_root, "C50") is None
