# scripts/geocode_supermarkets_osmnx.py

import sys
from pathlib import Path
import time

import pandas as pd
import geopandas as gpd
import osmnx as ox

project_root = Path("/Users/dpro/projects/food_desert")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from food_desert import paths  # noqa: F401


def build_full_address(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    def join_parts(row):
        parts = []
        for col in ["street", "city", "province", "postal_code", "country"]:
            if col in row and isinstance(row[col], str):
                val = row[col].strip()
                if val:
                    parts.append(val)
        return ", ".join(parts)

    df["full_address"] = df.apply(join_parts, axis=1)
    return df


def geocode_with_osmnx(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # configure osmnx
    ox.settings.use_cache = True
    ox.settings.log_console = False
    ox.settings.nominatim_timeout = 30  # bump timeout

    # make sure lat / lon columns exist
    if "lat" not in df.columns:
        df["lat"] = pd.NA
    if "lon" not in df.columns:
        df["lon"] = pd.NA

    # only geocode rows missing lat/lon
    mask = df["lat"].isna() | df["lon"].isna()
    sub = df.loc[mask, "full_address"]

    # dedupe addresses to reduce calls
    unique_addrs = sub.dropna().unique()

    addr_to_coords: dict[str, tuple[float | None, float | None]] = {}

    for addr in unique_addrs:
        if not isinstance(addr, str) or not addr.strip():
            addr_to_coords[addr] = (None, None)
            continue
        try:
            # ox.geocode returns (lat, lon)
            lat, lon = ox.geocode(addr)
            addr_to_coords[addr] = (lat, lon)
        except Exception:
            addr_to_coords[addr] = (None, None)
        # be gentle
        time.sleep(1)

    def lookup_lat(addr):
        coords = addr_to_coords.get(addr)
        if coords is None:
            return pd.NA
        return coords[0]

    def lookup_lon(addr):
        coords = addr_to_coords.get(addr)
        if coords is None:
            return pd.NA
        return coords[1]

    df.loc[mask, "lat"] = df.loc[mask, "full_address"].map(lookup_lat)
    df.loc[mask, "lon"] = df.loc[mask, "full_address"].map(lookup_lon)

    return df


def to_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    df = df.copy()
    df = df.dropna(subset=["lat", "lon"]).copy()

    df["lat"] = pd.to_numeric(df["lat"])
    df["lon"] = pd.to_numeric(df["lon"])

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
    return gdf


def main() -> None:
    in_path = project_root / "data" / "reference" / "supermarket_addresses.csv"
    out_csv = project_root / "data" / "processed" / "supermarkets_geocoded.csv"
    out_geojson = project_root / "data" / "processed" / "supermarkets_geocoded.geojson"

    df = pd.read_csv(in_path)

    df = build_full_address(df)
    df = geocode_with_osmnx(df)

    gdf = to_geodataframe(df)

    gdf.to_csv(out_csv, index=False)
    gdf.to_file(out_geojson, driver="GeoJSON")


if __name__ == "__main__":
    main()
