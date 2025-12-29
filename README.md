# BoundaryBench

**A National Benchmark for Geographic Boundary Resolution with Calibrated Uncertainty**

![Code License: MIT](https://img.shields.io/badge/Code%20License-MIT-green.svg)
![Data License: CC BY 4.0](https://img.shields.io/badge/Data%20License-CC%20BY%204.0-lightgrey.svg)
[![🤗 Dataset](https://img.shields.io/badge/🤗%20Dataset-HuggingFace-yellow)](https://huggingface.co/datasets/nidhipandya/boundarybench)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18090588.svg)](https://doi.org/10.5281/zenodo.18090588)


## Overview

BoundaryBench is a benchmark dataset of 13,000 synthetic coordinate queries across 50 U.S. states plus D.C., designed to evaluate geographic boundary resolution systems. Points are stratified by distance-to-boundary difficulty tiers and complex polygon geometries.

**Key findings:**
- LLM-only baselines are unreliable for boundary resolution (either abstain ~100% or wrong ~96%)
- GPS noise (±20m) causes 39.6% label flips within 10m of boundaries
- BoundarySafe achieves 100% accuracy on answered queries with 89.4% coverage

*Independent research; not endorsed by any organization.*

---

## Installation
```bash
git clone https://github.com/nidhipandya/boundarybench.git
cd boundarybench
pip install -r requirements.txt
```

## Quick Start (Dataset)
```python
import pandas as pd

# Load dataset (download from HuggingFace if not present)
df = pd.read_parquet("data/boundarybench_v1.parquet")

print("Total points:", len(df))
print("Layers:", df["layer"].unique())
print("Difficulties:", df["difficulty"].unique())

# Filter examples
boundary_points = df[df["difficulty"] == "boundary"]
county_points = df[df["layer"] == "county"]
```

> **Note:** If parquet files are not in `data/`, download from [HuggingFace](https://huggingface.co/datasets/nidhipandya/boundarybench).

---

## BoundarySafe Method

> **Note:** You must supply boundary polygons yourself; we do not distribute 
> shapefiles in this repo. Download TIGER/Line 2025 from the Census Bureau 
> and project to EPSG:2163 before use.

BoundarySafe estimates label stability under GPS uncertainty by sampling perturbed locations and re-running exact containment.

### Example (lat/lon)
```python
import geopandas as gpd
from src.boundarysafe import boundarysafe_lookup_latlon

# Load boundaries and project to EPSG:2163 (meters)
counties = gpd.read_file("path/to/counties.shp").to_crs(2163)
gdf_dict = {"county": counties}

result = boundarysafe_lookup_latlon(
    lat=40.7128,
    lon=-74.0060,
    layer="county",
    gdf_dict=gdf_dict,
    gps_radius_m=20,
    p_thresh=0.90,
)

print(result)
```

### Output
```json
{
  "status": "answer",
  "label_id": "36061",
  "confidence": 0.95,
  "dist_to_boundary_m": 234.5,
  "candidates": [["36061", 0.95], ["36047", 0.05]]
}
```

---

## Dataset Summary

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

---

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

---

## Reproduce Results

1. **Verify dataset:**
```bash
python src/verify_boundarybench.py
```

2. **View evaluation results:**
```bash
# Results are in outputs/
ls outputs/
```

---

## Repository Structure
```
boundarybench/
├── data/                    # Dataset files
├── src/                     # Source code
│   ├── boundarysafe.py      # BoundarySafe implementation
│   └── verify_boundarybench.py
├── figures/                 # Publication figures
├── outputs/                 # Evaluation results (CSVs)
├── requirements.txt
├── LICENSE                  # MIT (code)
├── LICENSE-DATA             # CC BY 4.0 (data)
├── CITATION.cff
└── README.md
```

---

## Citation
```bibtex
@misc{pandya2025boundarybench,
  title={BoundaryBench: Evaluating Geographic Boundary Resolution with Calibrated Uncertainty},
  author={Pandya, Nidhi},
  year={2025},
  howpublished={GitHub},
  url={https://github.com/nidhipandya/boundarybench}
}
```

---

## License

- **Code**: MIT ([LICENSE](LICENSE))
- **Dataset**: CC BY 4.0 ([LICENSE-DATA](LICENSE-DATA))

## Acknowledgments

This work uses publicly available boundary shapefiles (TIGER/Line 2025).
