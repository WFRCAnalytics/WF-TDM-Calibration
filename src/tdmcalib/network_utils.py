"""Cube Voyager network (.net) export helpers -- the .net-file analog of
matrix_utils.py's .mtx handling. A .net file is Voyager's proprietary binary
format and can't be read directly by geopandas/Python, so Cube Voyager's own
NETWORK program is used to export it first -- to a full shapefile (every
link attribute, FILEO LINKO=..., FORMAT=SHP) for the geojson/shp output
formats, or to a field-filtered native .net (FILEO NETO=..., EXCLUDE=...)
for the net format. Same two-step shape as matrix_utils.extract_matrix_tabs():
a full Voyager-side export/discovery step, then a trim to just the declared
fields.

NOTE (carried over from WF-TDM-Runs): the RUN PGM=NETWORK scripts below have
not been validated against a real Cube Voyager run yet (unlike
matrix_utils.py's CONVERTMAT pattern, exercised against real model output in
the source repo) -- they're built from
tdm/2_ModelScripts/5_AssignHwy/04_SummarizeLoadedNetworks.s's own usage of
FILEI NETI/GEOMI and FILEO LINKO=...,FORMAT=SHP / FILEO NETO=...,EXCLUDE=...,
simplified to a single network/geometry pair. Treat this as unverified until
run once against a real .net file.

Ported unchanged from WF-TDM-Runs' src/tdmruns/network_utils.py."""
import subprocess
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd

from tdmcalib.exceptions import OutputCollectionError


def _run_voyager_script(script_path: Path, bat_path: Path, voyager_exe: str):
    voyager_dir = str(Path(voyager_exe).parent)
    with open(bat_path, "w") as f:
        f.write(f'start /w "{voyager_dir}" VOYAGER.EXE "{script_path.resolve()}" /start -Report\n')
    subprocess.call(str(bat_path), cwd=str(bat_path.parent))


def export_net_to_shapefile(net_path: Path, geometry_shp: Path, dest_shp: Path, voyager_exe: str):
    """Runs Cube Voyager's NETWORK program to export every link attribute on
    net_path into a full shapefile at dest_shp -- the .net-file analog of
    matrix_utils.convert_mtx_to_omx(). geometry_shp supplies the actual line
    geometry (a raw .net file alone doesn't carry a GIS-ready alignment)."""
    with tempfile.TemporaryDirectory(prefix="netexport_") as work_dir_str:
        work_dir = Path(work_dir_str)
        script_path = work_dir / f"_export_{net_path.stem}.s"
        bat_path = work_dir / f"_export_{net_path.stem}.bat"
        with open(script_path, "w") as f:
            f.write(
                "RUN PGM=NETWORK\n"
                f'    FILEI NETI = "{net_path.resolve()}"\n'
                f'    FILEI GEOMI = "{geometry_shp.resolve()}"\n'
                f'    FILEO LINKO = "{dest_shp.resolve()}", FORMAT=SHP\n'
                "ENDRUN\n"
            )
        _run_voyager_script(script_path, bat_path, voyager_exe)
        if not dest_shp.exists():
            raise RuntimeError(f"NETWORK export did not produce {dest_shp} -- check {bat_path} output")


def export_net_field_filtered(
    net_path: Path, geometry_shp: Path, exclude_fields: list, dest_net: Path, voyager_exe: str
):
    """Runs Cube Voyager's NETWORK program to write a field-filtered copy of
    net_path's link attributes to dest_net, still in Cube's own native .net
    format -- used by export_network_fields() for output_format="net".
    Excludes every available field the caller doesn't want, via NETWORK's
    own FILEO NETO=...,EXCLUDE=... clause."""
    dest_net.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="netexport_net_") as work_dir_str:
        work_dir = Path(work_dir_str)
        script_path = work_dir / f"_exportnet_{net_path.stem}.s"
        bat_path = work_dir / f"_exportnet_{net_path.stem}.bat"
        fileo = f'    FILEO NETO = "{dest_net.resolve()}"'
        if exclude_fields:
            exclude_clause = ",\n                ".join(exclude_fields)
            fileo += f",\n        EXCLUDE={exclude_clause}"
        with open(script_path, "w") as f:
            f.write(
                "RUN PGM=NETWORK\n"
                f'    FILEI NETI = "{net_path.resolve()}"\n'
                f'    FILEI GEOMI = "{geometry_shp.resolve()}"\n'
                f"{fileo}\n"
                "ENDRUN\n"
            )
        _run_voyager_script(script_path, bat_path, voyager_exe)
        if not dest_net.exists():
            raise RuntimeError(f"NETWORK export did not produce {dest_net} -- check {bat_path} output")


