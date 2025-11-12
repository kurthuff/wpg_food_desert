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


