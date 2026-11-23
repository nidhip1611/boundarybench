# Paper audit — every number in paper/main.tex traced to its source

Audited 2026-11-18 against branch v2 (results committed in `results/*/summary.txt`).
Status column: ✓ = matches source (after rounding). All mismatches found during the audit were fixed in the paper.

## Abstract and introduction
| Claim in paper | Value | Source | Status |
|---|---|---|---|
| Benchmark size | 13,000 locations; 520,000 observations | v2_stats [D1], [D2] | ✓ |
| Observed/predicted | 0.99 (0.988 uniform, 0.994 Gaussian) | v2_geometry [G1] footer | ✓ |
| Excess at corners/junctions/slivers | 6–20% | v2_geometry_stress [S1] obs/pred 1.06–1.21 | ✓ |
| Real displacement median | 19–86 m | v2_nyc_streets [S1] 19.5–25.9; v2_utah [U1] 26.9–30.5; v2_national [G2] 30.5–85.6 | ✓ |
| Street offset | ~6.4 m | [S1], [U1], [G2] p50 6.3–6.4 | ✓ |
| Near-line real wrong-tract | 0.04–2.0% | Table 3 rows | ✓ |
| Random-direction | 10.8–20.2% | Table 3 rows | ✓ |
| Simplified files | 1.6–15% of benchmark locations | v2_cartographic [K1] 1.640 / 14.950 | ✓ |

## Sect. 4 Benchmark
| Claim | Value | Source | Status |
|---|---|---|---|
| Layer sizes | county 4,000; ZCTA 4,000; tract 5,000 | v2_stats [D1] | ✓ |
| Table 1 strata | 1,300 / 3,250 / 650 / 3,250 / 4,550 | v2_stats [D1] totals | ✓ |
| Strata distances | 0–10, 10–100, 10–100 (edge), 100–500, ≥500 m | data/dataset_card.md | ✓ |
| Stress set | 4,907 locations | v2_geometry_stress [S1] n_points at R=50 | ✓ (was "about 4,200": fixed) |
| Log-normal | median 61 m, p90 242 m | v2_heavy_tails [H0] median 61.1, R95 357.7 → p90 = 242 | ✓ |
| Held-out folds | 5 folds of states | v2_heldout_geography header | ✓ |

## Sect. 5 Results
| Claim | Value | Source | Status |
|---|---|---|---|
| Uniform R=20, 0–10 m | 34.3% [33.2, 35.5] | v2_stats [B1] 34.28 [33.17, 35.46] | ✓ |
| Uniform R=20, 10–25 m | 4.9% [4.2, 5.8] | [B1] 4.93 [4.20, 5.82] | ✓ |
| Uniform R=50 bands | 43.5 / 27.5 / 7.7% | [B1] 43.48 / 27.46 / 7.72 | ✓ |
| Layer differences | ≤ ~5 points | v2 [T1] max gap 37.20 vs 42.28 | ✓ (was "1–2": fixed) |
| n near-boundary | 33,390 / 43,760 | v2_geometry [G1] footer | ✓ |
| Geometry ratios | straight 0.97–1.00; junction 1.14–1.19; corner 1.13–1.20; sliver 1.06–1.21 | v2_geometry_stress [S1] | ✓ |
| CIs excluding 1 | 11 of 12 | [S1] ratio_ci (Gaussian R=20 sliver 0.98–1.25) | ✓ |
| Distance rule coverage at 0% risk | 95.0 / 91.4 / 87.3 / 76.8% | v2 [T3] uniform op_coverage | ✓ |
| Disk overlay coverage | 96.6 / 93.8 / 90.6 / 83.3% | [T3] | ✓ |
| Disk overlay risk | 0.06–0.70% | [T3] 0.056–0.695 | ✓ (was 0.69: fixed) |
| AURC Gaussian R=20 | distance 0.127 = Gauss overlay 0.127; disk 0.146; MC 0.164 | v2_gaussian [GA1] | ✓ |
| Distance better at corners/slivers; overlays at water edges | — | v2_geometry_stress [S2] | ✓ |
| Unassigned mass | tract 0.1–0.2; county 0.5–1.0; ZCTA 0.8–1.3% | v2_output_categories [O1] | ✓ |
| Gauss overlay vs MC | MAE 0.0032 | v2_gaussian [GA0] | ✓ |
| ECE Gaussian overlay | 1.6–1.7% (R=5–10), 3.8–4.6% (R=20–50) | v2_stats [K1] 1.664, 1.621, 4.562, 3.775 | ✓ |
| ECE disk overlay (uniform) | 2.0–5.6% | [K1] 3.159, 2.003, 5.572, 4.822 | ✓ |
| MC RMSE | 0.079 / 0.039 / 0.012 / 0.006 | v2_mc_convergence [C1] | ✓ |
| MC decisions differing from overlay | ~5% (N=100), 0.7% (N=5,000) | [C1] 4.58–5.42 / 0.67–0.69 | ✓ (wording fixed) |
| Heavy tails t3 R=50 | 67.9% coverage at ≤0.1%; disk overlay 0 | v2_heavy_tails [H2] 67.880 / 0.000 | ✓ |
| Held-out | 24/24 certified; empirical 6–7/24; MC 21/24; worst 0.168%; coverage 91.9 vs 88.5% | v2_heldout_geography [H2], [H1] | ✓ |
| MC not certifiable Gaussian R=50 at 0.1% | coverage 0 | [H1] line "gaussian 50 Monte Carlo 0.1 certified 0.0000" | ✓ |
| Table 2 runtimes (R=20) | 5 / 5 / 13 / 500 / 67 ms per 1k | v2 [T4] 5.45, 4.93, 13.19, 67.26; v2_gaussian [GA2] 500.46 | ✓ (old 18/15/27/238/1,008 fixed) |

