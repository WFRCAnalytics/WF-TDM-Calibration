"""WFRC chart helpers for Python (matplotlib, plotly).

    import sys; sys.path.append("_extensions/WFRCAnalytics/wfrc-brand/assets/charts")
    import wfrc_charts as wfrc
    wfrc.use_style()               # matplotlib; pass mode="dark" for dark pages
    fig = go.Figure(layout=dict(template=wfrc.plotly_template()))   # plotly

Colors are read from brand.yml, so there is one source of truth. Use at most five
categories, in this order. Gold (series 4) is below 3:1 on white: label series directly.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# The second is where `quarto add` installs it; the third is a copy placed by hand without the owner folder.
_CANDIDATES = ("_brand.yml", "_extensions/WFRCAnalytics/wfrc-brand/brand.yml", "_extensions/wfrc-brand/brand.yml")


def _brand_file(path: str | Path | None = None) -> Path:
    if path:
        return Path(path)
    here = Path.cwd().resolve()
    for folder in [here, *here.parents]:
        for rel in _CANDIDATES:
            candidate = folder / rel
            if candidate.exists():
                return candidate
    raise FileNotFoundError("brand.yml not found; pass path= to colors()")


def colors(path: str | Path | None = None) -> dict[str, str]:
    """Every palette color in brand.yml as {name: '#RRGGBB'}, with aliases resolved."""
    with open(_brand_file(path), encoding="utf-8") as f:
        raw = yaml.safe_load(f)["color"]["palette"]

    def resolve(name: str) -> str:
        value = raw[name]
        return resolve(value) if value in raw else str(value).upper()

    return {name: resolve(name) for name in raw}


def palette(n: int = 5, mode: str = "light", path: str | Path | None = None) -> list[str]:
    """The categorical chart colors for a mode, in fixed order (at most five)."""
    if n > 5:
        raise ValueError("WFRC charts use at most five categories; facet or group the rest as 'Other'.")
    pal = colors(path)
    suffix = "-dark" if mode == "dark" else ""
    return [pal[f"chart-{i}{suffix}"] for i in range(1, n + 1)]


def _roles(mode: str, path=None) -> dict[str, str]:
    pal = colors(path)
    dark = mode == "dark"
    return {
        "ink": pal["wfrc-snow" if dark else "wfrc-ink"],
        "soft": pal["wfrc-snow-soft" if dark else "wfrc-ink-soft"],
        "line": pal["wfrc-night-line" if dark else "wfrc-hairline"],
        "head": pal["wfrc-ice" if dark else "wfrc-navy"],
    }


def _font_stack() -> list[str]:
    """Inter when installed, otherwise matplotlib's default sans, without findfont warnings."""
    from matplotlib import font_manager

    installed = {f.name for f in font_manager.fontManager.ttflist}
    return ["Inter"] if "Inter" in installed else ["DejaVu Sans"]


def use_style(mode: str = "light", path=None) -> None:
    """Apply the WFRC look to matplotlib: hairline grid, ink text, transparent figure."""
    import matplotlib as mpl
    from cycler import cycler

    r = _roles(mode, path)
    mpl.rcParams.update({
        "axes.prop_cycle": cycler(color=palette(5, mode, path)),
        "figure.facecolor": "none",
        "axes.facecolor": "none",
        "savefig.facecolor": "none",
        "text.color": r["ink"],
        "axes.labelcolor": r["ink"],
        "axes.titlecolor": r["head"],
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "xtick.color": r["soft"],
        "ytick.color": r["soft"],
        "axes.edgecolor": r["line"],
        "axes.grid": True,
        "grid.color": r["line"],
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "font.family": _font_stack(),
    })


def plotly_template(mode: str = "light", path=None) -> dict:
    """A plotly layout template as a plain dict (plotly is not imported here)."""
    r = _roles(mode, path)
    return {
        "layout": {
            "colorway": palette(5, mode, path),
            "font": {"family": "Inter, sans-serif", "color": r["ink"]},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "title": {"font": {"color": r["head"]}, "x": 0},
            "xaxis": {"gridcolor": r["line"], "linecolor": r["line"], "tickfont": {"color": r["soft"]}},
            "yaxis": {"gridcolor": r["line"], "linecolor": r["line"], "tickfont": {"color": r["soft"]}},
            "legend": {"orientation": "h", "y": 1.08},
        }
    }
