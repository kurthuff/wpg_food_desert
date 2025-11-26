# scripts/attach_neighbourhoods_to_parcels.py

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


def clean_total_living_area(df: pd.DataFrame) -> pd.DataFrame:
    col = (
        df["Total Living Area"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace(["", "nan", "NaN", "None", "."], pd.NA)
    )
    df = df.copy()
    df["Total Living Area"] = pd.to_numeric(col, errors="coerce").astype("Int64")
    df = df[df["Total Living Area"] > 0].copy()
    return df


def make_parcels_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    if {"Centroid Lat", "Centroid Lon"}.issubset(df.columns):
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["Centroid Lon"], df["Centroid Lat"]),
            crs="EPSG:4326",
        )
        return gdf

    if "geometry" in df.columns:
        df = df.copy()
        df["geometry"] = df["geometry"].apply(
            lambda x: wkt.loads(x) if isinstance(x, str) and x.strip() else None
        )
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        return gdf

    raise ValueError("parcels must have centroid lat/lon or a geometry column")


def load_neighbourhoods(path: Path) -> gpd.GeoDataFrame:
    df = pd.read_csv(path)
    df["geometry"] = df["geometry"].apply(
        lambda x: wkt.loads(x) if isinstance(x, str) and x.strip() else None
    )
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    return gdf


def attach_neighbourhoods(
    parcels_gdf: gpd.GeoDataFrame, neigh_gdf: gpd.GeoDataFrame
) -> pd.DataFrame:
    if parcels_gdf.crs != neigh_gdf.crs:
        parcels_gdf = parcels_gdf.to_crs(neigh_gdf.crs)

    neigh_cols = ["neighbourhood_id", "name", "population", "geometry"]

    joined = gpd.sjoin(
        parcels_gdf,
        neigh_gdf[neigh_cols],
        how="left",
        predicate="within",
    )

    joined = joined.drop(columns=["index_right"])

    cols = ["Roll Number", "neighbourhood_id", "name", "population"]
    joined = joined[cols].copy()

    return joined


def main() -> None:
    parcels_path = project_root / "data" / "raw" / "Assessment_Parcels_20251112.csv"
    neigh_path = project_root / "data" / "reference" / "neighbourhoods.csv"
    out_path = project_root / "data" / "interim" / "parcel_neighbourhood_mask.csv"

    parcels_df = pd.read_csv(parcels_path, low_memory=False)
    parcels_df = clean_total_living_area(parcels_df)
    parcels_gdf = make_parcels_gdf(parcels_df)

    neigh_gdf = load_neighbourhoods(neigh_path)

    mask_df = attach_neighbourhoods(parcels_gdf, neigh_gdf)

    mask_df.to_csv(out_path, index=False)


if __name__ == "__main__":
    main()
