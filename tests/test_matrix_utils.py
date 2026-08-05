"""matrix_utils.trim_omx_tabs()/extract_matrix_tabs(source_format="omx") --
the no-Voyager path for trimming a matrix that's already OMX (e.g. importing
an archived calibration run whose raw output was pre-converted), as opposed
to the CONVERTMAT/Voyager path for a live run's native .mtx output."""
import numpy as np
import openmatrix as omx
import pytest

from tdmcalib import matrix_utils as mu
from tdmcalib.exceptions import OutputCollectionError


def _write_omx(path, tables):
    f = omx.open_file(str(path), "w")
    try:
        for name, mat in tables.items():
            f[name] = mat
    finally:
        f.close()


def test_trim_omx_tabs_keeps_only_named_tables(tmp_path):
    src = tmp_path / "full.omx"
    _write_omx(src, {
        "HBW": np.ones((3, 3)),
        "HBShp": np.zeros((3, 3)),
        "HBOth": np.full((3, 3), 2.0),
    })
    dest = tmp_path / "trimmed.omx"
    mu.trim_omx_tabs(src, ["HBW", "HBOth"], dest)

    f = omx.open_file(str(dest), "r")
    try:
        assert sorted(f.list_matrices()) == ["HBOth", "HBW"]
        assert np.array_equal(np.array(f["HBW"]), np.ones((3, 3)))
    finally:
        f.close()


def test_trim_omx_tabs_missing_table_raises(tmp_path):
    src = tmp_path / "full.omx"
    _write_omx(src, {"HBW": np.ones((2, 2))})
    dest = tmp_path / "trimmed.omx"
    with pytest.raises(OutputCollectionError, match="DoesNotExist"):
        mu.trim_omx_tabs(src, ["DoesNotExist"], dest)


def test_extract_matrix_tabs_omx_source_needs_no_voyager(tmp_path):
    src = tmp_path / "full.omx"
    _write_omx(src, {"HBW": np.ones((2, 2)), "HBShp": np.zeros((2, 2))})
    dest = tmp_path / "trimmed.omx"

    # voyager_exe=None -- must not be needed when source_format="omx".
    mu.extract_matrix_tabs(src, ["HBW"], dest, voyager_exe=None, source_format="omx")

    f = omx.open_file(str(dest), "r")
    try:
        assert f.list_matrices() == ["HBW"]
    finally:
        f.close()


def test_extract_matrix_tabs_omx_source_rejects_mtx_output(tmp_path):
    src = tmp_path / "full.omx"
    _write_omx(src, {"HBW": np.ones((2, 2))})
    dest = tmp_path / "trimmed.mtx"
    with pytest.raises(OutputCollectionError, match="output_format"):
        mu.extract_matrix_tabs(
            src, ["HBW"], dest, voyager_exe=None, output_format="mtx", source_format="omx"
        )
