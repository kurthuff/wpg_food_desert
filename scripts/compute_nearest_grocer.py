# scripts/compute_nearest_grocer.py

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


def load_parcels_with_residents(
    parcels_path: Path, residents_mask_path: Path
) -> pd.DataFrame:
    raw = pd.read_csv(parcels_path, low_memory=False)
    mask = pd.read_csv(residents_mask_path)

    df = raw.merge(mask, on="Roll Number", how="inner")

    keep_cols = [
        "Roll Number",
        "Centroid Lat",
        "Centroid Lon",
        "Geometry",
        "neighbourhood_id",
        "name",
        "population",
        "Total Living Area",
        "Dwelling Units",
        "residents",
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
    for c in ["grocer_chain", "grocer_store"]:
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


def main() -> None:
    parcels_path = project_root / "data" / "raw" / "Assessment_Parcels_20251112.csv"
    residents_mask_path = project_root / "data" / "interim" / "parcel_residents_mask.csv"
    grocers_path = project_root / "data" / "reference" / "grocers.geojson"

    out_mask_csv = (
        project_root / "data" / "interim" / "parcel_nearest_grocer_mask.csv"
    )

    parcels_df = load_parcels_with_residents(parcels_path, residents_mask_path)
    parcels_gdf = make_parcel_points(parcels_df)

    grocers_gdf = load_grocers(grocers_path)

    joined = compute_nearest(parcels_gdf, grocers_gdf)

    cols = [
        "Roll Number",
        "neighbourhood_id",
        "name",
        "population",
        "Total Living Area",
        "Dwelling Units",
        "residents",
        "dist_to_grocer_m",
        "grocer_chain",
        "grocer_store",
    ]
    cols = [c for c in cols if c in joined.columns]

    mask_df = joined[cols].copy()
    mask_df.to_csv(out_mask_csv, index=False)


if __name__ == "__main__":
    main()
