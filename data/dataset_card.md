---
language: en
pretty_name: BoundaryBench v1
tags:
- geospatial
- benchmark
- synthetic-data
- evaluation
- geoai
license: cc-by-4.0
size_categories:
- 10K<n<100K
---

# BoundaryBench v1

## Dataset Summary

BoundaryBench v1 is a national benchmark of 13,000 synthetic latitude/longitude points covering 50 U.S. states plus Washington, D.C., labeled with ground-truth administrative regions at three granularities: census tract, ZCTA, and county.

The dataset is explicitly stratified by distance-to-boundary difficulty tiers to evaluate performance near borders and complex polygon geometries.

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total points | 13,000 |
| States covered | 51 (50 + DC) |
| Layers | tract (5k), zcta (4k), county (4k) |
| Source boundaries | TIGER/Line 2025 |

## Supported Tasks

- Point-in-polygon classification: Given (lat, lon), predict the containing region ID
- Boundary robustness evaluation: Measure accuracy degradation as distance approaches 0
- Cross-region generalization: Test on held-out states

## Data Generation

Points are sampled uniformly within polygon-derived bands in a projected CRS (EPSG:2163) and verified to satisfy strict distance-to-boundary constraints:

| Difficulty | Distance Range |
|------------|---------------|
| boundary | 0-10 m |
| hard | 10-100 m |
| edge | 10-100 m (complex polygons only) |
| medium | 100-500 m |
| easy | >= 500 m |

Latitude/longitude are exported in EPSG:4269 (NAD83).

## Splits

| Split | Description |
|-------|-------------|
| test | 10 held-out states: AK, CA, DC, FL, IL, MA, NY, OR, TX, WA |
| dev | 15% of remaining points, stratified by (layer, difficulty) |
| train | Remainder |

## Intended Use

BoundaryBench is intended for research evaluation of:
- Geospatial labeling systems
- LLM geographic reasoning capabilities
- Retrieval-augmented generation for location queries
- Geocoding and reverse-geocoding accuracy

## Limitations

- Points are synthetic; they do not represent population density or real user distribution
- Labels depend on source polygon data (TIGER/Line 2025) and geometry validity
- ZCTAs are approximations of ZIP codes, not exact matches
- U.S. coverage only

## Privacy

No personal data is included. All coordinates are synthetically generated and not derived from individuals or real addresses.

## License

CC-BY-4.0
