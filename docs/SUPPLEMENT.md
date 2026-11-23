# Supplementary tables (S1–S7)

All values are copied from the result files named under each table. Rates are disagreement between the Census-returned tract and the tract of the named reference point.

## S1. Address flow by sample and stratum
Source: results/v2_realdata_sensitivity/S1_flow.csv. Stratum of unscored addresses inferred from the consecutive sampling blocks. Near-line = reference point within 50 m of a TIGER/Line 2025 tract line (distance in EPSG:2163); random = uniform draw from all eligible points of the same sample (it can include points near a line). County selection: in each Census division, the NAD r24 county with the most eligible points ('largest-coverage') and one county drawn with a fixed seed from those with 2,000–30,000 points ('smaller'); see experiments/exp16_national_transfer.py.

| group | stratum | submitted | Tie | No_Match | Match_excluded | ref_geocoded | scored | scored_%_of_submitted |
|---|---|---|---|---|---|---|---|---|
| NYC, PLUTO | near-line | 2500 | 1 | 20 | 1 | 0 | 2478 | 99.1 |
| NYC, PLUTO | random | 2500 | 4 | 9 | 2 | 0 | 2485 | 99.4 |
| NYC, Address Points | near-line | 1500 | 18 | 6 | 33 | 0 | 1443 | 96.2 |
| NYC, Address Points | random | 1500 | 7 | 9 | 33 | 0 | 1451 | 96.7 |
| Utah, Salt Lake County | near-line | 749 | 1 | 53 | 1 | 0 | 694 | 92.7 |
| Utah, Salt Lake County | random | 750 | 0 | 67 | 1 | 0 | 682 | 90.9 |
| Utah, six rural counties | near-line | 750 | 2 | 80 | 21 | 56 | 591 | 78.8 |
| Utah, six rural counties | random | 750 | 4 | 129 | 25 | 44 | 548 | 73.1 |
| National, largest-coverage counties | near-line | 564 | 5 | 26 | 4 | 0 | 529 | 93.8 |
| National, largest-coverage counties | random | 898 | 7 | 43 | 10 | 0 | 838 | 93.3 |
| National, smaller counties | near-line | 306 | 3 | 52 | 15 | 0 | 236 | 77.1 |
| National, smaller counties | random | 894 | 5 | 167 | 39 | 0 | 683 | 76.4 |
| TOTAL | near-line | 6369 | 30 | 237 | 75 | 56 | 5971 | 93.8 |
| TOTAL | random | 7292 | 27 | 424 | 110 | 44 | 6687 | 91.7 |

## S2. National Address Database counties (near-line stratum)
Source: results/v2_realdata_sensitivity/S4b_per_county.csv (cty = county FIPS).

| cty | n | wrong | rate_% | random_dir_% |
|---|---|---|---|---|
| AL|Baldwin | 15 | 0 | 0.0 | 19.13 |
| CA|Ventura | 67 | 0 | 0.0 | 12.29 |
| IL|Jo Daviess | 14 | 0 | 0.0 | 24.71 |
| IL|Lake | 52 | 0 | 0.0 | 17.29 |
| KY|Garrard | 50 | 3 | 6.0 | 28.33 |
| MA|Middlesex | 93 | 1 | 1.08 | 16.92 |
| ME|Kennebec | 20 | 0 | 0.0 | 23.95 |
| MN|Hennepin | 82 | 1 | 1.22 | 18.63 |
| MT|Deer Lodge | 29 | 0 | 0.0 | 19.95 |
| MT|Yellowstone | 58 | 0 | 0.0 | 20.86 |
| ND|Ransom | 11 | 0 | 0.0 | 30.45 |
| NY|Suffolk | 62 | 2 | 3.23 | 15.35 |
| NY|Yates | 21 | 0 | 0.0 | 34.9 |
| OK|Murray | 26 | 0 | 0.0 | 23.9 |
| OK|Tulsa | 41 | 1 | 2.44 | 20.61 |
| VA|Fairfax | 59 | 0 | 0.0 | 20.84 |
| VA|Halifax | 41 | 2 | 4.88 | 21.11 |
| WA|Snohomish | 24 | 2 | 8.33 | 30.52 |