## Sect. 6 Real geocoding
| Claim | Value | Source | Status |
|---|---|---|---|
| NYC samples | PLUTO 4,963; Address Points 2,894 | v2_cartographic [K2] / v2_nyc_streets [S1] | ✓ |
| Utah scored | 2,615 | v2_utah [U1] 647+592+694+682 | ✓ (was "about 2,660": fixed) |
| National | 18 counties, 2,286 scored; county sizes 2,000–30,000 | v2_national [G0], [G3] | ✓ |
| Exclusions | units, non-numeric numbers, geocoded truth | exp16 code line 8–9, 126–130; Utah U5 | ✓ |
| NYC displacement | 19–26 m | [S1] 19.5–25.9 | ✓ |
| Utah displacement | 27–31 m | [U1] 26.9–30.5 | ✓ |
| National displacement | 30–86 m | [G2] 30.5–85.6 | ✓ |
| Isotropic prediction Utah | 14–16% | [U1] 14.06 / 15.80 | ✓ |
| Table 3 PLUTO | 2,478; 0.04 [0.01, 0.23]; 11.5 | [S1] Wilson; v2_direction_counterfactual [D1] | ✓ |
| Table 3 Address Points | 1,443; 0.97 [0.58, 1.62]; 15.0 | [S1]; [D1] | ✓ |
| Table 3 Salt Lake | 694; 0.72 [0.31, 1.68]; 11.7 | [U1] | ✓ |
| Table 3 rural Utah | 591; 2.03 [1.17, 3.52]; 10.8 | [U5] | ✓ |
| Table 3 national | 765; 1.57 [0.90, 2.72]; 20.2 | [G4] | ✓ |
| 5–16× fewer errors (excl. PLUTO) | 15.0/0.97, 11.7/0.72, 10.8/2.03, 20.2/1.57 | computed | ✓ |
| Per-county full sample | real 0–3.1%, random 4.1–12.0% | [G2] | ✓ |
| 5–8 m band | 96–100% | [S1] 99.4–99.8; [U1] 99.3–100; [G2] 96.5–100 | ✓ |
| Same side | 84–99.7% | [G2] 84.2–98.9; [U3]; [S3] 99.4–99.7 | ✓ (was 84–99: fixed) |
| Boundaries following streets | 87% nationally; 60–100% by county | [G4] 87.32; [G2] 60.0–100 | ✓ |
| NYC failure taxonomy | 12 same street, 10 different street, 4 opposite side | v2_nyc_sensitivity [N3] | ✓ |
| Larger vs smaller counties | 0.44 [0.20, 0.95] vs 0.98 [0.52, 1.85] | [G3] | ✓ |
| Rural Utah same-side among errors | 44% (urban 78%) | [U3] 0.4375 / 0.7778 | ✓ |
| Non-street vs street | national 3.7 vs 0.66, 5.9 vs 2.7; Utah 3.0 vs 0.72, 4.3 vs 1.9 | [G5]; [U5] | ✓ |
| Pooled exploratory test | 7/187 vs 25/1,945; OR 3.0; Fisher p = 0.02 | computed from [G5] + [U5] (scipy fisher_exact p = 0.018) | ✓ |
| Cartographic tract | 1.64% [1.32, 2.03]; 14.2% within 10 m; 2.3% outside | [K1] | ✓ |
| Cartographic county | 2.1 / 8.0 / 15.0% | [K1] | ✓ |
| NYC PLUTO cartographic | 0.69% vs 0.10% (6.8×, "nearly seven times") | [K2] 0.685 / 0.101 | ✓ |
| Limitations: rural Utah | 2.47% → 2.03% | [U1] / [U5] | ✓ |

