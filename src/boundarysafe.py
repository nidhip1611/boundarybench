"""
BoundarySafe: Boundary-Aware Tool-Augmented Containment with Uncertainty

This module implements the BoundarySafe method for geographic boundary resolution
with Monte Carlo stability estimation.
"""

import numpy as np
from collections import Counter
from shapely.geometry import Point
from pyproj import Transformer


# Default transformer: WGS84 (lat/lon) -> EPSG:2163 (meters)
_transformer_to_meters = Transformer.from_crs("EPSG:4269", "EPSG:2163", always_xy=True)
_transformer_to_latlon = Transformer.from_crs("EPSG:2163", "EPSG:4269", always_xy=True)


def exact_lookup(x_m, y_m, layer, gdf_dict):
    """
    Exact point-in-polygon lookup using covers() for boundary robustness.
    
    Args:
        x_m: X coordinate in meters (projected CRS)
        y_m: Y coordinate in meters (projected CRS)
        layer: One of "county", "zcta", "tract"
        gdf_dict: Dictionary with GeoDataFrames for each layer
    
    Returns:
        (label_id, dist_to_boundary_m) or (None, None) if not found
    """
    point = Point(x_m, y_m)
    
    gdf = gdf_dict[layer]
    id_col = {
        "county": "GEOID",
        "zcta": "ZCTA5CE20", 
        "tract": "GEOID"
    }[layer]
    
    # Spatial index lookup
    possible_idx = list(gdf.sindex.intersection(point.bounds))
    if not possible_idx:
        return None, None
    
    possible = gdf.iloc[possible_idx]
    
    # Use covers() instead of contains() for boundary robustness
    # covers() returns True if point is ON the boundary
    matches = possible[possible.covers(point)]
    
    # Fallback to contains() if covers() fails
    if len(matches) == 0:
        matches = possible[possible.contains(point)]
    
    if len(matches) == 0:
        return None, None
    
    match = matches.iloc[0]
    label_id = str(match[id_col])
    dist_to_boundary = match.geometry.boundary.distance(point)
    
    return label_id, dist_to_boundary


def sample_disk(x_m, y_m, radius_m, n, rng):
    """
    Sample n points uniformly in a disk of radius_m around (x_m, y_m).
    
    Args:
        x_m: Center X coordinate
        y_m: Center Y coordinate
        radius_m: Disk radius in meters
        n: Number of samples
        rng: NumPy random generator
    
    Returns:
        (x_samples, y_samples) arrays
    """
    theta = rng.uniform(0, 2 * np.pi, n)
    r = radius_m * np.sqrt(rng.uniform(0, 1, n))
    x_samples = x_m + r * np.cos(theta)
    y_samples = y_m + r * np.sin(theta)
    return x_samples, y_samples


def boundarysafe_lookup(x_m, y_m, layer, gdf_dict, gps_radius_m=20, 
                        n_samples=100, p_thresh=0.90, rng=None):
    """
    BoundarySafe: Boundary-aware containment with uncertainty estimation.
    
    Args:
        x_m: X coordinate in meters (projected CRS)
        y_m: Y coordinate in meters (projected CRS)
        layer: One of "county", "zcta", "tract"
        gdf_dict: Dictionary with GeoDataFrames for each layer
        gps_radius_m: GPS uncertainty radius (default 20m)
        n_samples: Number of Monte Carlo samples (default 100)
        p_thresh: Confidence threshold for answering (default 0.90)
        rng: NumPy random generator (optional)
    
    Returns:
        dict with keys:
            - label_id: predicted label (or top candidate if abstain)
            - confidence: probability of top label
            - dist_to_boundary_m: distance to boundary
            - status: "answer" or "abstain"
            - candidates: top-2 candidates if abstain
    """
    if rng is None:
        rng = np.random.default_rng(42)
    
    # 1. Exact lookup for original point
    label_orig, dist_orig = exact_lookup(x_m, y_m, layer, gdf_dict)
    
    if label_orig is None:
        return {
            "label_id": None,
            "confidence": 0.0,
            "dist_to_boundary_m": None,
            "status": "error",
            "candidates": []
        }
    
    # 2. Monte Carlo stability estimation
    x_samples, y_samples = sample_disk(x_m, y_m, gps_radius_m, n_samples, rng)
    
    counts = Counter()
    for x_s, y_s in zip(x_samples, y_samples):
        label_s, _ = exact_lookup(x_s, y_s, layer, gdf_dict)
        if label_s is not None:
            counts[label_s] += 1
    
    if not counts:
        return {
            "label_id": label_orig,
            "confidence": 1.0,
            "dist_to_boundary_m": dist_orig,
            "status": "answer",
            "candidates": [(label_orig, 1.0)]
        }
    
    total = sum(counts.values())
    top_label, top_count = counts.most_common(1)[0]
    p_top = top_count / total
    
    # 3. Decision: answer or abstain
    if p_top >= p_thresh:
        return {
            "label_id": top_label,
            "confidence": p_top,
            "dist_to_boundary_m": dist_orig,
            "status": "answer",
            "candidates": [(l, c/total) for l, c in counts.most_common(2)]
        }
    else:
        return {
            "label_id": top_label,
            "confidence": p_top,
            "dist_to_boundary_m": dist_orig,
            "status": "abstain",
            "candidates": [(l, c/total) for l, c in counts.most_common(2)]
        }


def boundarysafe_lookup_latlon(lat, lon, layer, gdf_dict, gps_radius_m=20,
                                n_samples=100, p_thresh=0.90, rng=None):
    """
    BoundarySafe lookup using lat/lon coordinates (user-friendly wrapper).
    
    Args:
        lat: Latitude (WGS84 / NAD83)
        lon: Longitude (WGS84 / NAD83)
        layer: One of "county", "zcta", "tract"
        gdf_dict: Dictionary with GeoDataFrames for each layer (projected to EPSG:2163)
        gps_radius_m: GPS uncertainty radius (default 20m)
        n_samples: Number of Monte Carlo samples (default 100)
        p_thresh: Confidence threshold for answering (default 0.90)
        rng: NumPy random generator (optional)
    
    Returns:
        dict with keys:
            - label_id: predicted label
            - confidence: probability of top label
            - dist_to_boundary_m: distance to boundary
            - status: "answer" or "abstain"
            - candidates: top-2 candidates
            - lat: input latitude
            - lon: input longitude
    """
    # Transform lat/lon to meters
    x_m, y_m = _transformer_to_meters.transform(lon, lat)
    
    # Run BoundarySafe
    result = boundarysafe_lookup(
        x_m, y_m, layer, gdf_dict, 
        gps_radius_m=gps_radius_m,
        n_samples=n_samples,
        p_thresh=p_thresh,
        rng=rng
    )
    
    # Add input coordinates to result
    result["lat"] = lat
    result["lon"] = lon
    
    return result


if __name__ == "__main__":
    print("BoundarySafe module loaded successfully")
    print()
    print("Functions:")
    print("  - boundarysafe_lookup(x_m, y_m, layer, gdf_dict, ...)")
    print("  - boundarysafe_lookup_latlon(lat, lon, layer, gdf_dict, ...)")
    print()
    print("Example:")
    print("  result = boundarysafe_lookup_latlon(40.7128, -74.0060, 'county', gdf_dict)")
