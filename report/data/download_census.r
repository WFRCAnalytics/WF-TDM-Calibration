# 1. Define all required packages in one place
packages <- c("dplyr", "tidycensus", "sf", "rstudioapi", "tigris")

# 2. Loop through them: install if missing, then load
for (pkg in packages) {
  if (!require(pkg, character.only = TRUE)) {
    install.packages(pkg)
    library(pkg, character.only = TRUE)
  }
}

options(tigris_use_cache = TRUE)

# --- Define Core Variables ---
target_state <- "UT"
target_counties <- c("Box Elder", "Weber", "Davis", "Salt Lake", "Utah")
target_year <- 2023

# --- 1. Download County and Places Boundaries First ---
# Get counties first so they can be used as a spatial filter below
ut_counties <- tigris::counties(
  state = target_state,
  year = target_year,
  cb = TRUE
) |>
  dplyr::filter(NAME %in% target_counties)

# Get all places, then spatially filter to only those intersecting our 5 counties
ut_places <- tigris::places(
  state = target_state,
  year = target_year,
  cb = TRUE
) |>
  sf::st_filter(ut_counties, .predicate = sf::st_intersects)

# --- 2. Download Tract Data (Detailed Cross-tabs) ---
acs_vehown_tract <- tidycensus::get_acs(
  geography = "tract",
  table = "B08201",
  cache_table = TRUE,
  year = target_year,
  output = "wide",
  state = target_state,
  county = target_counties,
  survey = "acs5",
  geometry = TRUE
)

# --- 3. Download Place Data (for accurate city-level comparison) ---
# BG-centroid-to-city spatial joins miss households in BGs that straddle city
# boundaries. Using the Census pre-tabulated place-level data avoids this.
# Filtered to places intersecting the 5-county study area after downloading.
acs_vehown_place <- tidycensus::get_acs(
  geography = "place",
  table = "B08201",
  cache_table = TRUE,
  year = target_year,
  output = "wide",
  state = target_state,
  survey = "acs5",
  geometry = TRUE
) |>
  sf::st_filter(ut_counties, .predicate = sf::st_intersects)

# --- 4. Download Block Group Data (For Disaggregation Weights) ---
# B11001_001 represents Total Households
acs_hh_bg <- tidycensus::get_acs(
  geography = "block group",
  variables = c(Total_HH = "B11001_001"),
  cache_table = TRUE,
  year = target_year,
  output = "wide",
  state = target_state,
  county = target_counties,
  survey = "acs5",
  geometry = TRUE
)

# --- 5. Export data ---
# Get the directory of the currently active script
script_dir <- dirname(rstudioapi::getActiveDocumentContext()$path)
out_dir <- file.path(script_dir, "0-hhdisag-autoown")

# Create directory if it doesn't exist
if (!dir.exists(out_dir)) {
  dir.create(out_dir, recursive = TRUE)
}

# Export all layers as Geopackages
sf::write_sf(
  acs_vehown_tract,
  file.path(out_dir, "ACS5Y_2023_B08201_Tract.gpkg"),
  append = FALSE
)
sf::write_sf(
  acs_vehown_place,
  file.path(out_dir, "ACS5Y_2023_B08201_Place.gpkg"),
  append = FALSE
)
sf::write_sf(
  acs_hh_bg,
  file.path(out_dir, "ACS5Y_2023_B11001_BG.gpkg"),
  append = FALSE
)
sf::write_sf(
  ut_counties,
  file.path(out_dir, "Census_2023_Counties.gpkg"),
  append = FALSE
)
sf::write_sf(
  ut_places,
  file.path(out_dir, "Census_2023_Places.gpkg"),
  append = FALSE
)

print("Data download and export complete!")
