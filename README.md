# BoundaryBench

**A National Benchmark for Geographic Boundary Resolution with Calibrated Uncertainty**

[![License: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![License: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-lightgrey.svg)](LICENSE-DATA)
[![Dataset on HuggingFace](https://img.shields.io/badge/🤗-Dataset-yellow)](https://huggingface.co/datasets/nidhip1611/boundarybench)

## Overview

BoundaryBench is a benchmark dataset of 13,000 synthetic coordinate queries across 50 U.S. states plus D.C., designed to evaluate geographic boundary resolution systems. Points are stratified by distance-to-boundary difficulty tiers and complex polygon geometries.

**Key Findings:**
- LLM-only baselines are unreliable for boundary resolution (either abstain ~100% or wrong ~96%)
- GPS noise (±20m) causes 39.6% label flips within 10m of boundaries
- BoundarySafe achieves 100% accuracy on answered queries with 89.4% coverage

*This work is independent research and not affiliated with or endorsed by any agency.*

## Installation
```bash
# Clone repository
git clone https://github.com/nidhip1611/boundarybench.git
cd boundarybench

# Install dependencies
pip install -r requirements.txt
```

## Quick Start
```python
import pandas as pd

# Load dataset
df = pd.read_parquet("data/boundarybench_v1.parquet")

print(f"Total points: {len(df)}")
print(f"Layers: {df['layer'].unique()}")
print(f"Difficulties: {df['difficulty'].unique()}")

# Filter by difficulty
boundary_points = df[df["difficulty"] == "boundary"]

# Filter by layer
county_points = df[df["layer"] == "county"]
```

## Using BoundarySafe
```python
import geopandas as gpd
from src.boundarysafe import boundarysafe_lookup_latlon

# Load boundary shapefiles (you need to download TIGER/Line 2025)
counties = gpd.read_file("path/to/counties.shp").to_crs(2163)
gdf_dict = {"county": counties}

# Query with lat/lon
result = boundarysafe_lookup_latlon(
    lat=40.7128, 
    lon=-74.0060, 
    layer="county",
    gdf_dict=gdf_dict,
    gps_radius_m=20,
    p_thresh=0.90
)

print(result)
# {
#   "status": "answer",
#   "label_id": "36061",
#   "confidence": 0.95,
#   "dist_to_boundary_m": 234.5,
#   "candidates": [("36061", 0.95), ("36047", 0.05)]
# }
```

## Dataset

| Layer | Points | Description |
|-------|--------|-------------|
| County | 4,000 | U.S. counties (3,235 polygons) |
| ZCTA | 4,000 | ZIP Code Tabulation Areas (33,791 polygons) |
| Tract | 5,000 | Census tracts (84,415 polygons) |

### Difficulty Stratification

| Difficulty | Distance | Count | Description |
|------------|----------|-------|-------------|
| easy | ≥500m | 4,550 | Interior points |
| medium | 100-500m | 3,250 | Moderate proximity |
| hard | 10-100m | 3,250 | Near boundary |
| boundary | 0-10m | 1,300 | Very close to boundary |
| edge | 10-100m | 650 | Complex polygons only |

## Reproduce Results

### 1. Verify Dataset
```bash
python src/verify_boundarybench.py
```

### 2. Run BoundarySafe Evaluation

See the evaluation notebook in the repository for full reproduction steps.

## Results

### LLM-Only Baselines (n=210)

| Model | Coverage | Wrong \| Answered |
|-------|----------|-------------------|
| GPT-4o-mini (Safe) | 0.5% | 100.0% |
| Claude 3 Haiku (Safe) | 100.0% | 95.7% |

### BoundarySafe (n=1,992)

| Method | Accuracy (answered) | Abstain Rate | Coverage |
|--------|---------------------|--------------|----------|
| Exact GIS Lookup | 100.0% | 0.0% | 100.0% |
| **BoundarySafe** | **100.0%** | 10.6% | 89.4% |

### GPS Noise Impact (±20m)

| Distance to Boundary | Flip Rate |
|---------------------|-----------|
| 0-10m | 39.6% |
| 10-25m | 12.0% |
| >50m | 0.0% |

## Repository Structure
```
boundarybench/
├── data/
│   ├── boundarybench_v1.parquet          # Full dataset (13,000 points)
│   ├── boundarybench_v1_eval_subset.parquet  # Evaluation subset
│   ├── dataset_card.md                   # Dataset documentation
│   └── README.md                         # Data README
├── src/
│   ├── boundarysafe.py                   # BoundarySafe implementation
│   └── verify_boundarybench.py           # Verification script
├── figures/                              # Publication figures
├── outputs/                              # Evaluation results (CSVs)
├── requirements.txt                      # Python dependencies
├── LICENSE                               # MIT (code)
├── LICENSE-DATA                          # CC-BY-4.0 (data)
├── CITATION.cff                          # Citation metadata
└── README.md                             # This file
```

## Citation
```bibtex
@misc{pandya2025boundarybench,
  title={BoundaryBench: Evaluating Geographic Boundary Resolution with Calibrated Uncertainty},
  author={Pandya, Nidhi},
  year={2025},
  howpublished={GitHub},
  url={https://github.com/nidhip1611/boundarybench}
}
```

## License

- **Code**: [MIT License](LICENSE)
- **Dataset** (`/data`): [CC-BY-4.0](LICENSE-DATA)

## Acknowledgments

This work uses publicly available TIGER/Line 2025 boundary shapefiles.
