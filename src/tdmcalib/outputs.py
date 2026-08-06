"""Output inventory and curation.

Every file the TDM produces in a run's working folder gets inventoried
(path, size) regardless of whether it's curated -- that inventory backs run
metadata's aggregate file count/byte total even for files that never leave
the gitignored working folder. Working folders can hold thousands of files
and tens of gigabytes, so this listing is stat()-only and never reads file
contents. A declared, glob-based selection then determines which files
actually get copied into runs/{calib_run_id}/outputs/ (replacing whatever a
prior attempt for the same calib_run_id left there -- see execution.py);
only those get a checksum (computed at copy time). Every selected file is written
there regardless of size, but any file whose actual written size exceeds
the configured max_file_size_mb is marked "committed": False and listed in
that outputs/ folder's own auto-generated .gitignore -- kept on disk
locally (e.g. so reports still render fully on the machine that curated it)
but never committed to the repo, rather than aborting curation. This is
what actually enforces CLAUDE.md's "never commit large binary outputs"
rule in practice: it's automatic regardless of what outputs.include
declares, not something that depends on getting every pattern/tab
selection exactly right ahead of time.

Curated files land directly in runs/{calib_run_id}/ (siblings of that run's
run_info/ history -- see metadata.py) -- flattened, not nested under an
outputs/ subfolder.

Each outputs.include entry is one of three shapes (config/schemas/
calibration_run.schema.json enforces exactly one): {"datafile": <glob
pattern>, "columns": [...]}, "columns" optional, {"matrix": <glob pattern>,
"tabs": [...]}, or {"network": <glob pattern>, "fields": [...]}. Declaring
"columns" means the matched file(s) should be column-filtered rather than
copied whole -- e.g. Cube Voyager's "TAZ-Based Metrics.csv" summaries carry
~18 columns and run ~200 MB, comfortably over any reasonable size ceiling,
when the handful of columns a report actually reads would be a fraction of
that. For an entry like this, copy_selected() writes a column-filtered copy
(named "<stem>_filtered.csv") instead of copying the file whole. A "matrix"
entry matches a Cube Voyager .mtx file and extracts only the named "tabs"
tables via CONVERTMAT (matrix_utils.extract_matrix_tabs) -- for large
multi-table matrices (skims, trip tables) where only one or two tables are
actually needed downstream, and the full file would be hundreds of MB. Its
optional "format" is "omx" (default, Python-readable) or "mtx" (Cube's own
native format), written as "<stem>.<format>". A "network" entry matches a
Cube Voyager .net file and exports the named "fields" via
network_utils.export_network_fields() -- same rationale. Its optional
"format" is "geojson" (default), "shp" (zipped as a single "<stem>.shp.zip"),
or "net" (Cube's own native format, field-filtered via NETWORK's EXCLUDE=).
Matrix and network entries are the two curation paths that need Cube Voyager
itself (a voyager_exe path) -- plain datafile/column entries never do. The
size ceiling is checked against the bytes actually written -- the
filtered/extracted/exported size for these entries, the source size for a
plain copy -- not the raw source size in all cases, since the raw size of a
to-be-transformed file says nothing about what actually lands on disk.

Ported unchanged from WF-TDM-Runs' src/tdmruns/outputs.py -- output curation
mechanics are a property of what the TDM produces, not of the
run_set/scenario-vs-calibration-run data model."""

import csv
import fnmatch
import hashlib
import shutil
from pathlib import Path

from tdmcalib import matrix_utils, network_utils
from tdmcalib.exceptions import OutputCollectionError

CHECKSUM_CHUNK_BYTES = 1024 * 1024


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHECKSUM_CHUNK_BYTES):
            h.update(chunk)
    return h.hexdigest()


def inventory(scenario_folder: Path) -> list:
    """Full listing of every file produced in the run's working folder, with
    size but no checksum -- working folders are routinely tens of GB across
    thousands of files, and hashing all of it just to report an aggregate
    count/byte total (the only thing run metadata keeps from this) would
    read every byte for no benefit. Does not copy anything."""
    entries = []
    for path in sorted(scenario_folder.rglob("*")):
        if path.is_file():
            rel = path.relative_to(scenario_folder).as_posix()
            entries.append({"relative_path": rel, "size_bytes": path.stat().st_size})
    return entries


# Default output format per entry_type when a "format" key isn't declared --
# also the full set of extensions _dest_filename() ever produces.
_DEFAULT_FORMAT = {"matrix": "omx", "network": "geojson"}


