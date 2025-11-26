# scripts/compute_residents.py

import sys
from pathlib import Path

import numpy as np
import pandas as pd

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
    df["Total Living Area"] = pd.to_numeric(col, errors="coerce").astype("Float64")
    return df


def clean_dwelling_units(df: pd.DataFrame) -> pd.DataFrame:
    col = (
        df["Dwelling Units"]
        .astype(str)
        .str.strip()
        .replace(["", "nan", "NaN", "None", "."], pd.NA)
    )
    df = df.copy()
    df["Dwelling Units"] = pd.to_numeric(col, errors="coerce").astype("Float64")
    return df


def index_to_suffix(i: int) -> str:
    # 0 -> a, 1 -> b, ... 25 -> z, 26 -> aa, etc
    result = []
    n = i
    while True:
        n, r = divmod(n, 26)
        result.append(chr(ord("a") + r))
        if n == 0:
            break
        n -= 1
    return "".join(reversed(result))


def load_and_mask_raw(parcels_path: Path, mask_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(parcels_path, low_memory=False)
    mask = pd.read_csv(mask_path)

    # inner join keeps only roll numbers in the mask
    df = raw.merge(mask, on="Roll Number", how="inner")

    # keep only columns needed for residents work
    keep_cols = [
        "Roll Number",
        "Total Living Area",
        "Multiple Residences",
        "Dwelling Units",
        "Property Use Code",
        "neighbourhood_id",
        "name",
        "population",
    ]
    # silently drop ones that might not exist
    keep_cols = [c for c in keep_cols if c in df.columns]

    df = df[keep_cols].copy()
    return df


def split_multi_residences(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df = clean_total_living_area(df)
    df = clean_dwelling_units(df)

    if "roll_number_base" not in df.columns:
        df["roll_number_base"] = df["Roll Number"]

    # set single units to 1
    df["Dwelling Units"] = df["Dwelling Units"].fillna(1)

    mask_multi = (df["Multiple Residences"] == "Yes") & (df["Dwelling Units"] > 1)
    multi = df[mask_multi].copy()
    single = df[~mask_multi].copy()

    rows = []

    for _, row in multi.iterrows():
        n_units = int(row["Dwelling Units"])
        if n_units <= 0:
            n_units = 1

        area_total = row["Total Living Area"]
        area_per = area_total / n_units if pd.notna(area_total) else np.nan
        base_roll = row["Roll Number"]

        for i in range(n_units):
            r = row.copy()
            r["roll_number_base"] = base_roll
            suffix = index_to_suffix(i)
            r["Roll Number"] = f"{base_roll}-{suffix}"
            r["Dwelling Units"] = 1.0
            r["Total Living Area"] = area_per
            rows.append(r)

    if rows:
        multi_split = pd.DataFrame(rows)
        dwellings = pd.concat([single, multi_split], ignore_index=True)
    else:
        dwellings = single

    return dwellings


def allocate_residents(dwellings: pd.DataFrame) -> pd.DataFrame:
    df = dwellings.copy()

    df = clean_total_living_area(df)

    def alloc_group(g: pd.DataFrame) -> pd.DataFrame:
        g = g.copy()
        if "population" not in g.columns or g["population"].isna().all():
            g["residents"] = 0
            return g

        pop = g["population"].iloc[0]
        if pd.isna(pop) or pop <= 0:
            g["residents"] = 0
            return g

        area = g["Total Living Area"].fillna(0.0)
        total_area = area.sum()
        if total_area <= 0:
            n = len(g)
            base = np.zeros(n, dtype=int)
            forced = np.ones(n, dtype=bool)
            assigned = min(int(pop), n)
            base[:assigned] = 1
            g["residents"] = base
            return g

        quota = pop * area / total_area

        base = np.floor(quota).astype(int)

        forced_mask = base == 0
        base[forced_mask] = 1

        assigned_sum = int(base.sum())
        leftover = int(pop - assigned_sum)

        rema = quota - np.floor(quota)
        rema[forced_mask] = -1.0

        if leftover > 0:
            order = np.argsort(-rema.to_numpy())
            # cap leftovers so we don't overrun
            k = min(leftover, len(order))
            # use positional indexing
            base_vals = base.to_numpy()
            for pos in order[:k]:
                base_vals[pos] += 1
            base = pd.Series(base_vals, index=g.index)

        g["residents"] = base
        return g

    df = df.groupby("neighbourhood_id", group_keys=False).apply(alloc_group)
    return df


def recombine_to_parcels(dwellings: pd.DataFrame) -> pd.DataFrame:
    df = dwellings.copy()

    if "roll_number_base" not in df.columns:
        df["roll_number_base"] = df["Roll Number"]

    sum_cols = ["Total Living Area", "Dwelling Units", "residents"]
    for col in sum_cols:
        if col not in df.columns:
            df[col] = np.nan

    # columns that should be the same across units of a parcel
    first_cols = ["neighbourhood_id", "name", "population"]

    agg_dict = {c: "first" for c in first_cols}
    for c in sum_cols:
        agg_dict[c] = "sum"

    grouped = df.groupby("roll_number_base", as_index=False).agg(agg_dict)
    grouped = grouped.rename(columns={"roll_number_base": "Roll Number"})

    # final small mask style output
    out_cols = [
        "Roll Number",
        "neighbourhood_id",
        "name",
        "population",
        "Total Living Area",
        "Dwelling Units",
        "residents",
    ]
    out_cols = [c for c in out_cols if c in grouped.columns]
    grouped = grouped[out_cols].copy()

    return grouped


def main() -> None:
    parcels_path = project_root / "data" / "raw" / "Assessment_Parcels_20251112.csv"
    mask_path = project_root / "data" / "interim" / "parcel_neighbourhood_mask.csv"
    out_mask_path = project_root / "data" / "interim" / "parcel_residents_mask.csv"

    masked = load_and_mask_raw(parcels_path, mask_path)
    dwellings = split_multi_residences(masked)
    dwellings = allocate_residents(dwellings)
    parcel_residents = recombine_to_parcels(dwellings)

    parcel_residents.to_csv(out_mask_path, index=False)


if __name__ == "__main__":
    main()
