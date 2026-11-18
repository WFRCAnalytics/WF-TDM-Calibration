# WFRC chart helpers for R (ggplot2).
#
#   source("_extensions/WFRCAnalytics/wfrc-brand/assets/charts/wfrc-charts.R")
#   ggplot(df, aes(x, y, color = group)) + geom_line() + theme_wfrc() + scale_color_wfrc()
#
# Colors are read from brand.yml, so there is one source of truth. Use at most five
# categories, in this order. Gold (series 4) is below 3:1 on white: label series directly.

.wfrc_brand_file <- function(path = NULL) {
  # `quarto add` installs under the owner folder; the flat "_extensions/wfrc-brand" is a copy placed by hand.
  rel <- c("_extensions/WFRCAnalytics/wfrc-brand/brand.yml", "_extensions/wfrc-brand/brand.yml")
  candidates <- c(path, "_brand.yml", rel, paste0("../", rel), paste0("../../", rel))
  hit <- candidates[!is.na(candidates) & file.exists(candidates)]
  if (!length(hit)) stop("brand.yml not found; pass path = to wfrc_colors()", call. = FALSE)
  hit[[1]]
}

# Reads the flat `palette:` block (name: "#hex" or name: other-name). No YAML package needed.
.wfrc_read_palette <- function(path = NULL) {
  lines <- readLines(.wfrc_brand_file(path), warn = FALSE, encoding = "UTF-8")
  in_palette <- FALSE
  out <- character()
  alias <- character()
  for (ln in lines) {
    if (grepl("^\\s{2}palette:\\s*$", ln)) { in_palette <- TRUE; next }
    if (in_palette && grepl("^\\s{2}[A-Za-z]", ln)) break # next key under `color:`
    if (!in_palette) next
    m <- regmatches(ln, regexec("^\\s{4}([A-Za-z0-9_-]+):\\s*\"(#[0-9A-Fa-f]{6})\"", ln))[[1]]
    if (length(m)) { out[m[2]] <- toupper(m[3]); next }
    a <- regmatches(ln, regexec("^\\s{4}([A-Za-z0-9_-]+):\\s*([A-Za-z0-9_-]+)\\s*(#.*)?$", ln))[[1]]
    if (length(a)) alias[a[2]] <- a[3]
  }
  for (k in names(alias)) if (alias[[k]] %in% names(out)) out[k] <- out[[alias[[k]]]]
  out
}

#' Named vector of every brand.yml palette color.
wfrc_colors <- function(path = NULL) .wfrc_read_palette(path)

#' The categorical chart colors for a mode, in fixed order (at most five).
wfrc_palette <- function(n = 5, mode = c("light", "dark"), path = NULL) {
  mode <- match.arg(mode)
  if (n > 5) {
    stop("WFRC charts use at most five categories; facet or group the rest as 'Other'.", call. = FALSE)
  }
  pal <- wfrc_colors(path)
  keys <- paste0("chart-", 1:5, if (mode == "dark") "-dark" else "")
  unname(pal[keys][seq_len(n)])
}

scale_color_wfrc <- function(mode = c("light", "dark"), ...) {
  mode <- match.arg(mode)
  ggplot2::scale_color_manual(values = wfrc_palette(5, mode), ...)
}
scale_colour_wfrc <- scale_color_wfrc

scale_fill_wfrc <- function(mode = c("light", "dark"), ...) {
  mode <- match.arg(mode)
  ggplot2::scale_fill_manual(values = wfrc_palette(5, mode), ...)
}

#' A quiet ggplot2 theme: hairline grid, ink text, transparent background.
theme_wfrc <- function(base_size = 12, mode = c("light", "dark"), base_family = "", path = NULL) {
  mode <- match.arg(mode)
  pal <- wfrc_colors(path)
  dark <- mode == "dark"
  ink <- unname(pal[if (dark) "wfrc-snow" else "wfrc-ink"])
  soft <- unname(pal[if (dark) "wfrc-snow-soft" else "wfrc-ink-soft"])
  line <- unname(pal[if (dark) "wfrc-night-line" else "wfrc-hairline"])
  head <- unname(pal[if (dark) "wfrc-ice" else "wfrc-navy"])
  ggplot2::theme_minimal(base_size = base_size, base_family = base_family) +
    ggplot2::theme(
      text = ggplot2::element_text(color = ink),
      plot.title = ggplot2::element_text(face = "bold", color = head, size = ggplot2::rel(1.25)),
      plot.subtitle = ggplot2::element_text(color = soft),
      plot.caption = ggplot2::element_text(color = soft, hjust = 0),
      plot.title.position = "plot",
      axis.text = ggplot2::element_text(color = soft),
      axis.title = ggplot2::element_text(color = ink),
      panel.grid.major = ggplot2::element_line(color = line, linewidth = 0.4),
      panel.grid.minor = ggplot2::element_blank(),
      legend.position = "top",
      legend.title = ggplot2::element_blank(),
      plot.background = ggplot2::element_rect(fill = NA, color = NA),
      panel.background = ggplot2::element_rect(fill = NA, color = NA)
    )
}
