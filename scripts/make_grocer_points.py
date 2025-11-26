# scripts/make_grocer_points.py

import sys
from pathlib import Path

import pandas as pd
import geopandas as gpd

project_root = Path("/Users/dpro/projects/food_desert")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from food_desert import paths  # noqa: F401


def main() -> None:
    in_path = project_root / "data" / "reference" / "grocer_geocode.csv"
    out_geojson = project_root / "data" / "interim" / "grocers.geojson"
    out_csv = project_root / "data" / "interim" / "grocers.csv"

    df = pd.read_csv(in_path)

    df = df.dropna(subset=["X", "Y"]).copy()
    df["lon"] = pd.to_numeric(df["X"])
    df["lat"] = pd.to_numeric(df["Y"])

    cols = [
        "name",
        "store_name",
        "street",
        "city",
        "province",
        "postal_cod",
        "country",
        "source",
        "lon",
        "lat",
    ]
    cols = [c for c in cols if c in df.columns]
    df = df[cols].copy()

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )

    gdf.to_file(out_geojson, driver="GeoJSON")
    gdf.to_csv(out_csv, index=False)


if __name__ == "__main__":
    main()
