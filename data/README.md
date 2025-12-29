# BoundaryBench v1

BoundaryBench is a national geospatial benchmark of synthetic coordinates labeled with ground-truth administrative regions at multiple granularities. It is designed to stress-test location-to-region mapping, especially near polygon boundaries and complex shapes.

## What's Inside

| Metric | Value |
|--------|-------|
| **Total points** | 13,000 |
| **Coverage** | 50 U.S. states + Washington, D.C. (51) |
| **Layers** | county (4,000), ZCTA (4,000), tract (5,000) |
| **Source** | TIGER/Line 2025 (U.S. Census Bureau) |

## Difficulty Tiers

| Difficulty | Count | Distance to Boundary |
|------------|-------|---------------------|
| boundary | 1,300 | 0-10 m |
| hard | 3,250 | 10-100 m |
| edge | 650 | 10-100 m (complex polygons only) |
| medium | 3,250 | 100-500 m |
| easy | 4,550 | >= 500 m |

## Files

| File | Description |
|------|-------------|
| boundarybench_v1.parquet | Full dataset (recommended) |
| boundarybench_v1.csv | Full dataset (CSV format) |
| boundarybench_v1_train.* | Training split (41 states) |
| boundarybench_v1_dev.* | Development split (41 states, 15%) |
| boundarybench_v1_test.* | Test split (10 held-out states) |
| boundarybench_v1_eval_subset.* | 2,000-point subset for LLM evaluation |
| verify_boundarybench.py | Verification script |
| dataset_card.md | HuggingFace dataset card |

## Splits

| Split | States | Description |
|-------|--------|-------------|
| test | 10 held-out | AK, CA, DC, FL, IL, MA, NY, OR, TX, WA |
| dev | 41 states | 15% stratified sample |
| train | 41 states | Remainder |

Held-out state FIPS: 02, 06, 11, 12, 17, 25, 36, 41, 48, 53

## Coordinate Reference Systems

| Stage | CRS | Description |
|-------|-----|-------------|
| Generation | EPSG:2163 | US National Atlas Equal Area (meters) |
| Export | EPSG:4269 | NAD83 (lat/lon degrees) |

## Schema

| Column | Type | Description |
|--------|------|-------------|
| layer | string | Target layer: tract, zcta, or county |
| label_id | string | Ground-truth region identifier |
| difficulty | string | easy, medium, hard, boundary, or edge |
| split | string | train, dev, or test |
| statefp | string | 2-digit state FIPS code |
| lat | float | Latitude (EPSG:4269) |
| lon | float | Longitude (EPSG:4269) |
| dist_to_boundary_m | float | Distance to nearest boundary (meters) |

## Usage
```python
import pandas as pd

# Load full dataset
df = pd.read_parquet("boundarybench_v1.parquet")

# Load specific split
test = pd.read_parquet("boundarybench_v1_test.parquet")

# Filter by difficulty
hard_points = df[df["difficulty"] == "hard"]
```

## Task

Given a coordinate (lat, lon), predict the correct label_id for a specified layer.

Evaluation metric: Exact match accuracy

## Reproducibility

- Random seed: 42
- Generation: Stratified sampling with strict distance-to-boundary constraints
- Verification: Run python verify_boundarybench.py

## License

CC-BY-4.0

## Acknowledgments

Boundary polygons from TIGER/Line 2025, U.S. Census Bureau.
