"""Control Center rendering for Cube Voyager's native .block format.

The TDM's Scenarios/_default/ library holds known-good, fully-populated
Control Center templates (one per scenario group/year) that an analyst would
normally copy and hand-edit. This module automates exactly that step: load
the chosen default, layer this calibration run's overrides on top, force in
the orchestrator-computed identity/path fields, layer in machine-local
values, and write the result out as the live _ControlCenter.block the TDM
driver script expects -- preserving every comment, blank line, and
non-assignment statement (if/else/endif, DISTRIBUTE, cluster commands, ...)
from the original template verbatim, and substituting only the lines whose
key was actually overridden.

Input file selection (e.g. WFRC_SEFile) and sensitivity/calibration knobs
(e.g. HOT_Toll_Min) are not treated as separate concerns -- they are both
just keys in this same file, so there is exactly one override mechanism.

Ported unchanged from WF-TDM-Runs' src/tdmruns/controlcenter.py except
render()'s signature, which drops the run_set/scenario two-layer split (this
repo has no run_set/scenario nesting -- one calibration run's `overrides` is
the whole thing)."""

import re
from pathlib import Path

from tdmcalib.exceptions import ControlCenterError

_ASSIGNMENT_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(?P<rest>.*)$"
)


class _Assignment:
    """One recognized `KEY = value` line. `raw` is the original, unmodified
    text of the line, used verbatim on write unless `key` is overridden."""

    __slots__ = ("raw", "indent", "key", "value", "comment")

    def __init__(self, raw: str, indent: str, key: str, value: str, comment: str | None):
        self.raw = raw
        self.indent = indent
        self.key = key
        self.value = value
        self.comment = comment


def _split_value_and_comment(rest: str) -> tuple[str, str | None]:
    """Splits the text after '=' into (value_text, trailing_comment-or-None),
    respecting single-quoted string literals so a ';' inside quotes (e.g.
    AddNodeFields = ';') isn't mistaken for the start of a comment."""
    in_quote = False
    for i, ch in enumerate(rest):
        if ch == "'":
            in_quote = not in_quote
        elif ch == ";" and not in_quote:
            return rest[:i].rstrip(), rest[i:]
    return rest.rstrip(), None


def _parse_lines(path: Path) -> list:
    """Parses a Cube block file into a list of raw text lines and recognized
    _Assignment objects, in original order. Non-assignment lines (blank,
    comment-only, if/else/endif, DISTRIBUTE, *(...) cluster commands, etc.)
    are kept as opaque raw strings and passed through unchanged on write."""
    lines = []
    with open(path, encoding="utf-8-sig") as f:
        for raw_with_newline in f:
            raw = raw_with_newline.rstrip("\n").rstrip("\r")
            stripped = raw.strip()
            if not stripped or stripped.startswith(";"):
                lines.append(raw)
                continue
            m = _ASSIGNMENT_RE.match(raw)
            if not m:
                lines.append(raw)
                continue
            value, comment = _split_value_and_comment(m.group("rest"))
            lines.append(_Assignment(raw, m.group("indent"), m.group("key"), value, comment))
    return lines


def load_baseline(tdm_path: Path, defaults_dir: str, filename: str) -> dict:
    path = tdm_path / defaults_dir / filename
    if not path.is_file():
        raise ControlCenterError(
            f"Baseline Control Center '{filename}' not found at {path}. "
            f"Check the filename against what actually exists in {tdm_path / defaults_dir}."
        )
    data = {}
    for line in _parse_lines(path):
        if isinstance(line, _Assignment):
            data[line.key] = line.value
    if not data:
        raise ControlCenterError(
            f"{path} contains no recognizable 'KEY = value' assignments -- "
            "check that this is really a Cube Control Center block file."
        )
    return data


def validate_overrides(baseline: dict, overrides: dict, source_label: str):
    unknown = sorted(k for k in overrides if k not in baseline)
    if unknown:
        raise ControlCenterError(
            f"{source_label} sets unknown Control Center key(s) not present in the "
            f"baseline file: {', '.join(unknown)}. This usually means a typo, or the "
            "baseline was changed by the TDM team and this override needs updating."
        )


def render(overrides: dict, local_layer: dict, identity_fields: dict) -> dict:
    """Layers overrides in order, each winning over the last: this
    calibration run's overrides -> local/machine values -> orchestrator-
    computed identity fields (which always win, to guarantee folder/path
    consistency regardless of what any override set). Keys not present here
    are left completely untouched in the baseline template by
    write_block_file."""
    merged = dict(overrides)
    merged.update(local_layer)
    merged.update(identity_fields)
    return merged


def _format_cube_value(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if "'" in text:
        raise ControlCenterError(
            f"value {text!r} contains a single quote, which Cube's block format "
            "has no escape sequence for."
        )
    return f"'{text}'"


def _format_line(indent: str, key: str, value, comment: str | None) -> str:
    line = f"{indent}{key} = {_format_cube_value(value)}"
    return f"{line}  {comment}" if comment else line


def render_assignment_lines(overrides: dict, indent: str = "    ") -> list:
    """Formats a dict of key/values as standalone Cube block 'KEY = value'
    lines, no comments. Used both for write_block_file()'s extra-keys section
    below and by general_parameters.py's standalone GeneralParameters.block
    override file, which has no baseline template to preserve lines from at
    all."""
    return [_format_line(indent, key, value, None) for key, value in overrides.items()]


def write_block_file(baseline_path: Path, overrides: dict, output_path: Path):
    """Writes output_path as a full copy of the baseline template at
    baseline_path, substituting the value of every line whose key appears in
    `overrides` and leaving every other line -- including comments, blank
    lines, and non-assignment statements -- byte-for-byte unchanged. Any
    override key with no matching line in the template is appended at the
    end under a clearly labeled section."""
    lines = _parse_lines(baseline_path)
    applied = set()
    out_lines = []
    for line in lines:
        if isinstance(line, _Assignment) and line.key in overrides:
            out_lines.append(_format_line(line.indent, line.key, overrides[line.key], line.comment))
            applied.add(line.key)
        elif isinstance(line, _Assignment):
            out_lines.append(line.raw)
        else:
            out_lines.append(line)

    extra = {k: v for k, v in overrides.items() if k not in applied}
    if extra:
        out_lines.append("")
        out_lines.append(";--- keys set by the orchestrator, not present in the baseline template ---")
        out_lines.extend(render_assignment_lines(extra))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="\r\n") as f:
        f.write("\n".join(out_lines) + "\n")