## Sect. 7 Table 4
| Claim | Value | Source | Status |
|---|---|---|---|
| Residual risk near street boundaries | 0.04–2.0% (2.7% smaller counties) | Table 3; [G5] 2.740 | ✓ |
| Rural / non-street risk | 2–6% | [U5] 2.03; [G5] 2.74–5.88; [U2] 3.0–4.3 | ✓ |
| Coasts / ZCTA unassigned | 0.5–1.3% | [O1] | ✓ |

## Figures
- Fig. 1 lines: Eq. (1) and Φ(−d/σ), σ = R/2.4477; markers: v2_geometry [G1] observed_pct (paper/make_figures.py).
- Fig. 2 bars: Table 3 values (paper/make_figures.py).

## References (22) — verified against publisher/indexing records 2026-11-18
All bibliographic details (authors, title, venue, volume, pages, year) checked online: Blakemore 1984; Cayo & Talbot 2003;
Cheng et al. 2003; Cheung et al. 2004; Chow 1970; Geifman & El-Yaniv 2017 (pages added: 4878–4887); Goldberg et al. 2007;
Guo et al. 2017; Heuvelink 1998; Jacquez 2012; Krieger et al. 2001; Krieger et al. 2002; Rushton et al. 2006; Shi 2010
(CRC, © 2010, released Oct 2009); Strickland et al. 2007; Zandbergen 2008; Zandbergen 2009; Zhang & Goodchild 2002;
Zimmerman et al. 2007; plus Census Geocoder, TIGER/Line 2025 and USDOT NAD web pages.
Removed: Perkal 1956 ("On epsilon length") — the exact bibliographic record could not be verified online; the epsilon-band
point-in-polygon idea is cited to Blakemore 1984 instead.

## Revision after pre-submission reviews (2026-11-18)
| Claim | Value | Source | Status |
|---|---|---|---|
| Table 2 (matched risk) | coverage at risk ≤0.5% / ≤0.1%, Unif/Gauss × R 20/50 | v2/T3 pooled + v2_gaussian [GA1]; CIs v2_matched [M1] | ✓ |
| Distance rule within 0.1 pt of both overlays | all 24 model×R×target cells | [M1] / T3 / GA1 (max gap 0.08) | ✓ |
| MC vs distance rule | at most 0.1 higher, up to 0.9 lower; 0 at Gauss 50 m 0.1% | T3 (g20 0.1%: +0.07; u50 0.1%: −0.85) | ✓ |
| Bootstrap CI extent | ≤1.5 points; MC Gauss 50 0.1% [0, 79.0] | [M1] (g50 0.1% distance 78.4 [76.9, 79.5]) | ✓ |
| Runtime environment | Apple M4 Pro, Python 3.11, Shapely 2.2, single process | v2_realdata_extra [R5] | ✓ |
| UCB fold exceedances | 25–26/120 (MC 16) vs empirical 58–60 (MC 50) | v2_heldout_geography [H2] total_folds_over_target | ✓ |
| MC UCB Gauss 50 0.1% | coverage 0 (abstains on all) | [H1] | ✓ |
| Random-direction CIs (Table 3) | 11.5 [10.9,12.1]; 15.0 [14.1,16.0]; 11.7 [10.6,12.8]; 10.8 [9.6,12.1]; 20.2 [19.0,21.5] | v2_realdata_extra [R4] | ✓ |
| Joint boundary × side (pooled, within 50 m) | street+same side 27/6,949 = 0.39%; street+opposite 19/84 = 22.6%; non-street+same side 6/264 = 2.3% | [R1b] | ✓ |
| NYC overlap | 13 addresses, none misassigned | [R3] | ✓ |
| Distance rule on real geocodes (near-line pooled) | n = 5,971, 44 wrong; d_obs < 7 m withholds 64.9%, catches 26/44; answered risk 0.86% | [R2c] | ✓ |
| Geometry relative excess | 6–21% | v2_geometry_stress [S1] 1.061–1.207 | ✓ |
| Berg et al. 2026 | Trans. GIS 30(2) e70225; "overlay uncertainty"; aggregation / reallocation to populated blocks | CU Boulder record + department news (Apr 2026) | ✓ |
| Kinnee et al. 2020 | IJERPH 17(16) 5845; NYC; street-segment errors mostly toward one direction; few differences in census-area assignment | PMC7459468 | ✓ |
| Census geocoder documentation | "coordinates calculated along an address range" (offset not stated on current page) | census.gov Geocoding Services | ✓ |
| Cartographic file documentation | designed for small-scale thematic mapping; not for geocoding / precise area relationships | census.gov Cartographic Boundary File Description | ✓ |

