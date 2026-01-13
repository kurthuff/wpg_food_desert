# scripts/compute_nearest_grocer_aggregated.py

import sys
from pathlib import Path

import pandas as pd
import geopandas as gpd
from shapely import wkt

project_root = Path("/Users/dpro/projects/food_desert")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from food_desert import paths  # noqa: F401


def load_aggregated_parcels(parcels_path: Path) -> pd.DataFrame:
    df = pd.read_csv(parcels_path)
    
    keep_cols = [
        "Roll Number",
        "Centroid Lat",
        "Centroid Lon",
        "Geometry",
        "neighbourhood_id",
        "name",
        "population",
        "residents",
        "Dwelling Units",
        "area_m2",
        "height_metric_100m2",
        "height_metric_1000m2",
        "height_metric_sqrt",
        "height_metric_log",
        "parcel_count",
        "aggregated_roll_numbers"
    ]
    keep_cols = [c for c in keep_cols if c in df.columns]

    df = df[keep_cols].copy()
    return df


def make_parcel_points(df: pd.DataFrame) -> gpd.GeoDataFrame:
    df = df.copy()

    if {"Centroid Lat", "Centroid Lon"}.issubset(df.columns):
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["Centroid Lon"], df["Centroid Lat"]),
            crs="EPSG:4326",
        )
        return gdf

    if "Geometry" in df.columns:
        df["geometry"] = df["Geometry"].apply(
            lambda x: wkt.loads(x) if isinstance(x, str) and x.strip() else None
        )
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        gdf["geometry"] = gdf.geometry.centroid
        return gdf

    raise ValueError("no centroid lat/lon or geometry available for parcels")


def load_grocers(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)

    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)

    cols = list(gdf.columns)
    if "name" in cols:
        gdf = gdf.rename(columns={"name": "grocer_chain"})
    if "store_name" in cols:
        gdf = gdf.rename(columns={"store_name": "grocer_store"})

    keep_cols = ["geometry"]
    for c in ["grocer_id", "grocer_chain", "grocer_store"]:
        if c in gdf.columns:
            keep_cols.append(c)

    gdf = gdf[keep_cols].copy()
    return gdf


def compute_nearest(
    parcels_gdf: gpd.GeoDataFrame, grocers_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    if parcels_gdf.crs is None:
        parcels_gdf.set_crs(epsg=4326, inplace=True)

    grocers_gdf = grocers_gdf.to_crs(parcels_gdf.crs)

    parcels_proj = parcels_gdf.to_crs(epsg=26914)
    grocers_proj = grocers_gdf.to_crs(parcels_proj.crs)

    joined = gpd.sjoin_nearest(
        parcels_proj,
        grocers_proj,
        how="left",
        distance_col="dist_to_grocer_m",
    )

    joined["dist_to_grocer_m"] = joined["dist_to_grocer_m"].astype(float)
    joined = joined.drop(columns=["index_right"])

    joined = joined.to_crs(parcels_gdf.crs)
    return joined


def export_grocers_shapefile(grocers_geojson_path: Path, out_shp_path: Path) -> None:
    """Export grocers as shapefile for ArcGIS Pro."""
    gdf = gpd.read_file(grocers_geojson_path)
    
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    
    # Rename columns for shapefile compatibility (10 char limit)
    rename_map = {
        'grocer_id': 'groc_id',
        'grocer_chain': 'chain',
        'grocer_store': 'store'
    }
    
    for old_col, new_col in rename_map.items():
        if old_col in gdf.columns:
            gdf = gdf.rename(columns={old_col: new_col})
    
    # Keep only essential columns
    keep_cols = ['groc_id', 'chain', 'store', 'geometry']
    keep_cols = [c for c in keep_cols if c in gdf.columns]
    gdf = gdf[keep_cols]
    
    gdf.to_file(out_shp_path, driver='ESRI Shapefile')
    print(f"Exported grocers shapefile: {out_shp_path}")


def main() -> None:
    parcels_path = project_root / "data" / "processed" / "aggregated_parcels_3d_ready.csv"
    grocers_path = project_root / "data" / "reference" / "grocers.geojson"

    out_mask_csv = project_root / "data" / "interim" / "aggregated_grocer_distance_mask.csv"
    grocers_shp = project_root / "data" / "processed" / "grocers.shp"

    print("Loading aggregated parcels...")
    parcels_df = load_aggregated_parcels(parcels_path)
    print(f"Loaded {len(parcels_df):,} aggregated parcels")
    
    print("\nCreating parcel point geometries...")
    parcels_gdf = make_parcel_points(parcels_df)

    print("\nLoading grocers...")
    grocers_gdf = load_grocers(grocers_path)
    print(f"Loaded {len(grocers_gdf):,} grocers")

    print("\nComputing nearest grocer distances...")
    joined = compute_nearest(parcels_gdf, grocers_gdf)

    # Create lightweight mask with only distance info
    mask_cols = [
        "Roll Number",
        "dist_to_grocer_m",
        "grocer_chain",
        "grocer_store",
        "grocer_id"
    ]
    mask_cols = [c for c in mask_cols if c in joined.columns]

    mask_df = joined[mask_cols].copy()
    
    print(f"\nSaving distance mask...")
    mask_df.to_csv(out_mask_csv, index=False)
    print(f"  Mask CSV: {out_mask_csv}")
    
    print("\nExporting grocers shapefile...")
    export_grocers_shapefile(grocers_path, grocers_shp)
    
    print("\nDistance statistics:")
    print(f"  Min:    {mask_df['dist_to_grocer_m'].min():,.1f} m")
    print(f"  Median: {mask_df['dist_to_grocer_m'].median():,.1f} m")
    print(f"  Mean:   {mask_df['dist_to_grocer_m'].mean():,.1f} m")
    print(f"  Max:    {mask_df['dist_to_grocer_m'].max():,.1f} m")
    
    print(f"\nTo join in ArcGIS Pro:")
    print(f"  1. Right-click aggregated_parcels_3d_ready layer")
    print(f"  2. Joins and Relates > Add Join")
    print(f"  3. Input Join Field: Roll Number")
    print(f"  4. Join Table: {out_mask_csv}")
    print(f"  5. Join Table Field: Roll Number")
    print(f"  6. Color parcels by dist_to_grocer_m")


if __name__ == "__main__":
    main()