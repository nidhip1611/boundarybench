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
| EXP04b | `exp04b_nyc_mechanism.py` | Why NYC geocoding errors rarely cross tract lines: across- vs along-boundary displacement | `results/v2_nyc_mechanism/` |
| EXP05 | `exp05_mc_convergence.py` | Is MC-100's weakness finite-sample noise? N = 25…5,000 vs disk overlay | `results/v2_mc_convergence/` |
| EXP06 | `exp06_geometry_stress.py` | Targeted junction / corner / sliver / water-edge points: deviation from theory, strategy ranking | `results/v2_geometry_stress/` |
| EXP07 | `exp07_heavy_tails.py` | Robustness to heavy-tailed error (t3, contaminated, Strickland-scale lognormal) — simulation | `results/v2_heavy_tails/` |
| EXP09 | `exp09_nyc_streets.py` | NYC mechanism: Census point vs street centerlines, street vs non-street tract boundaries, same-side test, map panels; independent truth = NYC Address Points | `results/v2_nyc_streets/` |
| EXP10 | `exp10_output_categories.py` | Formal outputs: ANSWER / ABSTAIN (competing region) / ABSTAIN (unassigned mass: water, ZCTA gaps) | `results/v2_output_categories/` |
| EXP11 | `exp11_direction_counterfactual.py` | Real NYC displacement lengths with random directions vs actual directions | `results/v2_direction_counterfactual/` |
| EXP12 | `exp12_heldout_geography.py` | Thresholds chosen on 4/5 of states, risk checked on held-out states (empirical vs Wilson-certified) | `results/v2_heldout_geography/` |
| EXP13 | `exp13_nyc_sensitivity.py` | Street tolerance 1–5 m, Exact vs Non_Exact matches, Fisher test, failure taxonomy | `results/v2_nyc_sensitivity/` |
| EXP14 | `exp14_cartographic_boundaries.py` | Cartographic (simplified) boundary files with exact locations | `results/v2_cartographic/` |
| EXP15 | `exp15_utah_transfer.py` | Second region: Utah urban (Salt Lake Co.) vs 6 rural counties, UGRC address points, same measurements as EXP09/EXP11 | `results/v2_utah/` |
| EXP08 | `exp08_stats.py` | Data-flow table, bootstrap CIs over points, calibration (equal-mass bins, reliability diagrams) | `results/v2_stats/` |

Tests: `python -m pytest tests -q` (half-plane and junction checks against closed-form answers and high-sample MC).

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

### 2026-11-09 — EXP02–EXP04 (commit 5b614c6, results commit fd9fd3c)
- EXP02: wrong-region rate collapses onto d/R and matches straight-boundary theory: observed/predicted 0.988 (uniform,
  n = 33,390) and 0.994 (Gaussian, n = 43,760). 92–97% of near-boundary points have straight local boundaries.
  Junctions exceed theory (uniform R = 50: 45.1% [39.8, 50.4] vs 37.1%); bends/slivers smaller, n small.
- EXP03: Gaussian overlay validated (MAE 0.0037 vs 5,000-sample MC). Under Gaussian error its AURC equals the distance
  rule (R = 20: 0.127 vs 0.127), better than disk overlay (0.146) and MC (0.164). ECE not better at R = 20/50
  (3.8–4.0% vs 2.0–2.7%). 20× slower than disk overlay.
- EXP04 (NYC, 4,966 matched addresses): displacement p50 25 m, p95 64 m, but wrong tract only 0.24% [0.08, 0.70]
  (random sample) vs 4.2% predicted by an isotropic model; 0 / 1,261 near-boundary addresses. ZCTA 0.08%, county 0%.
  Hypothesis: Census Geocoder places addresses along TIGER street edges that tract boundaries also follow → EXP04b.

### Plan (locked 2026-11-11)
Paper = benchmark + controlled evaluation. Three findings: (1) d/R theory explains isotropic misassignment, junctions
deviate; (2) therefore distance ranking ≈ probability methods, probabilities only needed for graded output, MC adds
noise/cost; (3) real geocoding error is structured — the error model must match the error source.
Avoid: "first probabilistic PIP", "exact" for anything but uniform-disk overlay, "level/geometry don't matter",
"MC is unreliable", national real-world error rates.
Schedule: EXP04b–08 Nov 11–12 → freeze Nov 13–15 → go/no-go Nov 16 → write Nov 16–22 → submit ICICT Nov 25.
Outreach (Berg group, Geocodio, public-health GIS) only after submission.