def find_geometry_shapefile(scenario_folder: Path) -> Path:
    """Locates this run's network geometry shapefile -- ships per-scenario at
    a version-prefixed name (e.g. 'WFv1000_MasterNet_* - Link.shp'), so it's
    globbed rather than hardcoded."""
    geom_dir = scenario_folder / "0_InputProcessing" / "UpdatedMasterNet" / "GIS"
    matches = sorted(geom_dir.glob("*Link.shp"))
    if not matches:
        raise FileNotFoundError(f"No *Link.shp found under {geom_dir} -- needed as NETWORK's GEOMI input.")
    if len(matches) > 1:
        raise FileNotFoundError(f"Multiple *Link.shp found under {geom_dir}: {matches} -- expected exactly one.")
    return matches[0]


def _zip_shapefile(shp_path: Path, dest_zip: Path):
    """Bundles a shapefile's sidecar files (.shp/.shx/.dbf/.prj/.cpg/...)
    sharing shp_path's stem into a single dest_zip -- keeps curation's
    one-entry-one-file contract intact for a format that's naturally
    multi-file."""
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    sidecars = sorted(shp_path.parent.glob(f"{shp_path.stem}.*"))
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for sidecar in sidecars:
            zf.write(sidecar, arcname=sidecar.name)


def export_network_fields(
    net_path: Path,
    geometry_shp: Path,
    fields: list,
    dest_path: Path,
    voyager_exe: str,
    output_format: str = "geojson",
) -> None:
    """Exports net_path's link attributes to a full shapefile via Voyager
    (to discover/validate available fields, and for the geojson/shp output
    formats), then writes only the named fields to dest_path in the
    declared output_format -- deleting intermediate exports afterward
    regardless of outcome. Raises OutputCollectionError naming the
    available fields if any requested one isn't present.

    output_format="geojson" (default): geopandas writes dest_path directly,
    reprojected to EPSG:4326 if the source shapefile has a defined CRS.
    output_format="shp": geopandas writes a field-filtered shapefile
    (native CRS, no reprojection) to a temp dir, zipped into a single
    dest_path. output_format="net": field selection happens in Voyager
    itself (export_net_field_filtered(), NETWORK's own EXCLUDE=), producing
    a genuinely native-format .net at dest_path -- no geopandas/GeoJSON
    involved for this path at all.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="netexport_shp_") as shp_dir_str:
        shp_dir = Path(shp_dir_str)
        temp_shp = shp_dir / f"{net_path.stem}.shp"
        export_net_to_shapefile(net_path, geometry_shp, temp_shp, voyager_exe)

        gdf = gpd.read_file(temp_shp)
        available = [c for c in gdf.columns if c != "geometry"]
        missing = [f for f in fields if f not in available]
        if missing:
            raise OutputCollectionError(
                f"fields {missing} not found in {net_path.name} (available: {available})"
            )

        if output_format == "net":
            exclude_fields = [f for f in available if f not in fields]
            export_net_field_filtered(net_path, geometry_shp, exclude_fields, dest_path, voyager_exe)
            return

        trimmed = gdf[[*fields, "geometry"]]
        if output_format == "geojson":
            if trimmed.crs is not None:
                trimmed = trimmed.to_crs(epsg=4326)
            trimmed.to_file(dest_path, driver="GeoJSON")
        elif output_format == "shp":
            temp_out_shp = shp_dir / f"_trimmed_{net_path.stem}.shp"
            trimmed.to_file(temp_out_shp)
            _zip_shapefile(temp_out_shp, dest_path)
        else:
            raise ValueError(f"Unknown network output_format: {output_format!r}")