## 10-page version (2026-11-18)
Fig. 2 removed (its values are in Table 3, now with CIs); Table 1 folded into Sect. 4 text; references dropped:
Krieger 2002, Jacquez 2012, Goldberg 2007, Cheng 2003 (claims that used them were reworded or removed). All numbers unchanged.

## Using the spare page (2026-11-18)
The 10-page cut built to 9 pages, so Fig. 2, Eq. (2) as a display, the AURC sentence and the four dropped references
(Krieger 2002, Jacquez 2012, Goldberg 2007, Cheng 2003) were restored. Numbers unchanged.

## Revision round 3 (third reviewer + GPT re-review), sources for every new number

| Paper text | Value | Source | Check |
|---|---|---|---|
| Pipeline | 13,679 submitted; 12,947 Match; 59 Tie; 673 No_Match; 189 matched not scored; 100 Utah geocoded refs; 12,658 scored | v2_realdata_reconcile [P0], [P0b] | ✓ |
| Near-line cohort | 5,971 / 44 wrong; = Table 2 | [P1] | ✓ |
| Old street-side cohort | 7,327 / 54 = 5,971 + 1,356 random-stratum addresses with d_true < 50 m | [P1b–d] | ✓ explains 27/6,949 etc. |
| Street side (cohort) | same 21/5,630; opposite 18/75; non-street 5/266 | [P2b] | ✓ |
| Excl. segment ends/ambiguous | 11/4,164; 3/35 | [P4d] | ✓ |
| Street-following share | 5,705/5,971 = 95.5%; national 668/765 = 87% | [P0b] | ✓ |
| Along/across medians | wrong 83/31 m; correct 18/17 m | [P4b] | ✓ |
| Length-preserving test | 4,378 (73%); along 6.66 [6.17,7.20]; across 19.03 [18.28,19.76]; random 13.74 [13.25,14.22]; actual 0.37 [0.21,0.57]; ordering in all 6 | [P7] | ✓ |
| Non-street vs street | 1.6–5.9 vs 0.64–2.7 outside NYC; NYC 0/82; OR 2.78 p 0.0445; w/o NYC p 0.176 | [P3], [P3b], [P3c] | ✓ |
| National split | 5/529 0.95%; 7/236 2.97% | [P1] | ✓ |
| Rural Utah opposite side | 8 of 12; SLC 1 of 5 | [P2] | ✓ |
| Geocode-based boundary type | agreement 5,933/5,971 = 99.4%; flag 4.187% catches 5; distance same workload 5 | [P5b], [P5] | ✓ |
| C vs A in-sample | +1 to +3 at 4–65%; all bootstrap CIs include 0 | [P5], [P5c] | ✓ |
| C vs A held-out | near-line 7/10/25 vs 6/9/24 at 9.97/25.3/63.5%; all scored 7/28/36 vs 15/25/38 | [P8b], [P8c] | ✓ |
| Held-out folds | UCB(obs) met 24/24 (MC 23/23 + 1 no answers); empirical 6–7/24 (MC 21/24); folds over 25–26 (MC 16), empirical 58–60 (MC 50); UCB(loc) folds over 3/2/2/0, max 0.5126% at 0.5% target; coverage 91.38/91.41/88.27/85.87 vs 91.93–91.95/88.54; disk overlay UCB(loc) no answers at Gauss 50 m 0.1% | v2_heldout_folds [F2], [F3], F1_folds.csv | ✓ |
| Worst UCB(obs) relative excess | 0.168% vs 0.1% | F1_folds.csv | ✓ |
| 24 combinations | 8 settings × targets 1/0.5/0.1%; bootstrap recomputes coverage-at-target per replicate | exp17 code | ✓ |
| Vintage, run dates | Public_AR_Current / Current_Current; files dated Nov 9 (NYC PLUTO) and Nov 12, 2026 (others) | src/nycdata.py, exp04 | ✓ |
| Removed | Fig. 2 (duplicated Table 2); AURC and Brier mentions; NYC 26-case breakdown and full-sample county range (other cohorts); NYC cartographic 0.69% sentence | — | — |