def _dest_filename(entry: dict) -> str:
    src_name = Path(entry["relative_path"])
    entry_type = entry.get("entry_type")
    if entry_type == "matrix":
        return f"{src_name.stem}.{entry.get('format') or 'omx'}"
    if entry_type == "network":
        fmt = entry.get("format") or "geojson"
        return f"{src_name.stem}.shp.zip" if fmt == "shp" else f"{src_name.stem}.{fmt}"
    if entry.get("columns"):
        return f"{src_name.stem}_filtered{src_name.suffix}"
    return src_name.name


def select(entries: list, include_patterns: list) -> list:
    """Filters the full inventory down to entries matching at least one
    declared {"datafile": <glob>, "columns": [...]}, {"matrix": <glob>,
    "tabs": [...], "format": ...}, or {"network": <glob>, "fields": [...],
    "format": ...} entry, the glob evaluated against each file's path
    relative to the working folder. The resulting selected entries carry
    an "entry_type" ("datafile", "matrix", or "network") plus whichever of
    "columns"/"tabs"/"fields" applies (and "format", for matrix/network),
    that copy_selected() acts on."""
    if not include_patterns:
        return []
    normalized = []
    for p in include_patterns:
        if "matrix" in p:
            normalized.append((
                p["matrix"],
                {
                    "entry_type": "matrix",
                    "tabs": p["tabs"],
                    "format": p.get("format", _DEFAULT_FORMAT["matrix"]),
                    "source_format": p.get("source_format", "mtx"),
                },
            ))
        elif "network" in p:
            normalized.append((
                p["network"],
                {
                    "entry_type": "network",
                    "fields": p.get("fields"),
                    "format": p.get("format", _DEFAULT_FORMAT["network"]),
                },
            ))
        else:
            normalized.append((p["datafile"], {"entry_type": "datafile", "columns": p.get("columns")}))
    selected = []
    for entry in entries:
        for pattern, tags in normalized:
            if fnmatch.fnmatch(entry["relative_path"], pattern):
                selected.append({**entry, **tags})
                break
    return selected


def _write_outputs_gitignore(dest_dir: Path, uncommitted_names: list):
    """(Re)writes dest_dir/.gitignore to list exactly the currently-curated
    files that exceed the size ceiling -- regenerated fresh on every
    curation run (not appended), so it always reflects what's actually
    present right now, never stale entries from an earlier curation of the
    same run directory (e.g. after outputs.include narrowed a tabs list and
    a previously-oversized file no longer applies). Removes the file
    entirely when nothing is over the ceiling, rather than leaving an empty
    marker behind."""
    gitignore_path = dest_dir / ".gitignore"
    if not uncommitted_names:
        if gitignore_path.exists():
            gitignore_path.unlink()
        return
    lines = [
        "# Auto-generated by tdmcalib's output curation (src/tdmcalib/outputs.py).",
        "# These files exceeded the configured max_file_size_mb ceiling -- kept here",
        "# locally (e.g. so reports still render fully on this machine) but never",
        "# committed. Regenerated on every curation run; do not edit by hand.",
        "",
    ] + sorted(uncommitted_names)
    gitignore_path.write_text("\n".join(lines) + "\n")


