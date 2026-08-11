"""report/preprocess/distribution.py's _iter_omx_sources()/_extract_omx_to_df()
fallback to per-tab split files -- exercised against synthetic tmp_path
fixtures rather than a real calibration run's outputs, since the point is
just to confirm the loader transparently handles what
src/tdmcalib/outputs.py's copy_selected() writes when a combined multi-tab
matrix exceeds max_file_size_mb (see _split_omx_by_tab() there)."""
import numpy as np
import openmatrix as omx
import pytest

from report.preprocess import distribution as dist


def _write_omx(path, tables):
    f = omx.open_file(str(path), "w")
    try:
        for name, mat in tables.items():
            f[name] = mat
    finally:
        f.close()


def test_extract_omx_to_df_reads_combined_file_when_present(tmp_path):
    omx_path = tmp_path / "skm_DY_Dist.omx"
    _write_omx(omx_path, {"HBW": np.array([[0.0, 1.0], [2.0, 0.0]])})

    df = dist._extract_omx_to_df(omx_path, ["HBW"], "Dist")
    assert sorted(df["Purpose"].unique()) == ["HBW"]
    assert len(df) == 2  # two nonzero cells


def test_extract_omx_to_df_falls_back_to_split_siblings(tmp_path):
    omx_path = tmp_path / "skm_DY_Dist.omx"  # never written -- only splits exist
    _write_omx(tmp_path / "skm_DY_Dist__HBW.omx", {"HBW": np.array([[0.0, 1.0], [2.0, 0.0]])})
    _write_omx(tmp_path / "skm_DY_Dist__HBShp.omx", {"HBShp": np.array([[0.0, 3.0], [0.0, 0.0]])})

    df = dist._extract_omx_to_df(omx_path, ["HBW", "HBShp"], "Dist")
    assert sorted(df["Purpose"].unique()) == ["HBShp", "HBW"]
    assert len(df) == 3  # 2 nonzero cells for HBW + 1 for HBShp


def test_extract_omx_to_df_raises_when_neither_combined_nor_split_exist(tmp_path):
    omx_path = tmp_path / "skm_DY_Dist.omx"
    with pytest.raises(FileNotFoundError, match="skm_DY_Dist"):
        dist._extract_omx_to_df(omx_path, ["HBW"], "Dist")


def test_extract_omx_to_df_warns_but_does_not_raise_for_missing_tab(tmp_path, capsys):
    omx_path = tmp_path / "skm_DY_Dist.omx"
    _write_omx(tmp_path / "skm_DY_Dist__HBW.omx", {"HBW": np.array([[0.0, 1.0], [0.0, 0.0]])})

    df = dist._extract_omx_to_df(omx_path, ["HBW", "NotThere"], "Dist")
    assert sorted(df["Purpose"].unique()) == ["HBW"]
    assert "NotThere not found in OMX" in capsys.readouterr().out
