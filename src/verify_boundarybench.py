#!/usr/bin/env python3
"""
BoundaryBench v1 - Dataset Verification Script

Validates the dataset structure, counts, and distance-to-boundary constraints.

Usage:
    python verify_boundarybench.py
    python verify_boundarybench.py --path boundarybench_v1.parquet
"""

import argparse
import pandas as pd

EXPECTED_TOTAL = 13000
EXPECTED_STATES = 51

DIST_BANDS = {
    "boundary": (0.0, 10.0),
    "hard": (10.0, 100.0),
    "edge": (10.0, 100.0),
    "medium": (100.0, 500.0),
    "easy": (500.0, float("inf")),
}


def measured_bucket(d):
    """Assign distance to difficulty bucket."""
    if d < 10:
        return "boundary"
    if d < 100:
        return "hard"
    if d < 500:
        return "medium"
    return "easy"


def verify(path):
    """Run all verification checks."""

    print("=" * 60)
    print("BOUNDARYBENCH v1 VERIFICATION")
    print("=" * 60)

    # Load data
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    errors = []

    # Check total count
    print(f"\nTotal points: {len(df)}")
    if len(df) != EXPECTED_TOTAL:
        errors.append(f"Expected {EXPECTED_TOTAL} points, got {len(df)}")

    # Check state count
    state_col = "statefp" if "statefp" in df.columns else "statefp_point"
    n_states = df[state_col].nunique()
    print(f"Unique states: {n_states}")
    if n_states != EXPECTED_STATES:
        errors.append(f"Expected {EXPECTED_STATES} states, got {n_states}")

    # Check layer counts
    print("\nBy layer:")
    layer_counts = df.groupby("layer").size()
    print(layer_counts)

    # Check difficulty counts
    print("\nBy difficulty:")
    diff_counts = df.groupby("difficulty").size()
    print(diff_counts)

    # Check split counts
    print("\nBy split:")
    split_counts = df.groupby("split").size()
    print(split_counts)

    return df, errors


def verify_distances(df, errors):
    """Verify distance bands."""
    
    print("\nDistance ranges by difficulty:")
    for diff, (lo, hi) in DIST_BANDS.items():
        sub = df[df["difficulty"] == diff]
        if len(sub) == 0:
            print(f"  {diff}: (none)")
            continue
        
        mn = sub["dist_to_boundary_m"].min()
        mx = sub["dist_to_boundary_m"].max()
        print(f"  {diff}: min={mn:.1f}m, max={mx:.1f}m")
        
        if mn < lo - 0.1:
            errors.append(f"{diff}: min distance {mn:.1f} < {lo}")
        if hi != float("inf") and mx > hi + 0.1:
            errors.append(f"{diff}: max distance {mx:.1f} > {hi}")
    
    # Band verification
    df["difficulty_measured"] = df["dist_to_boundary_m"].apply(measured_bucket)
    expected_measured = df["difficulty"].replace({"edge": "hard"})
    mismatches = (expected_measured != df["difficulty_measured"]).sum()
    
    print(f"\nBand mismatches (edge=hard): {mismatches}")
    if mismatches > 0:
        errors.append(f"Found {mismatches} band mismatches")
    
    return errors


def main():
    parser = argparse.ArgumentParser(description="Verify BoundaryBench dataset")
    parser.add_argument("--path", default="boundarybench_v1.parquet", help="Path to dataset file")
    args = parser.parse_args()
    
    df, errors = verify(args.path)
    errors = verify_distances(df, errors)
    
    print("\n" + "=" * 60)
    if errors:
        print("VERIFICATION FAILED")
        for e in errors:
            print(f"  - {e}")
    else:
        print("VERIFICATION PASSED")


if __name__ == "__main__":
    main()
