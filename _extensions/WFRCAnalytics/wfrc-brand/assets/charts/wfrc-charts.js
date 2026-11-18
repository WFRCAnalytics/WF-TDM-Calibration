// WFRC chart helpers for Observable JS (Observable Plot, d3).
//
//   ```{ojs}
//   import {wfrcColors, wfrcPlot} from "./_extensions/WFRCAnalytics/wfrc-brand/assets/charts/wfrc-charts.js"
//   wfrcPlot({Plot, marks: [Plot.lineY(data, {x: "date", y: "value", stroke: "mode"})]})
//   ```
//
// Colors are the --wfrc-chart-N CSS variables set by the theme, so charts follow light and dark
// mode on their own. Use at most five categories, in this order. Gold (series 4) is below 3:1 on
// white: label series directly.

const FALLBACK = ["#1479B8", "#D2582A", "#8A5FB0", "#D6A21E", "#1FA0A6"];

export function wfrcColors() {
  const css = getComputedStyle(document.documentElement);
  return FALLBACK.map((fallback, i) => css.getPropertyValue(`--wfrc-chart-${i + 1}`).trim() || fallback);
}

export function wfrcPlot({ Plot, color = {}, ...options } = {}) {
  const P = Plot ?? window.Plot;
  if (!P) throw new Error("Observable Plot is not loaded; pass it as {Plot}.");
  return P.plot({
    style: { fontFamily: "Inter, sans-serif", fontSize: "12px", background: "transparent" },
    color: { range: wfrcColors(), ...color },
    ...options,
  });
}

// ── Tooltips ─────────────────────────────────────────────────────────────────
// Observable Plot draws a tooltip as a white box. The theme repaints that box in the page colour (a CSS
// rule in wfrc-overrides.scss), so `tip: true` already reads in light and dark mode. What the theme
// cannot do is format numbers: a tooltip ignores the axis tickFormat and prints raw values (2041.3333),
// so format them here.
//
//   import {wfrcTip, tipFormat, wfrcPointerTip, wfrcStackTip} from "./_extensions/WFRCAnalytics/wfrc-brand/assets/charts/wfrc-charts.js"
//   Plot.dot(data, {x: "year", y: "trips", tip: wfrcTip.with({format: {y: tipFormat.compact}})})
//   wfrcPointerTip(Plot, data, {x: "year", y: "trips", title: d => `${d.year}: ${tipFormat.compact(d.trips)}`})

// The box takes the page colour; the outline and text take the page ink (both follow the mode).
export const wfrcTip = Object.assign(
  { fill: "var(--wfrc-bg, white)", stroke: "currentColor" },
  { with: (extra = {}) => ({ fill: "var(--wfrc-bg, white)", stroke: "currentColor", ...extra }) }
);

// Number formatters for a tip's `format` and `title`. No d3 import on purpose: an imported ES module
// cannot see the page's own d3 global.
const blank = v => v == null || Number.isNaN(v);
export const tipFormat = {
  number: (digits = 0) => v => blank(v) ? "–" : Number(v).toLocaleString("en-US", {minimumFractionDigits: digits, maximumFractionDigits: digits}),
  percent: (digits = 1) => v => blank(v) ? "–" : `${Number(v).toFixed(digits)}%`,
  dollars: v => blank(v) ? "–" : `${v < 0 ? "-" : ""}$${Math.abs(v).toLocaleString("en-US", {maximumFractionDigits: 0})}`,
  compact: v => {
    if (blank(v)) return "–";
    const a = Math.abs(v), sign = v < 0 ? "-" : "";
    if (a >= 1e9) return `${sign}${(a / 1e9).toFixed(1)}B`;
    if (a >= 1e6) return `${sign}${(a / 1e6).toFixed(1)}M`;
    if (a >= 1e3) return `${sign}${(a / 1e3).toFixed(1)}K`;
    return `${sign}${a.toLocaleString("en-US", {maximumFractionDigits: 1})}`;
  },
};

// A tooltip that follows the pointer, for marks with no tip of their own (lines, areas, bars on a band
// scale). mode: "x" nearest by x (time series, bars), "y" nearest by y (horizontal bars), "xy" 2-D.
export function wfrcPointerTip(Plot, data, { x, y, fx, fy, title, format, mode = "x", ...rest } = {}) {
  const P = Plot ?? window.Plot;
  const pointer = {x: P?.pointerX, y: P?.pointerY, xy: P?.pointer}[mode];
  if (!pointer) throw new Error(`wfrcPointerTip: needs Observable Plot 0.6.11 or later passed as {Plot}, and mode "x", "y" or "xy" (got "${mode}").`);
  return P.tip(data, pointer({
    x, y, ...(fx ? {fx} : {}), ...(fy ? {fy} : {}), ...(title ? {title} : {}), ...(format ? {format} : {}),
    ...wfrcTip.with(), ...rest,
  }));
}

// The same for a STACKED bar or area. Under pointerX every segment of a stack shares one x, so a tip at
// the segment's top edge cannot tell them apart; each row is placed at its segment's midpoint and a 2-D
// pointer picks the nearest. `order` lists the group values bottom to top, as the mark stacks them.
// Assumes the values in a stack have the same sign.
export function wfrcStackTip(Plot, data, { x, y, group, order, fx, title, format, ...rest } = {}) {
  const P = Plot ?? window.Plot;
  const rank = d => { const i = order.indexOf(d[group]); return i < 0 ? order.length : i; };
  const filled = new Map();
  const rows = [...data].sort((a, b) => rank(a) - rank(b)).map(d => {
    const key = `${fx ? d[fx] : ""}|${d[x]}`;
    const lo = filled.get(key) ?? 0, v = d[y] ?? 0;
    filled.set(key, lo + v);
    return {...d, _mid: lo + v / 2};
  });
  return P.tip(rows, P.pointer({
    x, y: "_mid", ...(fx ? {fx} : {}), ...(title ? {title} : {}), ...(format ? {format} : {}),
    ...wfrcTip.with(), maxRadius: 80, ...rest,
  }));
}
