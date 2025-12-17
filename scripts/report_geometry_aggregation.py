# scripts/report_geometry_aggregation.py

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

project_root = Path("/Users/dpro/projects/food_desert")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from food_desert import paths  # noqa: F401


def main() -> None:
    mask_path = project_root / "data" / "interim" / "parcel_residents_mask.csv"
    agg_path = project_root / "data" / "processed" / "aggregated_parcels_by_geometry.csv"
    output_path = project_root / "outputs" / "reports" / "geometry_aggregation_report.txt"
    
    mask = pd.read_csv(mask_path)
    agg = pd.read_csv(agg_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        # Header
        f.write("=" * 100 + "\n")
        f.write("WINNIPEG PARCEL GEOMETRY AGGREGATION REPORT\n")
        f.write("Residential Parcels Grouped by Identical Geographic Location\n")
        f.write("=" * 100 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Data Sources: parcel_residents_mask.csv, Assessment_Parcels_20251112.csv\n\n")
        
        # Executive Summary
        f.write("EXECUTIVE SUMMARY\n")
        f.write("-" * 100 + "\n")
        f.write(f"Original residential parcels:     {len(mask):>10,}\n")
        f.write(f"Unique geographic locations:      {len(agg):>10,}\n")
        f.write(f"Parcels aggregated:               {len(mask) - len(agg):>10,} ({100 * (len(mask) - len(agg)) / len(mask):>5.1f}%)\n\n")
        
        f.write("Note: Multiple parcels at the same geographic location (e.g., individual condo units\n")
        f.write("      within a building) have been aggregated into single records. Resident totals and\n")
        f.write("      dwelling unit counts are summed; other attributes retain values only if identical\n")
        f.write("      across all parcels at that location.\n\n")
        
        # Parcel Count Distribution
        f.write("\n" + "=" * 100 + "\n")
        f.write("PARCEL COUNT DISTRIBUTION\n")
        f.write("=" * 100 + "\n\n")
        
        parcel_counts = agg['parcel_count'].value_counts().sort_index()
        f.write("Parcels per Geographic Location:\n")
        f.write("-" * 100 + "\n")
        
        for count, freq in parcel_counts.head(20).items():
            pct = 100 * freq / len(agg)
            f.write(f"  {count:3d} parcel(s):  {freq:>8,} locations  ({pct:>5.1f}%)\n")
        
        if len(parcel_counts) > 20:
            remaining_counts = parcel_counts.iloc[20:]
            remaining_total = remaining_counts.sum()
            f.write(f"  ... ({len(parcel_counts) - 20} more categories covering {remaining_total:,} locations)\n")
        
        f.write(f"\nMaximum parcels in single location: {agg['parcel_count'].max():,}\n")
        
        multi_parcel = agg[agg['parcel_count'] > 1]
        f.write(f"Locations with multiple parcels:     {len(multi_parcel):>8,} ({100 * len(multi_parcel) / len(agg):>5.1f}%)\n")
        f.write(f"Locations with single parcel:        {len(agg) - len(multi_parcel):>8,} ({100 * (len(agg) - len(multi_parcel)) / len(agg):>5.1f}%)\n")
        
        # Resident Statistics
        f.write("\n" + "=" * 100 + "\n")
        f.write("RESIDENT STATISTICS\n")
        f.write("=" * 100 + "\n\n")
        
        f.write(f"Total residents (original):       {mask['residents'].sum():>10,}\n")
        f.write(f"Total residents (aggregated):     {agg['residents'].sum():>10,}\n")
        f.write(f"Difference:                       {abs(mask['residents'].sum() - agg['residents'].sum()):>10,}\n\n")
        
        f.write("Resident Distribution (Aggregated):\n")
        f.write("-" * 100 + "\n")
        f.write(f"  Minimum:      {agg['residents'].min():>8.0f}\n")
        f.write(f"  25th %ile:    {agg['residents'].quantile(0.25):>8.0f}\n")
        f.write(f"  Median:       {agg['residents'].median():>8.0f}\n")
        f.write(f"  75th %ile:    {agg['residents'].quantile(0.75):>8.0f}\n")
        f.write(f"  Maximum:      {agg['residents'].max():>8.0f}\n")
        f.write(f"  Mean:         {agg['residents'].mean():>8.1f}\n")
        
        # Dwelling Units Statistics
        f.write("\n" + "=" * 100 + "\n")
        f.write("DWELLING UNITS STATISTICS\n")
        f.write("=" * 100 + "\n\n")
        
        f.write(f"Total dwelling units (original):  {mask['Dwelling Units'].sum():>10,.0f}\n")
        f.write(f"Total dwelling units (aggregated):{agg['Dwelling Units'].sum():>10,.0f}\n\n")
        
        f.write("Dwelling Units Distribution (Aggregated):\n")
        f.write("-" * 100 + "\n")
        f.write(f"  Minimum:      {agg['Dwelling Units'].min():>8.0f}\n")
        f.write(f"  25th %ile:    {agg['Dwelling Units'].quantile(0.25):>8.0f}\n")
        f.write(f"  Median:       {agg['Dwelling Units'].median():>8.0f}\n")
        f.write(f"  75th %ile:    {agg['Dwelling Units'].quantile(0.75):>8.0f}\n")
        f.write(f"  Maximum:      {agg['Dwelling Units'].max():>8.0f}\n")
        f.write(f"  Mean:         {agg['Dwelling Units'].mean():>8.1f}\n")
        
        # Column Retention
        f.write("\n" + "=" * 100 + "\n")
        f.write("COLUMN RETENTION ANALYSIS\n")
        f.write("=" * 100 + "\n\n")
        
        f.write(f"Total columns in aggregated dataset: {len(agg.columns)}\n\n")
        
        f.write("Columns with Missing Values (Conflicting Data Dropped):\n")
        f.write("-" * 100 + "\n")
        
        missing = agg.isnull().sum()
        missing = missing[missing > 0].sort_values(ascending=False)
        
        if len(missing) > 0:
            for col, count in missing.items():
                pct = 100 * count / len(agg)
                f.write(f"  {col:<50s} {count:>8,} missing  ({pct:>5.1f}%)\n")
        else:
            f.write("  (none - all columns fully populated)\n")
        
        # Top 10 Highest Resident Counts
        f.write("\n" + "=" * 100 + "\n")
        f.write("TOP 10 HIGHEST RESIDENT COUNTS\n")
        f.write("=" * 100 + "\n\n")
        
        display_cols = ['Roll Number', 'residents', 'Dwelling Units', 'parcel_count']
        optional_cols = ['Street Number', 'Street Name', 'Street Type']
        
        for col in optional_cols:
            if col in agg.columns:
                display_cols.append(col)
        
        top10 = agg.nlargest(10, 'residents')[display_cols].copy()
        
        # Format for better display
        top10['residents'] = top10['residents'].apply(lambda x: f"{x:,.0f}")
        top10['Dwelling Units'] = top10['Dwelling Units'].apply(lambda x: f"{x:,.0f}")
        
        f.write(top10.to_string(index=False) + "\n")
        
        f.write("\n" + "=" * 100 + "\n")
        f.write("METHODOLOGY\n")
        f.write("=" * 100 + "\n\n")
        
        f.write("Aggregation Rules:\n\n")
        f.write("1. SUMMED: residents, Dwelling Units, Total Living Area, Rooms, Total Assessed Value\n\n")
        f.write("2. RETAINED IF IDENTICAL (dropped if conflicting): Property Use Code, Year Built,\n")
        f.write("   Street Number, Street Name, Air Conditioning, Fire Place, Building Type, and all\n")
        f.write("   other descriptive attributes\n\n")
        f.write("3. CONCATENATED: Unit Number, Property Influences (comma-separated lists)\n\n")
        f.write("4. NEW COLUMNS: parcel_count (number of parcels aggregated), aggregated_roll_numbers\n")
        f.write("   (comma-separated list of all Roll Numbers at this location)\n\n")
        f.write("Purpose: Enables accurate 3D visualization by preventing visual overlap of co-located\n")
        f.write("         parcels (e.g., individual condo units) while preserving total population counts.\n\n")
        
        f.write("=" * 100 + "\n")
    
    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()