# scripts/aggregate_parcels_by_geometry.py

import sys
from pathlib import Path
import pandas as pd
import numpy as np

project_root = Path("/Users/dpro/projects/food_desert")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from food_desert import paths  # noqa: F401


def load_data(parcels_path: Path, mask_path: Path) -> pd.DataFrame:
    """Load parcels and merge with resident mask."""
    parcels = pd.read_csv(parcels_path, low_memory=False)
    mask = pd.read_csv(mask_path)
    
    # Merge to get residents column and filter to residential parcels only
    df = parcels.merge(mask[['Roll Number', 'residents']], on='Roll Number', how='inner')
    return df


def clean_numeric(series, col_name):
    """Clean numeric columns by removing commas."""
    if col_name in ['Total Living Area', 'Total Assessed Value', 'Total Proposed Assessment Value']:
        vals = series.astype(str).str.replace(',', '').str.replace('$', '').str.replace(' ', '').replace('', np.nan)
        return pd.to_numeric(vals, errors='coerce')
    return pd.to_numeric(series, errors='coerce')


def aggregate_by_geometry(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate parcels with identical geometry."""
    
    # Define aggregation rules
    sum_cols = [
        'residents',
        'Dwelling Units', 
        'Total Living Area',
        'Rooms',
        'Total Assessed Value',
        'Total Proposed Assessment Value'
    ]
    
    # Columns that must be identical or will be dropped
    identical_cols = [
        'Centroid Lat',
        'Centroid Lon',
        'neighbourhood_id',
        'name',
        'population',
        'Year Built',
        'Neighbourhood Area',
        'Number Floors (Condo)',
        'Assessed Land Area',
        'Street Number',
        'Street Name',
        'Street Type',
        'Street Direction',
        'Street Suffix',
        'Air Conditioning',
        'Fire Place',
        'Attached Garage',
        'Detached Garage',
        'Pool',
        'Building Type',
        'Basement',
        'Basement Finish',
        'Water Frontage Measurement',
        'Sewer Frontage Measurement',
        'Market Region',
        'GISID'
    ]
    
    # Concatenate unique values
    concat_cols = [
        'Unit Number',
        'Property Influences',
        'Property Use Code',
        'Zoning'
    ]
    
    # Group by geometry
    grouped = df.groupby('Geometry')
    
    results = []
    
    for geom, group in grouped:
        record = {'Geometry': geom}
        
        # Keep first Roll Number (or last - doesn't matter as long as it matches geometry)
        record['Roll Number'] = group['Roll Number'].iloc[0]
        
        # Aggregated roll numbers as CSV string
        record['aggregated_roll_numbers'] = ', '.join(group['Roll Number'].astype(str))
        
        # Count of parcels
        record['parcel_count'] = len(group)
        
        # Sum columns
        for col in sum_cols:
            if col in group.columns:
                vals = clean_numeric(group[col], col)
                record[col] = vals.sum()
        
        # Identical columns - drop if any conflict
        for col in identical_cols:
            if col in group.columns:
                unique_vals = group[col].dropna().unique()
                if len(unique_vals) == 1:
                    record[col] = unique_vals[0]
                elif len(unique_vals) == 0:
                    record[col] = np.nan
                # else: don't add to record (will be missing/dropped)
        
        # Concatenate columns
        for col in concat_cols:
            if col in group.columns:
                unique_vals = group[col].dropna().astype(str).unique()
                unique_vals = [v for v in unique_vals if v not in ['', 'nan', 'None']]
                if len(unique_vals) > 0:
                    record[col] = ', '.join(unique_vals)
                else:
                    record[col] = np.nan
        
        results.append(record)
    
    result_df = pd.DataFrame(results)
    return result_df


def main() -> None:
    parcels_path = project_root / "data" / "raw" / "Assessment_Parcels_20251112.csv"
    mask_path = project_root / "data" / "interim" / "parcel_residents_mask.csv"
    out_path = project_root / "data" / "processed" / "aggregated_parcels_by_geometry.csv"
    
    print("Loading data...")
    df = load_data(parcels_path, mask_path)
    print(f"Loaded {len(df):,} parcels")
    
    print("\nAggregating by geometry...")
    result = aggregate_by_geometry(df)
    print(f"Aggregated to {len(result):,} unique geometries")
    
    print("\nSaving result...")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_path, index=False)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()






