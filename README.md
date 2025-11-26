## Project Structure and Usage

```text
data/
├── raw/
├── interim/
├── processed/
├── reference/
outputs/
├── rasters/
├── mapping/
└── reports/
scripts/
src/ag_res/
logs/
```

## Running Scripts

```bash
python scripts/<script_name>.py
```

## Path Handling

Paths are managed through `src/food_desert/paths.py` to keep file access consistent and portable.

```python
from food_desert import paths

input_csv = paths.raw() / f"example_data.csv"
output_tif = paths.rasters() / f"example_raster.tif"
```

## Data Sources

1) City of Winnipeg 'Assessment Parcels'
Used for notebook EDA, as well as mapping neighbourhood population to exact residential location. A further iteration of
this project would use the API, but for now I'll use static data downloaded on 11/12/2025.
https://data.winnipeg.ca/Assessment-Taxation-Corporate/Assessment-Parcels/d4mq-wa44/about_data

2) City of Winnipeg 'Map of Road Network'
Used later in the project to determine disatnce along roads to nearest supermarket. Roads are assumed to have sidewalks.
A further iteration of the project can use the API, but for this iteration a static download on 11/12/2025 is used.
https://data.winnipeg.ca/City-Planning/Map-of-Road-Network/2eba-wm4h

3) OpenStreetMaps 'supermarket API query'
*DEPRECATED*; too many formatting and query errors to be reliable.
Used to locate supermarkets in Winnipeg, this queries the Overpass API, and by running pull_osm_supermarkets.py, saves
data/reference/winnipeg_supermarkets.geojson. This list of supermarkets is explored and cleaned in osm_eda.ipynb.

4) Company Websites
Used to build a reliable address inventory of supermarkets and large independent grocery stores.

5) 2021 Census Information for Winnipeg Neighbourhoods
The page linked below gives an alphabetical listing of Winnipeg's 2021 census data for neighbourhoods. I used this
data in a previous class project involving crime and bus data. Each neighbourhood linked page contains an .xlsx,
where I ran a script that collected the population number and appended it to a lookup table. Then, this neighbourhood
data was appended with the neighbourhood geometry multipolygon from City of Winnipeg Open Data Portal. This creates a
file /data/reference/neighbourhoods.csv folder. This original file was a pain to create.
https://legacy.winnipeg.ca/census/2021/Alpha/default.asp

## Scripts
in run order

1) pull_osm_supermarkets.py
*DEPRECATED* OpenStreetMaps no longer used in favour of manual data collection.
This queries the Overpass API, saving data/reference/winnipeg_supermarkets.geojson for further exploring and cleaning
before being used for the project.

2) attach_neighbourhoods_to_parcels.py
This file takes in /data/raw/Assessment_Parcels_20251112.csv or whichever dated file you grab from the Open Data portal,
and as well takes in /data/reference/neighbourhoods.csv. First, valid residential parcels are filtered from the
aggregate of all parcels, then the centroid lat and lon of each is computed to be inside one of the neighbourhoods
in the neighbourhoods.csv using its geometry column, being a multipolygon. population_id, geometry, name and population
fields are joined to the parcels dataframe, and then a mask is written out to data/interim/. The mask is a much smaller
file that can be re-read to the next script, instead of writing out another huge parcels dataset.

3) compute_residents.py
Each neighbourhood has its Total Living Area calculated, and each parcel gets a sqft weight of the total sqft neighbourhood
sum. The weight calculated against the population of the neighbourhood to calculate residents in the parcel. Those with <1
get 1. Then the remaining pop gets recalculated. This is iterative and is a bottom-up approach. It's more realistic to have
the residents per parcel level off as parcel sqft grows. Also outputs a mask, not the entire dataset.


