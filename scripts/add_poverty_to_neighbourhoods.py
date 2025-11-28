# scripts/add_poverty_to_neighbourhoods.py

import sys
from pathlib import Path

import pandas as pd

project_root = Path("/Users/dpro/projects/food_desert")

src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from food_desert import paths  # noqa: F401


def read_poverty_from_excel(xlsx_path: Path) -> dict:
    df = pd.read_excel(xlsx_path, sheet_name=0, header=None, engine="openpyxl")

    # excel is 1-based, pandas iloc is 0-based
    # C526 -> row 526, col C -> iloc[525, 2]
    # C531 -> row 531, col C -> iloc[530, 2]
    lim_at = df.iloc[525, 2]
    lico_at = df.iloc[530, 2]

    def to_float(val):
        if isinstance(val, str):
            val = val.strip()
            if val.endswith("%"):
                val = val[:-1]
        try:
            return float(val)
        except Exception:
            return pd.NA

    lim_at_pct = to_float(lim_at)
    lico_at_pct = to_float(lico_at)

    return {
        "lim_at_pct": lim_at_pct,
        "lico_at_pct": lico_at_pct,
    }


def main() -> None:
    neigh_csv = project_root / "data" / "reference" / "neighbourhoods.csv"
    excel_dir = project_root / "data" / "reference" / "neighbourhoodpop_excel"

    out_csv = project_root / "data" / "reference" / "neighbourhoods_with_poverty.csv"

    neigh_df = pd.read_csv(neigh_csv)

    records = []

    for xlsx_path in sorted(excel_dir.glob("*.xlsx")):
        name = xlsx_path.stem  # file name without extension
        data = read_poverty_from_excel(xlsx_path)
        record = {
            "name": name,
            "lim_at_pct": data["lim_at_pct"],
            "lico_at_pct": data["lico_at_pct"],
        }
        records.append(record)

    poverty_df = pd.DataFrame(records)

    merged = neigh_df.merge(poverty_df, on="name", how="left")

    merged.to_csv(out_csv, index=False)

    missing = poverty_df[~poverty_df["name"].isin(neigh_df["name"])]
    if not missing.empty:
        print("these excel files did not match any neighbourhood name:")
        print(missing["name"].tolist())

    missing_neigh = neigh_df[~neigh_df["name"].isin(poverty_df["name"])]
    if not missing_neigh.empty:
        print("these neighbourhoods have no poverty data (no xlsx):")
        print(missing_neigh["name"].tolist())

    print(f"wrote {out_csv}")


if __name__ == "__main__":
    main()
