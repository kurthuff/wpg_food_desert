## Project Structure and Usage

```text
food_desert/              # project root
├── data/
│   ├── cache/
│   ├── raw/
│   ├── interim/
│   │   ├── geocode_audit/
│   ├── processed/
│   └── reference/
│       ├── qgis/
├── literature/
├── logs/
├── notebooks/
├── outputs/
│   ├── mapping/
│   ├── rasters/
│   └── reports/
├── scripts/
├── src/
│   └── food_desert/
├── README.md
└── requirements.txt

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

1) __City of Winnipeg 'Assessment Parcels'__<br>
Used for notebook EDA, as well as mapping neighbourhood population to exact residential location. A further iteration of
this project would use the API, but for now I'll use static data downloaded on 11/12/2025.<br>
https://data.winnipeg.ca/Assessment-Taxation-Corporate/Assessment-Parcels/d4mq-wa44/about_data

2) __City of Winnipeg 'Map of Road Network'__<br>
Used later in the project to determine disatnce along roads to nearest grocer. Roads are assumed to have sidewalks.
A further iteration of the project can use the API, but for this iteration a static download on 11/12/2025 is used.<br>
https://data.winnipeg.ca/City-Planning/Map-of-Road-Network/2eba-wm4h

3) __OpenStreetMaps 'supermarket API query'__<br>
*NO LONGER USED*; too many formatting and query errors to be reliable.
Used to locate supermarkets in Winnipeg, this queries the Overpass API, and by running pull_osm_supermarkets.py, saves
data/reference/winnipeg_supermarkets.geojson. This list of supermarkets is explored and cleaned in osm_eda.ipynb.

4) __Company Websites with geocode__<br>
Used to build a reliable address inventory of supermarkets and large independent grocery stores. Using QGIS and the
MMQGIS plugin, I chose 'Geocode CSV with Web Service', specifying the fields needed. Used OpenStreetMaps/Nomanatim
as Web Service. This creates lat and lon fields using addresses.

5) __2021 Census Information for Winnipeg Neighbourhoods__<br>
The page linked below gives an alphabetical listing of Winnipeg's 2021 census data for neighbourhoods. I used this
data in a previous class project involving crime and bus data. Each neighbourhood linked page contains an .xlsx,
where I ran a script that collected the population number and appended it to a lookup table. Then, this neighbourhood
data was appended with the neighbourhood geometry multipolygon from City of Winnipeg Open Data Portal. This creates a
file /data/reference/neighbourhoods.csv folder. This original file was a pain to create.<br>
https://legacy.winnipeg.ca/census/2021/Alpha/default.asp

6) __2021 Winnipeg Household Data__<br>
The page linked is used in Winnipeg's own 2025 Housing Needs Assessment report. The data source is through the Canada
Mortgage and Housing Corporation, and it's source is 'CMHC, adapted from Statistics Canada (National Household Survey)'
It provides a way to create an algorithm to map residential parcel units which takes into account the different distributions
of 1-to-5 resident households dependent on the type of property. This helps create a more defensible resident allotment
within neighbourhoods. I'll probably reiterate on this synthetic resident distribution technique as I do more analysis.
See 'Intelligent Dasymetric Mapping and Its Application to Areal Interpolation' (Mennis and Hultgren, 2006) for more information.
https://www03.cmhc-schl.gc.ca/hmip-pimh/en#Profile/4611040/4/Winnipeg%20(CY)

## Scripts

In run order:

1) __pull_osm_supermarkets.py__<br>
_NO LONGER USED_<br>
OpenStreetMaps no longer used in favour of manual data collection.
This queries the Overpass API, saving data/reference/winnipeg_supermarkets.geojson for further exploring and cleaning
before being used for the project.

2) __attach_neighbourhoods_to_parcels.py__<br>
This file takes in /data/raw/Assessment_Parcels_20251112.csv (or whichever dated file you grab from the Open
Data portal) and /data/reference/neighbourhoods.csv. Valid residential parcels are filtered based on Dwelling Units > 0,
which ensures apartment buildings are included (unlike the previous Total Living Area filter that excluded buildings
without square footage data). The centroid lat/lon of each parcel is spatially joined to determine which neighbourhood
polygon it falls within. The neighbourhood_id, name, and population fields are appended to the parcels dataframe, and
a mask is written to data/interim/. This mask is much smaller than the full parcels dataset and can be efficiently read
by subsequent scripts.

3) __compute_residents.py__<br>
This script allocates neighbourhood census population to individual parcels using empirically-derived household size
distributions. Parcels are first classified as owner-occupied or renter-occupied based on Property Use Code (e.g.,
single-family homes vs. apartments). The CMHC 2021 household size distribution percentages are then applied to calculate
expected population by household type (1-person, 2-person, etc.) for each tenure category. These raw population values
are scaled proportionally to match the neighbourhood's actual census population. Finally, household sizes are
probabilistically assigned to parcels proportional to their Dwelling Units, ensuring every parcel receives at least 1
resident. This approach reflects real-world variation in household composition (1-5+ persons) while preserving exact 
neighbourhood population totals. Outputs a mask file.

4) __make_grocer_points.py__<br>
Using the output from QGIS and the plugin MMQGIS to add geocode to raw_grocer_addresses.csv, this script creates a .csv,
.geojson, and .html in data/interim/geocode_audit. Using the .html, I can manually check if there lat/lon are correct as
generated by MMQGIS. If they aren't, I update them using google maps. The script asks if I'm happy with
grocers.csv. If I type 'n' into the terminal, it rereads my updates to grocers.csv, regenerates the .geojson and .html,
and I check again. Once I'm happy, I type 'y' and it writes the audited locations back to reference.

5) __compute_nearest_grocer.py__<br>
Using the assessment parcels data for location, the parcel_residents_mask.csv to only calculate those residential parcels
of interest, and the final, audited grocers.geojson grocer locations, this calculates the nearest grocer to each parcel.
Output is a mask that can be joined with assessment parcel data for more information. This is an 'as the crow flies'
distance, effectively Euclidian (technically geodesic since it's on the Earth sphere).

6) __compute_nearest_grocer_path.py__<br>
This script using the road network data to snap parcels and grocers to the nearest line geometry, and then finds the
nearest parcel to grocer path. The result is mixed; some paths end up being unreasonably long, while others, due
to the snapping to lines, are shorter than the Euclidean path (can't happen). So, while I leave this script and it's
mask in the repo, I won't be using it for analysis.

7) __add_poverty_to_neighbourhoods.py__<br>
_Used conditionally to gather census data_<br>
This script builds off of my original neighbourhood aggregation process from an old project. It takes in all of the
.xlsx census files from 2021 census that the City of Winnipeg bought from Stats Canada, and extracts poverty data.
I will probably have more scripts like this as I dig deeper. Keep in mind that my repo ignores those .xlsx files,
and this script won't work without them.

