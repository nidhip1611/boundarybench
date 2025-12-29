"""
Example 1: Load and Explore BoundaryBench Dataset
"""
import pandas as pd

# Load dataset
# If not present, download from: https://huggingface.co/datasets/nidhip1611/boundarybench
df = pd.read_parquet("../data/boundarybench_v1.parquet")

print("="*60)
print("BoundaryBench Dataset")
print("="*60)

print(f"\nTotal points: {len(df):,}")
print(f"Columns: {list(df.columns)}")

print(f"\nLayers:")
print(df["layer"].value_counts())

print(f"\nDifficulties:")
print(df["difficulty"].value_counts())

print(f"\nSample rows:")
print(df.head())

# Filter examples
print(f"\n" + "="*60)
print("Filter Examples")
print("="*60)

boundary_points = df[df["difficulty"] == "boundary"]
print(f"\nBoundary points (0-10m from edge): {len(boundary_points)}")

county_points = df[df["layer"] == "county"]
print(f"County layer points: {len(county_points)}")

# Check distance distribution
print(f"\nDistance to boundary stats:")
print(df["dist_to_boundary_m"].describe())
