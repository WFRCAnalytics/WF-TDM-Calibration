"""Output inventory/selection/curation -- size ceiling and flattening-collision
behavior in particular, since those are the failure modes that would
otherwise silently commit something too large or overwrite one curated file
with another."""
import numpy as np
import openmatrix as omx
import pytest

from tdmcalib import outputs as out
from tdmcalib.exceptions import OutputCollectionError


def _make_file(path, size_bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"0" * size_bytes)


def test_inventory_lists_all_files_with_sizes(tmp_path):
    _make_file(tmp_path / "a" / "one.csv", 10)
    _make_file(tmp_path / "b" / "two.csv", 20)
    entries = out.inventory(tmp_path)
    by_path = {e["relative_path"]: e["size_bytes"] for e in entries}
    assert by_path == {"a/one.csv": 10, "b/two.csv": 20}


def test_select_matches_glob_and_tags_entry_type():
    entries = [
        {"relative_path": "reports/summary.csv", "size_bytes": 100},
        {"relative_path": "logs/run.log", "size_bytes": 5},
    ]
    selected = out.select(entries, [{"datafile": "reports/*.csv"}])
    assert len(selected) == 1
    assert selected[0]["entry_type"] == "datafile"
    assert selected[0]["relative_path"] == "reports/summary.csv"


def test_select_returns_nothing_for_empty_patterns():
    assert out.select([{"relative_path": "x", "size_bytes": 1}], []) == []


def test_copy_selected_flattening_collision_raises(tmp_path):
    scenario_folder = tmp_path / "scenario"
    _make_file(scenario_folder / "a" / "summary.csv", 10)
    _make_file(scenario_folder / "b" / "summary.csv", 10)
    dest = tmp_path / "outputs"
    selected = [
        {"relative_path": "a/summary.csv", "size_bytes": 10, "entry_type": "datafile", "columns": None},
        {"relative_path": "b/summary.csv", "size_bytes": 10, "entry_type": "datafile", "columns": None},
    ]
    with pytest.raises(OutputCollectionError, match="both flatten"):
        out.copy_selected(scenario_folder, selected, dest, 100, tmp_path)


def test_copy_selected_plain_datafile_copies_byte_for_byte(tmp_path):
    scenario_folder = tmp_path / "scenario"
    _make_file(scenario_folder / "reports" / "summary.csv", 42)
    dest = tmp_path / "outputs"
    selected = [{"relative_path": "reports/summary.csv", "size_bytes": 42, "entry_type": "datafile", "columns": None}]
    curated = out.copy_selected(scenario_folder, selected, dest, 100, tmp_path)
    assert len(curated) == 1
    assert (dest / "summary.csv").stat().st_size == 42
    assert curated[0]["sha256"]
    assert curated[0]["repo_path"] == "outputs/summary.csv"
    assert curated[0]["committed"] is True
    assert not (dest / ".gitignore").exists()  # nothing over the ceiling


def test_copy_selected_column_filtered_csv(tmp_path):
    scenario_folder = tmp_path / "scenario"
    scenario_folder.mkdir()
    src = scenario_folder / "wide.csv"
    src.write_text("TAZID,Metric,Extra\n1,10,ignored\n2,20,ignored\n")
    dest = tmp_path / "outputs"
    selected = [
        {
            "relative_path": "wide.csv",
            "size_bytes": src.stat().st_size,
            "entry_type": "datafile",
            "columns": ["TAZID", "Metric"],
        }
    ]
    curated = out.copy_selected(scenario_folder, selected, dest, 100, tmp_path)
    out_text = (dest / "wide_filtered.csv").read_text()
    assert out_text == "TAZID,Metric\n1,10\n2,20\n"
    assert curated[0]["repo_path"].endswith("wide_filtered.csv")


def test_copy_selected_missing_column_raises(tmp_path):
    scenario_folder = tmp_path / "scenario"
    scenario_folder.mkdir()
    src = scenario_folder / "wide.csv"
    src.write_text("TAZID,Metric\n1,10\n")
    dest = tmp_path / "outputs"
    selected = [
        {
            "relative_path": "wide.csv",
            "size_bytes": src.stat().st_size,
            "entry_type": "datafile",
            "columns": ["TAZID", "DoesNotExist"],
        }
    ]
    with pytest.raises(OutputCollectionError, match="DoesNotExist"):
        out.copy_selected(scenario_folder, selected, dest, 100, tmp_path)


