"""Central configuration for all BoundaryBench experiments.

Paths can be overridden with environment variables:
  BB_WORK   working folder for large files (TIGER shapefiles, raw per-observation outputs)
  BB_TIGER  folder containing COUNTY/, ZCTA520/, TRACT/ (default: $BB_WORK/tiger2025)
  BB_DATA   BoundaryBench point file (default: data/boundarybench_v1.parquet in this repo)

Small, shareable results (tables + figures) are written to results/ inside the repo.
"""
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORK = os.path.abspath(os.environ.get("BB_WORK", os.path.join(REPO, "work")))
TIGER = os.environ.get("BB_TIGER", os.path.join(WORK, "tiger2025"))
DATA = os.environ.get("BB_DATA", os.path.join(REPO, "data", "boundarybench_v1.parquet"))
RAW = os.path.join(WORK, "outputs")          # large per-observation files (not committed)
RESULTS = os.path.join(REPO, "results")      # tables + figures (committed)

# Experimental design (V2) — changing these changes the results
CRS_M = 2163                  # US National Atlas Equal Area (same CRS used to build the dataset)
RADII = [5, 10, 20, 50]       # error scale R in metres
MODELS = ["uniform", "gaussian"]
GAUSS_K95 = 2.4477            # Gaussian: sigma = R / 2.4477, so 95% of errors fall within R
K_OBS = 5                     # noisy observations per benchmark point
N_MC = 100                    # Monte Carlo samples
THETA = 0.90                  # default answer threshold for probabilistic methods
N_RINGS = 16                  # Gaussian overlay: equal-probability rings
Q_MAX = 0.999                 # Gaussian overlay covers 99.9% of the error mass

LAYER_ID = {"county": "GEOID", "zcta": "ZCTA5CE20", "tract": "GEOID"}
LABEL_WIDTH = {"county": 5, "zcta": 5, "tract": 11}


def out_dir(*parts):
    p = os.path.join(*parts)
    os.makedirs(p, exist_ok=True)
    return p
