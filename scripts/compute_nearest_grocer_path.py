# scripts/compute_nearest_grocer_path.py

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx
from shapely import wkt
from shapely.geometry import Point
from shapely.strtree import STRtree

project_root = Path("/Users/dpro/projects/food_desert")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from food_desert import paths  # noqa: F401


def load_parcels_with_residents(parcels_path: Path,
                                residents_mask_path: Path) -> pd.DataFrame:
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


def load_paths(path: Path) -> gpd.GeoDataFrame:
    paths_gdf = gpd.read_file(path)
    if paths_gdf.crs is None:
        paths_gdf.set_crs(epsg=4326, inplace=True)
    return paths_gdf


def build_path_graph(paths_gdf: gpd.GeoDataFrame) -> nx.Graph:
    paths_proj = paths_gdf.to_crs(epsg=26914)

    g = nx.Graph()

    for _, row in paths_proj.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "MultiLineString":
            lines = geom.geoms
        else:
            lines = [geom]

        for line in lines:
            coords = list(line.coords)
            if len(coords) < 2:
                continue

            start = coords[0]
            end = coords[-1]
            length = line.length

            u = start
            v = end

            if u not in g:
                g.add_node(u, x=u[0], y=u[1])
            if v not in g:
                g.add_node(v, x=v[0], y=v[1])

            if u == v:
                continue

            if g.has_edge(u, v):
                if length < g[u][v]["weight"]:
                    g[u][v]["weight"] = length
            else:
                g.add_edge(u, v, weight=length)

    return g


def build_node_index(g: nx.Graph):
    node_coords = list(g.nodes)
    points = [Point(x, y) for x, y in node_coords]
    tree = STRtree(points)
    return tree, points


def nearest_node_for_geom(geom, tree: STRtree, points):
    if geom is None or geom.is_empty:
        return None

    idx = tree.nearest(geom)

    # shapely STRtree can return an index (int) or a geometry
    if isinstance(idx, (int, np.integer)):
        pt = points[int(idx)]
    else:
        pt = idx

    return (pt.x, pt.y)


def assign_nearest_nodes(points_gdf: gpd.GeoDataFrame,
                         tree: STRtree,
                         points,
                         col_name: str) -> gpd.GeoDataFrame:
    gdf = points_gdf.copy()
    gdf[col_name] = gdf.geometry.apply(
        lambda geom: nearest_node_for_geom(geom, tree, points)
    )
    return gdf


def compute_node_distances(g: nx.Graph, source_nodes: list[tuple[float, float]]):
    dist = nx.multi_source_dijkstra_path_length(g, source_nodes, weight="weight")
    return dist


def main() -> None:
    parcels_path = project_root / "data" / "raw" / "Assessment_Parcels_20251112.csv"
    residents_mask_path = project_root / "data" / "interim" / "parcel_residents_mask.csv"
    grocers_path = project_root / "data" / "reference" / "grocers.geojson"
    paths_path = project_root / "data" / "reference" / "Road_Network_20251112.geojson"

    out_mask_csv = (
        project_root / "data" / "interim" / "parcel_nearest_grocer_path_mask.csv"
    )

    parcels_df = load_parcels_with_residents(parcels_path, residents_mask_path)
    parcels_gdf = make_parcel_points(parcels_df)

    grocers_gdf = load_grocers(grocers_path)
    paths_gdf = load_paths(paths_path)

    parcels_proj = parcels_gdf.to_crs(epsg=26914)
    grocers_proj = grocers_gdf.to_crs(epsg=26914)

    path_graph = build_path_graph(paths_gdf)

    tree, points = build_node_index(path_graph)

    parcels_proj = assign_nearest_nodes(parcels_proj, tree, points, "path_node")
    grocers_proj = assign_nearest_nodes(grocers_proj, tree, points, "path_node")

    grocer_nodes = (
        grocers_proj["path_node"]
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    if not grocer_nodes:
        raise ValueError("no grocer path nodes snapped; check CRS / path data")

    node_dist = compute_node_distances(path_graph, grocer_nodes)

    parcels_proj["dist_to_grocer_path_m"] = parcels_proj["path_node"].map(node_dist)

    result = pd.DataFrame(parcels_proj.drop(columns="geometry"))

    cols = [
        "Roll Number",
        "neighbourhood_id",
        "name",
        "population",
        "Total Living Area",
        "Dwelling Units",
        "residents",
        "dist_to_grocer_path_m",
    ]
    cols = [c for c in cols if c in result.columns]
    result = result[cols].copy()

    result.to_csv(out_mask_csv, index=False)


if __name__ == "__main__":
    main()
