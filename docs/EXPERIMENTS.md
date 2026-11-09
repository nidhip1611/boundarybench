# BoundaryBench — experiment log

One place for what was run, why, and where the results live. Add an entry every time an experiment is (re)run
or a design decision changes. Numbers here must come from `results/*/summary.txt`.

## Repository layout

| Path | What |
|---|---|
| `data/` | Benchmark points (`boundarybench_v1.parquet`, 13,000 points: county 4,000 / ZCTA 4,000 / tract 5,000) |
| `src/config.py` | All paths and design constants (radii, error models, K, thresholds) |
| `src/geo.py` | TIGER layers, point loading, point-in-polygon, distance to boundary |
| `src/uncertainty.py` | Error simulation + strategies (crisp, distance rule, Monte Carlo, disk overlay, Gaussian overlay) + straight-line theory |
| `src/metrics.py` | Risk–coverage, AURC, operating points, ECE, Wilson CI |
| `src/boundarysafe.py` | V1 method (kept for reference / V1 reproducibility) |
| `experiments/exp01…04_*.py` | One script per experiment (see below) |
| `experiments/run_all.py` | Runs all experiments in order |
| `notebooks/BoundaryBench_V2_colab.ipynb` | Colab runner: clones this repo and calls the scripts |
| `results/<experiment>/` | Committed tables (CSV), figures (PNG) and `summary.txt` |
| `$BB_WORK` (default `work/`, not committed) | TIGER shapefiles and large per-observation parquet files |
| `outputs/`, `figures/` | V1 results (unchanged) |

## Experiments

| ID | Script | Question | Output |
|---|---|---|---|
| EXP01 | `exp01_v2_main.py` | RQ1–RQ3: reliability vs distance/level/error model; strategy comparison | `results/v2/` |
| EXP02 | `exp02_geometry.py` | Does error collapse onto d/R and match straight-boundary theory? Where does local geometry deviate? | `results/v2_geometry/` |
| EXP03 | `exp03_gaussian_overlay.py` | Gaussian-weighted overlay (correctly specified under Gaussian error) vs other strategies | `results/v2_gaussian/` |
| EXP04 | `exp04_nyc_real.py` | RQ4: real geocoding error (NYC PLUTO lot centroids vs Census Geocoder) | `results/v2_nyc/` |

## Design decisions (locked)

- **Evaluation fix vs V1.** V1 (Colab Cell 59) gave every method the clean true point, so exact GIS = 100% and
  BoundarySafe = 100% on answered queries by construction. From V2 on, methods see only the noisy reported point and
  are scored against the true region.
- **Positioning.** Benchmark + systematic evaluation paper. No claim of a new algorithm. Probabilistic point-in-polygon
  (Cheung et al. 2004), geocoding misassignment (Strickland et al. 2007; Berg et al. 2026) are prior work.
- **R.** Uniform: maximum error radius. Gaussian: 95% radius, sigma = R / 2.4477. Methods are given R only.
- **Naming.** "Disk overlay" (previously "exact overlay") is exact only under a uniform-disk error model.
- **Geometry.** V1 "edge" tier = points 10–100 m inside multipart / holed / thin polygons; all 0–10 m points come
  from simple polygons. The tiers therefore do not test corners, junctions or slivers at close range → EXP02.
- **Heavy-tailed simulation** is a robustness test, never called validation. Real-world evidence = EXP04.

## Run history

### 2026-11-09 — EXP01 full run (pre-repo version, Colab notebook converted by Cursor)
Machine: MacBook Pro M4 Pro, 24 GB. Runtime 64 s. Sanity check PASS. 520,000 observations.
Key results (uniform error):
- Crisp PIP wrong-region rate, R = 20: 33–35% at 0–10 m, 4.5–5.5% at 10–25 m, 0% beyond 25 m.
- R = 50: 43–44% at 0–10 m, 27–29% at 10–25 m, 7–8% at 25–50 m.
- County / ZCTA / tract within ~1–2 points in every band. "edge" tier ≈ "hard" tier.
- AURC: distance rule ≈ disk overlay ≤ Monte Carlo. At uniform R = 20: distance rule (tau = R) 87.3% coverage, 0% risk;
  disk overlay (theta = 0.9) 90.6% coverage, 0.26% risk — a tradeoff, not a win.
- Monte Carlo (100 samples) gives confident wrong answers: Gaussian R = 50, coverage at risk ≤ 0.1% is 0% (MC) vs 78% (overlay).
- Runtime per 1,000 queries at R = 20: crisp 5.5 ms, overlay 13.4 ms, MC 68 ms.
- Pooled error rates (0.8–6.3%) reflect the benchmark's stratified mix, not real-world rates — report per-band rates.

### 2026-11-09 — EXP01 re-run from repo (branch v2, commit b7bf0d8)
Reproduced the first run exactly: all 32 pooled and 96 by-layer [T3] rows identical
(e.g. uniform R = 20 crisp error 3.665%, disk overlay AURC 0.167%).
EXP02 failed: `shapely.clip_by_rect` accepts only scalar bounds. The same call in `disk_pairs` had always fallen back
to plain intersection via try/except, so EXP01 numbers are unaffected. Fix: removed `clip_by_rect` in both places.

### Next
- Run EXP02–EXP04. Go / no-go for ICICT 2027 (deadline Nov 25) on Nov 16.
