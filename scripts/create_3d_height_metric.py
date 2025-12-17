# scripts/create_3d_height_metric.py

import sys
from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely import wkt
import numpy as np

project_root = Path("/Users/dpro/projects/food_desert")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from food_desert import paths  # noqa: F401


def load_aggregated_parcels(csv_path: Path) -> gpd.GeoDataFrame:
    """Load aggregated parcels and convert to GeoDataFrame."""
    df = pd.read_csv(csv_path)
    
    # Parse WKT geometry
    df['geometry'] = df['Geometry'].apply(
        lambda x: wkt.loads(x) if isinstance(x, str) and x.strip() else None
    )
    
    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    
    return gdf


def calculate_area_and_height_metric(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Calculate parcel area and height metric for 3D visualization.
    
    Height metric = residents / area (resident density)
    This normalizes for parcel footprint size.
    """
    gdf = gdf.copy()
    
    # Reproject to UTM Zone 14N (EPSG:26914) for accurate area calculation
    # Winnipeg is in UTM Zone 14N
    gdf_proj = gdf.to_crs(epsg=26914)
    
    # Calculate area in square meters
    gdf['area_m2'] = gdf_proj.geometry.area
    
    # Calculate height metric: residents per square meter
    # This will be very small, so we'll also create scaled versions
    gdf['resident_density'] = gdf['residents'] / gdf['area_m2']
    
    # Handle division by zero or missing area
    gdf['resident_density'] = gdf['resident_density'].replace([np.inf, -np.inf], np.nan)
    
    # Create scaled versions for visualization
    # Scale 1: multiply by 100 (residents per 100 m²)
    gdf['height_metric_100m2'] = gdf['resident_density'] * 100
    
    # Scale 2: multiply by 1000 (residents per 1000 m²)
    gdf['height_metric_1000m2'] = gdf['resident_density'] * 1000
    
    # Scale 3: square root transformation to compress extreme values
    gdf['height_metric_sqrt'] = np.sqrt(gdf['resident_density'] * 1000)
    
    # Scale 4: log transformation (good for wide range compression)
    # Add 1 to avoid log(0)
    gdf['height_metric_log'] = np.log10((gdf['resident_density'] * 1000) + 1)
    
    return gdf


def main() -> None:
    agg_path = project_root / "data" / "processed" / "aggregated_parcels_by_geometry.csv"
    
    # Output paths
    out_csv = project_root / "data" / "processed" / "aggregated_parcels_3d_ready.csv"
    out_geojson = project_root / "data" / "processed" / "aggregated_parcels_3d_ready.geojson"
    out_shp = project_root / "data" / "processed" / "aggregated_parcels_3d_ready.shp"
    
    print("Loading aggregated parcels...")
    gdf = load_aggregated_parcels(agg_path)
    print(f"Loaded {len(gdf):,} parcels")
    
    print("\nCalculating area and height metrics...")
    gdf = calculate_area_and_height_metric(gdf)
    
    print("\nHeight metric statistics:")
    print(f"  Resident density (per m²):")
    print(f"    Min:    {gdf['resident_density'].min():.6f}")
    print(f"    Median: {gdf['resident_density'].median():.6f}")
    print(f"    Max:    {gdf['resident_density'].max():.6f}")
    
    print(f"\n  Height metric (per 100 m²):")
    print(f"    Min:    {gdf['height_metric_100m2'].min():.3f}")
    print(f"    Median: {gdf['height_metric_100m2'].median():.3f}")
    print(f"    Max:    {gdf['height_metric_100m2'].max():.3f}")
    
    print(f"\n  Height metric (per 1000 m²):")
    print(f"    Min:    {gdf['height_metric_1000m2'].min():.3f}")
    print(f"    Median: {gdf['height_metric_1000m2'].median():.3f}")
    print(f"    Max:    {gdf['height_metric_1000m2'].max():.3f}")
    
    print(f"\n  Height metric (sqrt scale):")
    print(f"    Min:    {gdf['height_metric_sqrt'].min():.3f}")
    print(f"    Median: {gdf['height_metric_sqrt'].median():.3f}")
    print(f"    Max:    {gdf['height_metric_sqrt'].max():.3f}")
    
    print(f"\n  Height metric (log scale):")
    print(f"    Min:    {gdf['height_metric_log'].min():.3f}")
    print(f"    Median: {gdf['height_metric_log'].median():.3f}")
    print(f"    Max:    {gdf['height_metric_log'].max():.3f}")
    
    print("\nSaving outputs...")
    
    # CSV (drop geometry for cleaner CSV)
    csv_df = gdf.drop(columns=['geometry'])
    csv_df.to_csv(out_csv, index=False)
    print(f"  CSV:     {out_csv}")
    
    # GeoJSON (for web mapping or QGIS)
    gdf.to_file(out_geojson, driver='GeoJSON')
    print(f"  GeoJSON: {out_geojson}")
    
    # Shapefile (for ArcGIS Pro)
    # Note: Shapefile has column name length limits (10 chars)
    gdf_shp = gdf.copy()
    gdf_shp = gdf_shp.rename(columns={
        'height_metric_100m2': 'ht_100m2',
        'height_metric_1000m2': 'ht_1000m2',
        'height_metric_sqrt': 'ht_sqrt',
        'height_metric_log': 'ht_log',
        'resident_density': 'res_dens',
        'aggregated_roll_numbers': 'agg_rolls',
        'neighbourhood_id': 'neigh_id'
    })
    gdf_shp.to_file(out_shp, driver='ESRI Shapefile')
    print(f"  Shapefile: {out_shp}")
    
    print("\n" + "=" * 70)
    print("HEIGHT METRIC RECOMMENDATIONS FOR ARCGIS PRO:")
    print("=" * 70)
    print("\n1. height_metric_100m2 (ht_100m2 in shapefile):")
    print("   Use for: Standard visualization with interpretable units")
    print("   Range: Varies widely, may need manual scaling in ArcGIS")
    
    print("\n2. height_metric_1000m2 (ht_1000m2 in shapefile):")
    print("   Use for: Larger scale values, easier manual adjustment")
    print("   Range: 10x larger than 100m2 version")
    
    print("\n3. height_metric_sqrt (ht_sqrt in shapefile):")
    print("   Use for: Compressing extreme values while preserving differences")
    print("   Range: More balanced, reduces dominance of high-density towers")
    
    print("\n4. height_metric_log (ht_log in shapefile):")
    print("   Use for: Maximum compression, shows relative differences")
    print("   Range: Most compressed, all values visible")
    
    print("\nRecommendation: Start with height_metric_sqrt or height_metric_log")
    print("for best visual balance in 3D scenes.")
    print("=" * 70)


if __name__ == "__main__":
    main()