## Revision round 4 (two Weak-Accept reviews, Nov 23): new numbers and sources

| Paper text | Value | Source |
|---|---|---|
| Near-line flow | 6,369 submitted; Tie 30; No_Match 237; Match >500 m 75; Utah geocoded refs 56; scored 5,971 (93.8%); rural Utah 78.8%, smaller counties 77.1% | v2_realdata_sensitivity [S1] |
| Excluded counted as wrong | 0.08 / 3.18 / 0.86 / 5.39 / 3.95; all 1.97 [1.65, 2.35]; random 13.4 | [S2] |
| 18-county CI | county-cluster [0.67, 2.67]; random [18.03, 23.14]; real < random in 18/18 counties | [S4], [S4b] |
| Bands | near-line 0–10 m 1/52 vs 27.96; all strata <25 m 0.84 vs 16.96; <100 m 0.70 vs 11.34 | [S5], [S5b] |
| Census-returned tract = PIP | 5,970/5,971 near-line; 12,657/12,658 all | [S3] |
| Non_Exact | 50.43% of near-line; 30/3,011 (1.00%) vs 14/2,960 (0.47%); Fisher p = 0.022 (computed from S6c counts); distance at 50% workload catches 23 | [S6c]; v2_realdata_reconcile P5 |
| EPSG:2163 distortion | max linear scale error 1.647%; max angular 2.051° | [S7] |
| Matched edge | geocode on reported side 100%; offset median 6.37 m; 99.98% within 5–8 m | v2_matched_edge [M1] |
| Block-face cases | same face 2/5,594; beyond end 13/168; other side 4/13; >60 m 25/112 (42/293) | [M2] |
| Face counterfactual | near-line observed 0.747; random position on face 0.884; opposite side 63.74 | [M3] |
| Fold table | distance rule, UCB(location), 0.1%: per-fold errors/answered | v2_heldout_folds F1_folds.csv |
| NYC ratio | 0.97 / 0.04 ≈ 24 | [P1] |

## Revision round 5 (research-driven additions, Nov 23)

| Paper text | Value | Source |
|---|---|---|
| Block group / block near-line | 0.837% / 1.658% [1.36, 2.01]; random 14.78 / 22.10 | v2_blocks_policy [B1] |
| Blocks on/off matched face | 6/5,594; 92/293 | [B2] |
| QCT | 1,123/5,971 near-line addresses in 2026 QCTs (18.8%); flips 8/44 near-line, 2/18 random stratum | [Q1], [Q2] |
| Non_Exact anatomy | city name only 2,637 (17 wrong); directional differs 268 (11 wrong, 4.10%); house number differs 6 (1) | [F1] |
| Flag | house no./directional differs: 4.59% reviewed, 12/44 caught; distance same share 5 | [F1c] |
| Region concentration | rural Utah 10 of 12 caught | [F1d] |
| Non_Exact stratified | MH OR 3.28, CMH p = 0.0031 | [F2b] |
| Prior work | Whitsel 2006 concordance 85–98%; Brokamp 2018 95.5%; Wilson et al. 2024 3.3% wrong tract (CA LIHTC) | research report (verified citations) |
