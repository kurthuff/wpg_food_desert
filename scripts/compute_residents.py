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


# Property Use Code classification for household size distribution
OWNED_CODES = [
    'RESSD - DETACHED SINGLE DWELLING',
    'RESSS - SIDE BY SIDE',
    'CNRES - CONDO RESIDENTIAL',
    'RESRH - ROW HOUSING',
    'RESMA - MULTIPLE ATTACHED UNITS',
    'RESDU - DUPLEX',  # Moved to owned
]

RENTED_CODES = [
    'RESAP - APARTMENTS',
    'CNAPT - CONDO APARTMENT',
    'RESAM - APARTMENTS MULTIPLE USE',
    'RESMC - MULTIFAMILY CONVERSION',
    'CMMRH - COMMERCIAL ROW HOUSE',
]

# All other codes default to RENTED behavior
DEFAULT_TENURE = 'rented'


def load_household_distribution(csv_path: Path) -> pd.DataFrame:
    """
    Load CMHC household size distribution data.
    """
    df = pd.read_csv(csv_path)
    return df


def load_and_classify_parcels(
    parcels_path: Path, mask_path: Path, household_dist_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load parcels, apply mask, and classify as owned/rented.
    
    Returns:
        tuple: (parcels_df with tenure classification, household_dist_df)
    """
    raw = pd.read_csv(parcels_path, low_memory=False)
    mask = pd.read_csv(mask_path)
    household_dist = load_household_distribution(household_dist_path)

    # Inner join keeps only roll numbers in the mask
    df = raw.merge(mask, on="Roll Number", how="inner")

    # Keep only columns needed for residents work
    keep_cols = [
        "Roll Number",
        "Property Use Code",
        "Dwelling Units",
        "neighbourhood_id",
        "name",
        "population",
    ]
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols].copy()

    # Clean Dwelling Units
    df["Dwelling Units"] = pd.to_numeric(df["Dwelling Units"], errors="coerce")

    # Classify tenure
    def classify_tenure(code):
        if code in OWNED_CODES:
            return 'owned'
        elif code in RENTED_CODES:
            return 'rented'
        else:
            return DEFAULT_TENURE

    df['tenure'] = df['Property Use Code'].apply(classify_tenure)

    return df, household_dist


def allocate_residents_to_neighbourhood(
    parcels: pd.DataFrame, household_dist: pd.DataFrame, neighbourhood_id: int
) -> pd.DataFrame:
    """
    Allocate residents to parcels within a single neighbourhood using
    CMHC household size distributions.
    
    Algorithm:
    1. Calculate raw population using city-wide household size percentages
    2. Scale to match neighbourhood census population
    3. Create pools of household sizes for owned/rented parcels
    4. Assign residents by drawing from pools proportional to dwelling units
    5. Ensure minimum 1 resident per parcel
    """
    neigh_parcels = parcels[parcels['neighbourhood_id'] == neighbourhood_id].copy()
    
    if len(neigh_parcels) == 0:
        return neigh_parcels
    
    census_pop = neigh_parcels['population'].iloc[0]
    
    # Count owned and rented dwelling units
    owned = neigh_parcels[neigh_parcels['tenure'] == 'owned']
    rented = neigh_parcels[neigh_parcels['tenure'] == 'rented']
    
    total_owned_units = owned['Dwelling Units'].sum()
    total_rented_units = rented['Dwelling Units'].sum()
    
    # Get household size distributions from CMHC data
    dist = household_dist.set_index('Category')
    
    # Calculate raw populations using percentages
    # For owned units
    own1_raw = (dist.loc['One-person household', 'Owners_Pct'] / 100) * total_owned_units * 1
    own2_raw = (dist.loc['Two-person household', 'Owners_Pct'] / 100) * total_owned_units * 2
    own3_raw = (dist.loc['Three-person household', 'Owners_Pct'] / 100) * total_owned_units * 3
    own4_raw = (dist.loc['Four-person household', 'Owners_Pct'] / 100) * total_owned_units * 4
    own5_raw = (dist.loc['Five-or-more-person household', 'Owners_Pct'] / 100) * total_owned_units * 5
    
    # For rented units
    rent1_raw = (dist.loc['One-person household', 'Renters_Pct'] / 100) * total_rented_units * 1
    rent2_raw = (dist.loc['Two-person household', 'Renters_Pct'] / 100) * total_rented_units * 2
    rent3_raw = (dist.loc['Three-person household', 'Renters_Pct'] / 100) * total_rented_units * 3
    rent4_raw = (dist.loc['Four-person household', 'Renters_Pct'] / 100) * total_rented_units * 4
    rent5_raw = (dist.loc['Five-or-more-person household', 'Renters_Pct'] / 100) * total_rented_units * 5
    
    total_raw = own1_raw + own2_raw + own3_raw + own4_raw + own5_raw + \
                rent1_raw + rent2_raw + rent3_raw + rent4_raw + rent5_raw
    
    # Scale to match census population
    scaling_factor = census_pop / total_raw if total_raw > 0 else 0
    
    own1_pop = own1_raw * scaling_factor
    own2_pop = own2_raw * scaling_factor
    own3_pop = own3_raw * scaling_factor
    own4_pop = own4_raw * scaling_factor
    own5_pop = own5_raw * scaling_factor
    
    rent1_pop = rent1_raw * scaling_factor
    rent2_pop = rent2_raw * scaling_factor
    rent3_pop = rent3_raw * scaling_factor
    rent4_pop = rent4_raw * scaling_factor
    rent5_pop = rent5_raw * scaling_factor
    
    # Convert populations to dwelling unit counts
    def pop_to_units_with_rounding(pop, household_size, total_units):
        """
        Convert population to number of dwelling units with proper rounding.
        Uses remainder distribution to ensure exact match to total units.
        """
        exact_units = pop / household_size
        base_units = int(exact_units)
        return base_units, exact_units - base_units
    
    # Calculate base units and remainders
    owned_allocations = [
        pop_to_units_with_rounding(own1_pop, 1, total_owned_units),
        pop_to_units_with_rounding(own2_pop, 2, total_owned_units),
        pop_to_units_with_rounding(own3_pop, 3, total_owned_units),
        pop_to_units_with_rounding(own4_pop, 4, total_owned_units),
        pop_to_units_with_rounding(own5_pop, 5, total_owned_units),
    ]
    
    rented_allocations = [
        pop_to_units_with_rounding(rent1_pop, 1, total_rented_units),
        pop_to_units_with_rounding(rent2_pop, 2, total_rented_units),
        pop_to_units_with_rounding(rent3_pop, 3, total_rented_units),
        pop_to_units_with_rounding(rent4_pop, 4, total_rented_units),
        pop_to_units_with_rounding(rent5_pop, 5, total_rented_units),
    ]
    
    # Distribute remainders
    def distribute_remainders(allocations, target_total):
        """
        Distribute remainder dwelling units based on fractional parts.
        """
        base_units = [alloc[0] for alloc in allocations]
        remainders = [alloc[1] for alloc in allocations]
        
        current_total = sum(base_units)
        needed = int(target_total - current_total)
        
        # Sort by remainder (largest first) and add units
        sorted_indices = np.argsort(remainders)[::-1]
        
        for i in range(min(needed, len(sorted_indices))):
            idx = sorted_indices[i]
            base_units[idx] += 1
        
        return base_units
    
    owned_units = distribute_remainders(owned_allocations, total_owned_units)
    rented_units = distribute_remainders(rented_allocations, total_rented_units)
    
    # Create household size pools
    owned_pool = (
        [1] * owned_units[0] +
        [2] * owned_units[1] +
        [3] * owned_units[2] +
        [4] * owned_units[3] +
        [5] * owned_units[4]
    )
    
    rented_pool = (
        [1] * rented_units[0] +
        [2] * rented_units[1] +
        [3] * rented_units[2] +
        [4] * rented_units[3] +
        [5] * rented_units[4]
    )
    
    # Shuffle pools
    np.random.seed(42)  # Reproducible
    np.random.shuffle(owned_pool)
    np.random.shuffle(rented_pool)
    
    # Assign residents to parcels
    owned_idx = 0
    rented_idx = 0
    
    residents_list = []
    
    for _, parcel in neigh_parcels.iterrows():
        du = int(parcel['Dwelling Units'])
        tenure = parcel['tenure']
        
        if tenure == 'owned' and owned_idx < len(owned_pool):
            end_idx = min(owned_idx + du, len(owned_pool))
            household_sizes = owned_pool[owned_idx:end_idx]
            residents = sum(household_sizes)
            owned_idx = end_idx
        elif tenure == 'rented' and rented_idx < len(rented_pool):
            end_idx = min(rented_idx + du, len(rented_pool))
            household_sizes = rented_pool[rented_idx:end_idx]
            residents = sum(household_sizes)
            rented_idx = end_idx
        else:
            # Shouldn't happen if pools sized correctly, but fallback
            residents = du  # 1 person per unit as fallback
        
        residents_list.append(residents)
    
    neigh_parcels['residents'] = residents_list
    
    # Ensure minimum 1 resident per parcel
    neigh_parcels.loc[neigh_parcels['residents'] == 0, 'residents'] = 1
    
    # Adjust if total doesn't match census (due to rounding or minimum enforcement)
    total_assigned = neigh_parcels['residents'].sum()
    diff = int(census_pop - total_assigned)
    
    if diff != 0:
        # Sort by residents (descending for removal, ascending for addition)
        sorted_parcels = neigh_parcels.sort_values('residents', ascending=(diff > 0))
        
        abs_diff = abs(diff)
        for i in range(min(abs_diff, len(sorted_parcels))):
            idx = sorted_parcels.index[i]
            if diff > 0:
                neigh_parcels.loc[idx, 'residents'] += 1
            elif diff < 0 and neigh_parcels.loc[idx, 'residents'] > 1:
                neigh_parcels.loc[idx, 'residents'] -= 1
    
    return neigh_parcels


def main() -> None:
    parcels_path = project_root / "data" / "raw" / "Assessment_Parcels_20251112.csv"
    mask_path = project_root / "data" / "interim" / "parcel_neighbourhood_mask.csv"
    household_dist_path = project_root / "data" / "reference" / "winnipeg_household_data_2021.csv"
    out_mask_path = project_root / "data" / "interim" / "parcel_residents_mask.csv"

    parcels_df, household_dist = load_and_classify_parcels(
        parcels_path, mask_path, household_dist_path
    )

    # Process each neighbourhood
    all_results = []
    
    for neighbourhood_id in parcels_df['neighbourhood_id'].unique():
        if pd.notna(neighbourhood_id):
            result = allocate_residents_to_neighbourhood(
                parcels_df, household_dist, neighbourhood_id
            )
            all_results.append(result)
    
    # Combine all neighbourhoods
    final_df = pd.concat(all_results, ignore_index=True)
    
    # Output columns (matching original structure)
    out_cols = [
        "Roll Number",
        "neighbourhood_id",
        "name",
        "population",
        "Total Living Area",
        "Dwelling Units",
        "residents",
    ]
    
    # Add Total Living Area from original if needed for downstream compatibility
    if "Total Living Area" not in final_df.columns:
        raw = pd.read_csv(parcels_path, low_memory=False)
        tla_map = raw[['Roll Number', 'Total Living Area']].drop_duplicates()
        final_df = final_df.merge(tla_map, on='Roll Number', how='left')
    
    out_cols = [c for c in out_cols if c in final_df.columns]
    final_df = final_df[out_cols].copy()
    
    final_df.to_csv(out_mask_path, index=False)


if __name__ == "__main__":
    main()