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

## S8. The 44 near-line disagreements, case by case
Source: results/v2_blocks_policy/S8_disagreement_cases.csv (from F1b_error_cases.csv and v2_matched_edge/M_points.csv).

| group | case | match_type | diff | ref_to_edge_m | input | out_address |
|---|---|---|---|---|---|---|
| NYC, Address Points | adjacent block face, same street | Non_Exact | city name only | 24.5 | 2459 OCEAN AVE, New York, NY, 11229 | 2459 OCEAN AVE, BROOKLYN, NY, 11229 |
| NYC, Address Points | adjacent block face, same street | Non_Exact | city name only | 28.5 | 210-02 113 AVE, New York, NY, 11429 | 210-02 113TH AVE, QUEENS VILLAGE, NY, 11429 |
| NYC, Address Points | adjacent block face, same street | Non_Exact | city name only | 54.9 | 60-28 FRESH POND RD, New York, NY, 11378 | 60-28 FRESH POND RD, MASPETH, NY, 11378 |
| NYC, Address Points | adjacent block face, same street | Non_Exact | city name only | 28.9 | 113-42 196 ST, New York, NY, 11412 | 113-42 196TH ST, SAINT ALBANS, NY, 11412 |
| NYC, Address Points | adjacent block face, same street | Non_Exact | city name only | 24.5 | 3851 FLATLANDS AVE, New York, NY, 11234 | 3851 FLATLANDS AVE, BROOKLYN, NY, 11234 |
| NYC, Address Points | adjacent block face, same street | Non_Exact | city name only | 54.5 | 1329 FLATBUSH AVE, New York, NY, 11226 | 1329 FLATBUSH AVE, BROOKLYN, NY, 11226 |
| National, largest-coverage counties | adjacent block face, same street | Non_Exact | city name only | 50.8 | 8340 Highway 7, Not stated, MN, 55375 | 8340 STATE HWY 7, SAINT BONIFACIUS, MN, 55375 |
| National, smaller counties | adjacent block face, same street | Exact | no difference | 22.5 | 35 PUBLIC Square, LANCASTER, KY, 40444 | 35 PUBLIC SQ, LANCASTER, KY, 40444 |
| National, smaller counties | adjacent block face, same street | Exact | no difference | 37.7 | 1826 178TH Street Southwest, LYNNWOOD, WA, 98037 | 1826 178TH ST SW, LYNNWOOD, WA, 98037 |
| Utah, Salt Lake County | adjacent block face, same street | Exact | no difference | 31.9 | 4742 W DUCKHORN DR, SOUTH JORDAN, UT, 84009 | 4742 W DUCKHORN DR, SOUTH JORDAN, UT, 84009 |
| Utah, Salt Lake County | adjacent block face, same street | Non_Exact | city name only | 27.6 | 2127 E 11270 S, SANDY CITY, UT, 84092 | 2127 E 11270 S, SANDY, UT, 84092 |
| Utah, Salt Lake County | adjacent block face, same street | Exact | no difference | 56.2 | 2930 S 2000 E, SALT LAKE CITY, UT, 84109 | 2930 S 2000 E, SALT LAKE CITY, UT, 84109 |
| NYC, Address Points | matched a different address | Non_Exact | house number differs | 202.1 | 107-18 ASCAN AVE, New York, NY, 11375 | 107 ASCAN AVE, FOREST HILLS, NY, 11375 |
| National, largest-coverage counties | matched a different address | Non_Exact | directional differs | 39.1 | 2193 South MAIN Street, BROKEN ARROW, OK, 74012 | 2193 MAIN ST, BROKEN ARROW, OK, 74012 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 37.0 | 1600 W HWY 40, VERNAL, UT, 84078 | 1600 E US HWY 40, VERNAL, UT, 84078 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 51.2 | 58 S HWY 118, , UT, 84754 | 58 STATE RTE 118, MONROE, UT, 84754 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 326.0 | 104 N MAIN ST, RICHFIELD CITY, UT, 84701 | 104 S MAIN ST, RICHFIELD, UT, 84701 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 392.2 | 154 N MAIN ST, RICHFIELD CITY, UT, 84701 | 154 S MAIN ST, RICHFIELD, UT, 84701 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 375.4 | 142 N MAIN ST, RICHFIELD CITY, UT, 84701 | 142 S MAIN ST, RICHFIELD, UT, 84701 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 369.1 | 136 N MAIN ST, RICHFIELD CITY, UT, 84701 | 136 S MAIN ST, RICHFIELD, UT, 84701 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 402.1 | 160 N MAIN ST, RICHFIELD CITY, UT, 84701 | 160 S MAIN ST, RICHFIELD, UT, 84701 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 79.7 | 1335 S HWY 6, , UT, 84501 | 1335 US HWY 6, PRICE, UT, 84501 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 330.3 | 108 N MAIN ST, RICHFIELD CITY, UT, 84701 | 108 S MAIN ST, RICHFIELD, UT, 84701 |
| Utah, six rural counties | matched a different address | Non_Exact | directional differs | 386.6 | 319 N 200 E, EPHRAIM, UT, 84627 | 319 E 200 N, EPHRAIM, UT, 84627 |
| NYC, Address Points | on matched face | Non_Exact | city name only | 33.6 | 170-04 NORTHERN BLVD, New York, NY, 11358 | 170-04 NORTHERN BLVD, FLUSHING, NY, 11358 |
| National, largest-coverage counties | on matched face | Non_Exact | city name only | 17.1 | 44 RICH Street, Not stated, MA, 02148 | 44 RICH ST, MALDEN, MA, 02148 |
| National, largest-coverage counties | other side, same block | Exact | no difference | 22.2 | 72 West 11th Street, Huntington Station, NY, 11746 | 72 W 11TH ST, HUNTINGTON STATION, NY, 11746 |
| Utah, six rural counties | other side, same block | Exact | no difference | 28.1 | 487 W 500 S, VERNAL, UT, 84078 | 487 W 500 S, VERNAL, UT, 84078 |
| NYC, Address Points | reference >60 m from matched street, same address text | Non_Exact | city name only | 64.6 | 7 HUGH J GRANT CIR, New York, NY, 10462 | 7 HUGH J GRANT CIR, BRONX, NY, 10462 |
| NYC, Address Points | reference >60 m from matched street, same address text | Non_Exact | city name only | 138.3 | 63-01 99 ST, New York, NY, 11374 | 63-01 99TH ST, REGO PARK, NY, 11374 |
| NYC, Address Points | reference >60 m from matched street, same address text | Non_Exact | city name only | 305.3 | 2 SUMPTER ST, New York, NY, 11233 | 2 SUMPTER ST, BROOKLYN, NY, 11233 |
| NYC, Address Points | reference >60 m from matched street, same address text | Non_Exact | city name only | 95.7 | 1555 OVINGTON AVE, New York, NY, 11219 | 1555 OVINGTON AVE, BROOKLYN, NY, 11219 |
| NYC, Address Points | reference >60 m from matched street, same address text | Non_Exact | city name only | 104.1 | 1494 E  35 ST, New York, NY, 11234 | 1494 E 35TH ST, BROOKLYN, NY, 11234 |
| NYC, Address Points | reference >60 m from matched street, same address text | Non_Exact | city name only | 104.8 | 1559 OVINGTON AVE, New York, NY, 11219 | 1559 OVINGTON AVE, BROOKLYN, NY, 11219 |
| NYC, PLUTO | reference >60 m from matched street, same address text | Exact | no difference | 118.3 | 1492 EAST 35 STREET, Brooklyn, NY, 11234 | 1492 E 35TH ST, BROOKLYN, NY, 11234 |
| National, largest-coverage counties | reference >60 m from matched street, same address text | Exact | no difference | 125.1 | 4 Hunters Lane, Huntington Station, NY, 11746 | 4 HUNTERS LN, HUNTINGTON STATION, NY, 11746 |
| National, smaller counties | reference >60 m from matched street, same address text | Exact | no difference | 339.5 | 1123 Old RAILROAD GRADE Road, LANCASTER, KY, 40444 | 1123 OLD RAILROAD GRADE RD, LANCASTER, KY, 40444 |
| National, smaller counties | reference >60 m from matched street, same address text | Exact | no difference | 95.5 | 1427 KEMPER Lane, LANCASTER, KY, 40444 | 1427 KEMPER LN, LANCASTER, KY, 40444 |
| National, smaller counties | reference >60 m from matched street, same address text | Exact | no difference | 90.1 | 3602 200TH Place Southeast, BOTHELL, WA, 98012 | 3602 200TH PL SE, BOTHELL, WA, 98012 |
| National, smaller counties | reference >60 m from matched street, same address text | Exact | no difference | 317.8 | 1712 Peytonsburg Road, Vernon Hill, VA, 24597 | 1712 PEYTONSBURG RD, VERNON HILL, VA, 24597 |
| National, smaller counties | reference >60 m from matched street, same address text | Exact | no difference | 293.0 | 1076 Huell Matthews Highway, South Boston, VA, 24592 | 1076 HUELL MATTHEWS HWY, SOUTH BOSTON, VA, 24592 |
| Utah, Salt Lake County | reference >60 m from matched street, same address text | Non_Exact | ZIP differs | 458.6 | 3995 S REDWOOD RD, WEST VALLEY CITY, UT, 84123 | 3995 S REDWOOD RD, WEST VALLEY CITY, UT, 84119 |
| Utah, Salt Lake County | reference >60 m from matched street, same address text | Non_Exact | city name only | 75.3 | 6790 S 400 W, MURRAY, UT, 84047 | 6790 S 400 W, MIDVALE, UT, 84047 |
| Utah, six rural counties | reference >60 m from matched street, same address text | Exact | no difference | 91.1 | 849 W MAIN ST, VERNAL, UT, 84078 | 849 W MAIN ST, VERNAL, UT, 84078 |
