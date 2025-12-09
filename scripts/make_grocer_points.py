# scripts/make_grocer_points.py

import sys
from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium

project_root = Path("/Users/dpro/projects/food_desert")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from food_desert import paths  # noqa: F401


def build_working_csv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if not {"X", "Y"}.issubset(df.columns):
        raise ValueError(f"expected X and Y columns, got: {list(df.columns)}")

    df["lon"] = pd.to_numeric(df["X"], errors="coerce")
    df["lat"] = pd.to_numeric(df["Y"], errors="coerce")

    df = df[df["lon"].notna() & df["lat"].notna()].copy()

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

    return df


def csv_to_geodataframe(csv_path: Path) -> gpd.GeoDataFrame:
    df = pd.read_csv(csv_path)

    # Add a simple surrogate key if one doesn't already exist
    if "grocer_id" not in df.columns:
        df = df.reset_index(drop=True)
        df.insert(0, "grocer_id", df.index + 1)  # 1,2,3,...

    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df = df[df["lon"].notna() & df["lat"].notna()].copy()

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
    return gdf


def make_folium_map(gdf: gpd.GeoDataFrame, html_path: Path) -> None:
    if gdf.empty:
        raise ValueError("no grocers to map")

    center_lat = gdf["lat"].mean()
    center_lon = gdf["lon"].mean()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

    for _, row in gdf.iterrows():
        name = row.get("store_name") or row.get("name") or ""
        popup_text = f"{name}"
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=4,
            fill=True,
            popup=popup_text,
        ).add_to(m)

    m.save(str(html_path))


def main() -> None:
    geocode_src = project_root / "data" / "reference" / "qgis_grocer_geocode.csv"

    audit_dir = project_root / "data" / "interim" / "geocode_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    audit_csv = audit_dir / "grocers.csv"
    audit_geojson = audit_dir / "grocers.geojson"
    audit_html = audit_dir / "grocers_map.html"

    final_csv = project_root / "data" / "reference" / "grocers.csv"
    final_geojson = project_root / "data" / "reference" / "grocers.geojson"

    current_csv_path = geocode_src

    while True:
        if current_csv_path == geocode_src:
            src_df = pd.read_csv(geocode_src)
            work_df = build_working_csv(src_df)
            work_df.to_csv(audit_csv, index=False)
        else:
            work_df = pd.read_csv(audit_csv)

        gdf = csv_to_geodataframe(audit_csv)
        gdf.to_file(audit_geojson, driver="GeoJSON")
        make_folium_map(gdf, audit_html)

        print()
        print("grocer audit files written:")
        print(f"  csv:    {audit_csv}")
        print(f"  geojson:{audit_geojson}")
        print(f"  map:    {audit_html}")
        print()
        print("open the html map in a browser, check locations,")
        print(f"edit {audit_csv} if needed (lon/lat), then come back here.")
        ans = input("are you happy with grocers.csv? [y/n]: ").strip().lower()

        if ans == "y":
            gdf.to_csv(final_csv, index=False)
            gdf.to_file(final_geojson, driver="GeoJSON")
            print()
            print("final grocers written to:")
            print(f"  {final_csv}")
            print(f"  {final_geojson}")
            break
        elif ans == "n":
            print()
            print(f"ok. edit {audit_csv} and then press enter to regenerate.")
            input("press enter when ready: ")
            current_csv_path = audit_csv
            continue
        else:
            print("please answer 'y' or 'n'")


if __name__ == "__main__":
    main()
