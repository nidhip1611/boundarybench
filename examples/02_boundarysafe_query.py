"""
Example 2: BoundarySafe Single Query

Prerequisites:
1. Download TIGER/Line 2025 county shapefile from:
   https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
2. pip install geopandas pyproj shapely

Note: You must supply boundary polygons yourself; we do not distribute 
shapefiles in this repo.
"""
import sys
sys.path.insert(0, "..")

import geopandas as gpd
from src.boundarysafe import boundarysafe_lookup_latlon

# ============================================================
# 1. Load and project boundaries to EPSG:2163
# ============================================================
# Update this path to your downloaded shapefile
COUNTY_SHP = "path/to/tl_2025_us_county.shp"

print("Loading county boundaries...")
print("(Update COUNTY_SHP path to your downloaded shapefile)")

# Uncomment when you have the shapefile:
# counties = gpd.read_file(COUNTY_SHP).to_crs(2163)
# gdf_dict = {"county": counties}
# print(f"Loaded {len(counties)} counties")

# ============================================================
# 2. Query with BoundarySafe
# ============================================================
# Example coordinates (New York City)
lat, lon = 40.7128, -74.0060

print(f"\nQuery: lat={lat}, lon={lon}")

# Uncomment when you have the shapefile:
# result = boundarysafe_lookup_latlon(
#     lat=lat,
#     lon=lon,
#     layer="county",
#     gdf_dict=gdf_dict,
#     gps_radius_m=20,
#     p_thresh=0.90
# )
# 
# print(f"\nResult:")
# print(f"  Status: {result['status']}")
# print(f"  Label: {result['label_id']}")
# print(f"  Confidence: {result['confidence']}")
# print(f"  Distance to boundary: {result['dist_to_boundary_m']:.1f}m")
# print(f"  Candidates: {result['candidates']}")

# ============================================================
# 3. Expected output format
# ============================================================
print("\nExpected output format:")
expected = {
    "status": "answer",
    "label_id": "36061",
    "confidence": 0.95,
    "dist_to_boundary_m": 234.5,
    "candidates": [["36061", 0.95], ["36047", 0.05]],
    "lat": 40.7128,
    "lon": -74.0060
}
import json
print(json.dumps(expected, indent=2))