## S3. Disagreement by reference placement type (near-line)
Source: results/v2_reference_sensitivity/R1_placement.csv.

| group | reference | n | wrong | rate_% | ci | random_dir_% |
|---|---|---|---|---|---|---|
| NYC, Address Points | structure/rooftop/address point | 1443 | 14 | 0.97 | [0.58, 1.62] | 15.012 |
| NYC, PLUTO | other placement | 2478 | 1 | 0.04 | [0.01, 0.23] | 11.484 |
| National, largest-coverage counties | other placement | 141 | 0 | 0.0 | [0.00, 2.65] | 14.645 |
| National, largest-coverage counties | structure/rooftop/address point | 388 | 5 | 1.289 | [0.55, 2.98] | 18.768 |
| National, smaller counties | other placement | 7 | 0 | 0.0 | [0.00, 35.43] | 41.071 |
| National, smaller counties | structure/rooftop/address point | 229 | 7 | 3.057 | [1.49, 6.17] | 25.415 |
| Utah, Salt Lake County | other placement | 694 | 5 | 0.72 | [0.31, 1.68] | 11.717 |
| Utah, six rural counties | other placement | 570 | 11 | 1.93 | [1.08, 3.42] | 10.661 |
| Utah, six rural counties | structure/rooftop/address point | 21 | 1 | 4.762 | [0.85, 22.67] | 14.619 |
| ALL | structure/rooftop/address point | 2081 | 27 | 1.297 | [0.89, 1.88] | 16.853 |

## S4. Block-face split under alternative definitions (near-line, matched edge found)
Source: results/v2_reference_sensitivity/R3_face_definition.csv. On the matched face = reference point projects onto the interior of the matched TIGER edge (not within the end tolerance of either end), lies on the side reported by the geocoder, and is within the distance threshold of the edge; multi-part edges use their longest part.

| dist_thr_m | end_tol_m | on_face_n | on_face_wrong | off_face_n | off_face_wrong |
|---|---|---|---|---|---|
| 30 | 1 | 4893 | 1 | 994 | 43 |
| 30 | 5 | 4819 | 1 | 1068 | 43 |
| 30 | 10 | 4684 | 1 | 1203 | 43 |
| 45 | 1 | 5516 | 2 | 371 | 42 |
| 45 | 5 | 5425 | 2 | 462 | 42 |
| 45 | 10 | 5273 | 2 | 614 | 42 |
| 60 | 1 | 5594 | 2 | 293 | 42 |
| 60 | 5 | 5501 | 2 | 386 | 42 |
| 60 | 10 | 5348 | 2 | 539 | 42 |
| 90 | 1 | 5607 | 2 | 280 | 42 |
| 90 | 5 | 5514 | 2 | 373 | 42 |
| 90 | 10 | 5360 | 2 | 527 | 42 |
| 120 | 1 | 5611 | 3 | 276 | 41 |
| 120 | 5 | 5518 | 3 | 369 | 41 |
| 120 | 10 | 5364 | 3 | 523 | 41 |

## S5. Reference jitter
Source: results/v2_reference_sensitivity/R2_jitter.csv.

| jitter_m | disagreement_% | range | on_face_n | on_face_wrong | off_face_n | off_face_wrong | face_class_changed_% |
|---|---|---|---|---|---|---|---|
| 5 | 0.78 | 0.75-0.80 | 5575.5 | 2.75 | 311.5 | 42.9 | 0.86 |
| 10 | 0.88 | 0.82-0.99 | 5523.05 | 3.0 | 363.95 | 48.85 | 2.12 |
| 20 | 5.72 | 5.20-6.51 | 4897.05 | 13.45 | 989.95 | 323.15 | 13.2 |

## S6. Match-quality flags
Sources: results/v2_blocks_policy/F1_match_anatomy.csv, F1c_flags.csv, F1d_flags_by_region.csv, F2_nonexact_by_region.csv.