### 2026-11-11 — Gaussian overlay corrected (tail bias)
The new unit test caught a tail error in the EXP03 method (16 equal-probability rings with uniform density inside each
ring): at d = 1.25 R it gave P(cross) = 0.45% vs the exact 0.11%; max absolute error 0.0046.
Replaced by radial Gauss-Legendre quadrature, P = ∫ A(r) (r/σ²) φ(r) dr on [0, 5σ], 24 nodes:
max absolute error 0.0002 on the half-plane test. EXP03 results from commit 5b614c6 are SUPERSEDED — rerun EXP03,
then EXP06 and EXP08 (they use it). Expect ECE of the Gaussian overlay at R = 20/50 to change.

### 2026-11-12 — EXP01–EXP08 full run (commit 5d09585); results frozen
EXP01 reproduced (all T3 values identical after removing clip_by_rect). Fixed Gaussian overlay validated
(MAE 0.0032 vs 5,000-sample Gaussian MC). Full numbers: results/*/summary.txt. Key results:
- d/R theory holds for every isotropic error model tried (uniform, Gaussian, t3, contaminated, lognormal).
- Geometry stress set: straight ≈ theory; junctions ×1.14–1.19, corners ×1.13–1.20, slivers ×1.06–1.21 (tight CIs).
- Distance score ranks as well as or better than overlays (better at corners/slivers and under heavy tails);
  overlays clearly better only at water edges / coverage gaps.
- MC error ∝ 1/sqrt(N): needs ~5,000 samples to match the overlay.
- Overlay calibration ECE 1.6–5.6% even when correctly specified.
- NYC mechanism: errors are not parallel to boundaries (across share 0.475 vs 0.5 isotropic); 67% move toward the line
  (80% near-boundary) but Census points stop at a fixed ~6.3 m offset (none < 5 m; near-boundary median 6.4 m vs true
  25.6 m). The geocoder snaps toward the street centreline that forms the tract boundary and stays on the correct side.
  The earlier "slides along the street" hypothesis was wrong. Check added to EXP04b as [M4].

### 2026-11-12 — Strengthening plan (merged with second-opinion review)
Added EXP09 (street mechanism + independent NYC Address Points truth + map panels) and EXP10 (formal output
categories). NYC wording stays conservative until EXP09: "Census geocodes concentrate ~6.3 m from tract lines,
consistent with street-side placement". LLM evaluation dropped from the paper (future work). Paper adds a
practitioner decision table and a Zenodo DOI for code + data.

### 2026-11-12 — EXP09–EXP10 results (results commit 82d1156)
Census points sit 6.3–6.5 m from the nearest TIGER street centerline (99.4–99.8%), on the same side as the true address
(99.4–99.7% of correct cases). Independent NYC Address Points truth: wrong tract 0.48% random, 0.97% near-boundary
(isotropic prediction 12–16%). 95–98% of near-boundary tract lines follow streets. Unassigned mass is largest for
ZCTA (gaps) and county (coast). Full numbers in results/v2_nyc_streets and results/v2_output_categories.

### 2026-11-12 — Final batch (combined plan)
EXP11–EXP14 added; EXP09 now also saves match type and street names (rerun needed; results unchanged otherwise).
Paper framing: assignment risk = f(distance, error distribution, error direction, boundary geometry, coverage gaps);
each experiment answers one factor. After this batch: experiments frozen.

### 2026-11-12 — EXP15 added (second region, not only NYC)
Utah chosen because one state gives an urban street grid (Salt Lake County) and rural counties where tract lines more
often follow non-street features. Prediction from the NYC mechanism: more Census tract crossings on non-street
boundaries. Truth = UGRC statewide address points (county Master Address List authorities).

### Next
- Run EXP09 (rerun), EXP11–EXP15. Write paper Nov 13–21; Springer LNNS format Nov 22–24; submit Nov 25.