def _write_filtered_csv(src: Path, dst: Path, columns: list):
    with open(src, newline="") as fin, open(dst, "w", newline="") as fout:
        reader = csv.DictReader(fin)
        missing = [c for c in columns if c not in (reader.fieldnames or [])]
        if missing:
            raise OutputCollectionError(
                f"columns {missing} not found in {src.name} "
                f"(available: {reader.fieldnames})"
            )
        writer = csv.DictWriter(fout, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            writer.writerow(row)


def copy_selected(
    scenario_folder: Path,
    selected: list,
    dest_dir: Path,
    max_file_size_mb: float,
    repo_root: Path,
    voyager_exe: str = None,
) -> list:
    """Copies each selected file directly into dest_dir, flattened to just
    its filename -- curated outputs don't preserve the model's internal
    folder structure. A datafile entry with a "columns" list (see select())
    is written as a column-filtered copy ("<stem>_filtered.csv") instead of
    a byte-for-byte copy; a "matrix" entry is extracted via
    matrix_utils.extract_matrix_tabs() in its declared format (omx/mtx); a
    "network" entry is exported via network_utils.export_network_fields()
    in its declared format (geojson/shp/net) -- both matrix and network
    entries require voyager_exe to be set. Returns the manifest entries
    augmented with a sha256 checksum, the repo-relative destination path,
    size_bytes updated to the actual bytes written, and a "committed" flag.
    Every selected file is written to dest_dir regardless of size (every
    curated file gets a checksum -- computed here, not in inventory(), since
    only the typically handful of selected files ever need one); a file
    whose written size exceeds max_file_size_mb is left in place with
    "committed": False rather than deleted, and dest_dir/.gitignore is
    (re)written to list every such file (see _write_outputs_gitignore()) --
    so it's still usable locally (e.g. rendering reports on this machine)
    without ever being committed. Raises OutputCollectionError only if
    flattening would collide two selected files onto the same filename, or
    for a genuine extraction failure (missing tabs/columns/fields, Voyager
    not configured when required)."""
    seen = {}
    for entry in selected:
        name = _dest_filename(entry)
        if name in seen:
            raise OutputCollectionError(
                f"Selected outputs '{seen[name]}' and '{entry['relative_path']}' both "
                f"flatten to the filename '{name}' -- refusing to let one overwrite the "
                "other. Narrow the outputs.include patterns so each selected file is unique."
            )
        seen[name] = entry["relative_path"]

    dest_dir.mkdir(parents=True, exist_ok=True)
    curated = []
    for entry in selected:
        src = scenario_folder / entry["relative_path"]
        dst = dest_dir / _dest_filename(entry)
        if entry.get("entry_type") == "matrix":
            source_format = entry.get("source_format", "mtx")
            if source_format != "omx" and not voyager_exe:
                raise OutputCollectionError(
                    f"'{entry['relative_path']}' is a matrix output but no Voyager "
                    "executable is configured (config/local.yaml's Voyager_EXE) -- "
                    "required to extract matrix tabs at curation time."
                )
            matrix_utils.extract_matrix_tabs(
                src, entry["tabs"], dst, voyager_exe,
                output_format=entry["format"], source_format=source_format,
            )
        elif entry.get("entry_type") == "network":
            if not voyager_exe:
                raise OutputCollectionError(
                    f"'{entry['relative_path']}' is a network output but no Voyager "
                    "executable is configured (config/local.yaml's Voyager_EXE) -- "
                    "required to export network fields at curation time."
                )
            geometry_shp = network_utils.find_geometry_shapefile(scenario_folder)
            network_utils.export_network_fields(
                src, geometry_shp, entry["fields"], dst, voyager_exe, output_format=entry["format"]
            )
        elif entry.get("columns"):
            _write_filtered_csv(src, dst, entry["columns"])
        else:
            shutil.copy2(src, dst)

        size_bytes = dst.stat().st_size
        committed = size_bytes <= int(max_file_size_mb * 1024 * 1024)

        curated.append(
            {
                **entry,
                "size_bytes": size_bytes,
                "sha256": _sha256(dst),
                "repo_path": dst.resolve().relative_to(repo_root.resolve()).as_posix(),
                "committed": committed,
            }
        )

    _write_outputs_gitignore(dest_dir, [c["repo_path"].rsplit("/", 1)[-1] for c in curated if not c["committed"]])
    return curated


def curate(
    scenario_folder: Path,
    full_inventory: list,
    output_spec: dict,
    run_dir: Path,
    status: str,
    error: str,
    repo_root: Path,
    voyager_exe: str = None,
) -> tuple:
    """Selects+copies whatever outputs.include matches out of full_inventory
    (already produced by inventory(scenario_folder) -- passed in rather than
    recomputed here, since the caller also needs it for the aggregate
    inventory_count/inventory_total_bytes in run metadata, and a working
    folder can hold thousands of files, not worth walking twice). Folds the
    result into the execution status/error decided so far (e.g. from the
    TDM's exit code, or "success"/None for a manual import). Returns
    (status, error, curated) for the caller to pass straight into
    metadata.build().

    An exit code of 0 (or a manual import) alone isn't "success" if
    outputs.include declared patterns but none of them matched anything on
    disk -- e.g. the model didn't reach the step that produces them. That's
    treated as a failure here rather than passed through unexamined.
    """
    selected = select(full_inventory, output_spec["include"])
    curated = []
    if selected:
        try:
            curated = copy_selected(
                scenario_folder,
                selected,
                run_dir,
                output_spec["max_file_size_mb"],
                repo_root,
                voyager_exe=voyager_exe,
            )
        except Exception as e:  # noqa: BLE001 -- recorded in metadata, not swallowed silently
            status = "failed"
            error = (error + " " if error else "") + f"Output curation failed: {e}"
    elif output_spec["include"]:
        status = "failed"
        error = (
            (error + " " if error else "")
            + f"No files under {scenario_folder} matched outputs.include "
            f"{output_spec['include']!r}."
        )
    return status, error, curated