| non_exact | diff | n | wrong | wrong_% | ci |
|---|---|---|---|---|---|
| False | city name only | 190 | 0 | 0.0 | [0.00, 1.98] |
| False | no difference | 2749 | 14 | 0.509 | [0.30, 0.85] |
| False | street name/type differs | 21 | 0 | 0.0 | [0.00, 15.46] |
| True | ZIP differs | 7 | 1 | 14.286 | [2.57, 51.31] |
| True | city name only | 2637 | 17 | 0.645 | [0.40, 1.03] |
| True | directional differs | 268 | 11 | 4.104 | [2.31, 7.20] |
| True | house number differs | 6 | 1 | 16.667 | [3.01, 56.35] |
| True | no difference | 12 | 0 | 0.0 | [0.00, 24.25] |
| True | street name/type differs | 81 | 0 | 0.0 | [0.00, 4.53] |

| flag | reviewed_% | caught | of | risk_answered_% | distance_same_workload_caught | distance_risk_answered_% |
|---|---|---|---|---|---|---|
| Non_Exact | 50.427 | 30 | 44 | 0.473 | 23 | 0.709 |
| house no./directional/street differs | 6.297 | 12 | 44 | 0.572 | 5 | 0.697 |
| house no./directional differs | 4.589 | 12 | 44 | 0.562 | 5 | 0.685 |

| group | flag | n | reviewed_% | caught | errors |
|---|---|---|---|---|---|
| NYC, PLUTO | Non_Exact | 2478 | 38.38 | 0 | 1 |
| NYC, PLUTO | house no./directional/street differs | 2478 | 1.33 | 0 | 1 |
| NYC, PLUTO | house no./directional differs | 2478 | 0.24 | 0 | 1 |
| NYC, Address Points | Non_Exact | 1443 | 92.45 | 14 | 14 |
| NYC, Address Points | house no./directional/street differs | 1443 | 2.15 | 1 | 14 |
| NYC, Address Points | house no./directional differs | 1443 | 0.35 | 1 | 14 |
| Utah, Salt Lake County | Non_Exact | 694 | 48.99 | 3 | 5 |
| Utah, Salt Lake County | house no./directional/street differs | 694 | 25.5 | 0 | 5 |
| Utah, Salt Lake County | house no./directional differs | 694 | 23.78 | 0 | 5 |
| Utah, six rural counties | Non_Exact | 591 | 26.57 | 10 | 12 |
| Utah, six rural counties | house no./directional/street differs | 591 | 10.83 | 10 | 12 |
| Utah, six rural counties | house no./directional differs | 591 | 10.66 | 10 | 12 |
| National, largest-coverage counties | Non_Exact | 529 | 36.86 | 3 | 5 |
| National, largest-coverage counties | house no./directional/street differs | 529 | 6.62 | 1 | 5 |
| National, largest-coverage counties | house no./directional differs | 529 | 4.91 | 1 | 5 |
| National, smaller counties | Non_Exact | 236 | 14.41 | 0 | 7 |
| National, smaller counties | house no./directional/street differs | 236 | 15.25 | 0 | 7 |
| National, smaller counties | house no./directional differs | 236 | 3.81 | 0 | 7 |

| group | nonexact_wrong | nonexact_n | exact_wrong | exact_n |
|---|---|---|---|---|
| NYC, PLUTO | 0 | 951 | 1 | 1527 |
| NYC, Address Points | 14 | 1334 | 0 | 109 |
| Utah, Salt Lake County | 3 | 340 | 2 | 354 |
| Utah, six rural counties | 10 | 157 | 2 | 434 |
| National, largest-coverage counties | 3 | 195 | 2 | 334 |
| National, smaller counties | 0 | 34 | 7 | 202 |

## S7. HUD 2026 Qualified Census Tracts
Source: results/v2_blocks_policy/Q1_qct_flips.csv and Q1b_cases.csv. For each address whose Census-returned tract differs from the reference tract, QCT status (HUD 2026 list, 14,539 tracts) of the two tracts is compared; a flip is a difference in status. Random stratum: 19 disagreements, 18 with a reference block found (one NYC Address Point fell outside every 2020 block polygon).

| near | wrong_tract | qct_status_flips | ref_qct | geo_qct |
|---|---|---|---|---|
| False | 18 | 2 | 2 | 4 |
| True | 44 | 8 | 5 | 5 |

## Data note
The archived geocoder inputs/outputs (data/geocoder_outputs/) contain street addresses taken from public open-data address files (NYC PLUTO, NYC Address Points, Utah SGID Address Points, USDOT NAD). They contain no names or other personal information; use follows the open-data terms of each source.