def test_copy_selected_keeps_oversized_file_uncommitted_and_gitignored(tmp_path):
    scenario_folder = tmp_path / "scenario"
    _make_file(scenario_folder / "big.csv", 2 * 1024 * 1024)
    dest = tmp_path / "outputs"
    selected = [{"relative_path": "big.csv", "size_bytes": 2 * 1024 * 1024, "entry_type": "datafile", "columns": None}]
    curated = out.copy_selected(scenario_folder, selected, dest, max_file_size_mb=1, repo_root=tmp_path)
    assert len(curated) == 1
    assert curated[0]["committed"] is False
    assert (dest / "big.csv").exists()  # kept locally, not deleted
    assert "big.csv" in (dest / ".gitignore").read_text()


def test_copy_selected_removes_gitignore_once_nothing_is_oversized(tmp_path):
    # A prior curation left an oversized file + .gitignore; re-curating with
    # a smaller selection (e.g. a narrowed tabs list) should clean it up
    # rather than leave a stale .gitignore entry behind.
    scenario_folder = tmp_path / "scenario"
    _make_file(scenario_folder / "big.csv", 2 * 1024 * 1024)
    dest = tmp_path / "outputs"
    big_selected = [{"relative_path": "big.csv", "size_bytes": 2 * 1024 * 1024, "entry_type": "datafile", "columns": None}]
    out.copy_selected(scenario_folder, big_selected, dest, max_file_size_mb=1, repo_root=tmp_path)
    assert (dest / ".gitignore").exists()

    small_selected = [{"relative_path": "big.csv", "size_bytes": 2 * 1024 * 1024, "entry_type": "datafile", "columns": None}]
    curated = out.copy_selected(scenario_folder, small_selected, dest, max_file_size_mb=100, repo_root=tmp_path)
    assert curated[0]["committed"] is True
    assert not (dest / ".gitignore").exists()


def test_copy_selected_matrix_omx_source_needs_no_voyager(tmp_path):
    scenario_folder = tmp_path / "scenario"
    scenario_folder.mkdir()
    src = scenario_folder / "skm_DY_Dist.omx"
    f = omx.open_file(str(src), "w")
    try:
        f["HBW"] = np.ones((2, 2))
        f["HBShp"] = np.zeros((2, 2))
    finally:
        f.close()
    dest = tmp_path / "outputs"
    selected = [
        {
            "relative_path": "skm_DY_Dist.omx",
            "size_bytes": src.stat().st_size,
            "entry_type": "matrix",
            "tabs": ["HBW"],
            "format": "omx",
            "source_format": "omx",
        }
    ]
    # voyager_exe=None -- must not raise, since source_format="omx" doesn't need it.
    curated = out.copy_selected(scenario_folder, selected, dest, 100, tmp_path, voyager_exe=None)
    assert len(curated) == 1
    result = omx.open_file(str(dest / "skm_DY_Dist.omx"), "r")
    try:
        assert result.list_matrices() == ["HBW"]
    finally:
        result.close()


def test_copy_selected_matrix_mtx_source_without_voyager_raises(tmp_path):
    scenario_folder = tmp_path / "scenario"
    _make_file(scenario_folder / "skm_DY_Dist.MTX", 10)
    dest = tmp_path / "outputs"
    selected = [
        {
            "relative_path": "skm_DY_Dist.MTX",
            "size_bytes": 10,
            "entry_type": "matrix",
            "tabs": ["HBW"],
            "format": "omx",
            "source_format": "mtx",
        }
    ]
    with pytest.raises(OutputCollectionError, match="Voyager"):
        out.copy_selected(scenario_folder, selected, dest, 100, tmp_path, voyager_exe=None)


def test_curate_marks_failed_when_include_declared_but_nothing_matched(tmp_path):
    scenario_folder = tmp_path / "scenario"
    scenario_folder.mkdir()
    status, error, curated = out.curate(
        scenario_folder,
        full_inventory=[],
        output_spec={"include": [{"datafile": "reports/*.csv"}], "max_file_size_mb": 100},
        run_dir=tmp_path / "run",
        status="success",
        error=None,
        repo_root=tmp_path,
    )
    assert status == "failed"
    assert "matched" in error
    assert curated == []
