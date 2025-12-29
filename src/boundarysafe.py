"""
BoundarySafe: Boundary-Aware Tool-Augmented Containment with Uncertainty

This module implements the BoundarySafe method for geographic boundary resolution
with Monte Carlo stability estimation.
"""

import numpy as np
from collections import Counter
from shapely.geometry import Point
from pyproj import Transformer


# Transformer: EPSG:4326 (WGS84 lat/lon) -> EPSG:2163 (US National Atlas, meters)
# always_xy=True ensures input order is (lon, lat), not (lat, lon)
_transformer_to_meters = Transformer.from_crs("EPSG:4326", "EPSG:2163", always_xy=True)


def _check_crs(gdf, layer):
    """Verify GeoDataFrame is projected to EPSG:2163."""
    if gdf.crs is None:
        raise ValueError(f"gdf_dict['{layer}'] has no CRS. Must be projected to EPSG:2163.")
    
    epsg = gdf.crs.to_epsg()
    if epsg != 2163:
        raise ValueError(
            f"gdf_dict['{layer}'] is in EPSG:{epsg}. Must be projected to EPSG:2163. "
            f"Use: gdf = gdf.to_crs(2163)"
        )


def exact_lookup(x_m, y_m, layer, gdf_dict):
    """
    Exact point-in-polygon lookup using covers() for boundary robustness.
    
    Args:
        x_m: X coordinate in meters (EPSG:2163)
        y_m: Y coordinate in meters (EPSG:2163)
        layer: One of "county", "zcta", "tract"
        gdf_dict: Dictionary with GeoDataFrames for each layer (must be EPSG:2163)
    
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
    
    # Verify required column exists
    if id_col not in gdf.columns:
        raise ValueError(
            f"Column '{id_col}' not found in gdf_dict['{layer}']. "
            f"Available columns: {list(gdf.columns)}"
        )
    
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
    
    # Distance to boundary in meters (EPSG:2163 units)
    dist_to_boundary = match.geometry.boundary.distance(point)
    
    return label_id, dist_to_boundary


def sample_disk(x_m, y_m, radius_m, n, rng):
    """
    Sample n points uniformly in a disk of radius_m around (x_m, y_m).
    
    Args:
        x_m: Center X coordinate (meters)
        y_m: Center Y coordinate (meters)
        radius_m: Disk radius in meters
        n: Number of samples
        rng: NumPy random generator
    
    Returns:
        (x_samples, y_samples) arrays in meters
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
        x_m: X coordinate in meters (EPSG:2163)
        y_m: Y coordinate in meters (EPSG:2163)
        layer: One of "county", "zcta", "tract"
        gdf_dict: Dictionary with GeoDataFrames for each layer (must be EPSG:2163)
        gps_radius_m: GPS uncertainty radius in meters (default 20)
        n_samples: Number of Monte Carlo samples (default 100)
        p_thresh: Confidence threshold for answering (default 0.90)
        rng: NumPy random generator (optional)
    
    Returns:
        dict with keys:
            - label_id: predicted label (or top candidate if abstain)
            - confidence: probability of top label
            - dist_to_boundary_m: distance to boundary in meters
            - status: "answer" or "abstain"
            - candidates: list of [label, probability] pairs
    """
    if rng is None:
        rng = np.random.default_rng(42)
    
    # Verify CRS
    _check_crs(gdf_dict[layer], layer)
    
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
            "candidates": [[label_orig, 1.0]]
        }
    
    total = sum(counts.values())
    top_label, top_count = counts.most_common(1)[0]
    p_top = top_count / total
    
    # Build candidates list (JSON-serializable format)
    candidates = [[label, count/total] for label, count in counts.most_common(2)]
    
    # 3. Decision: answer or abstain
    if p_top >= p_thresh:
        return {
            "label_id": top_label,
            "confidence": round(p_top, 4),
            "dist_to_boundary_m": round(dist_orig, 2),
            "status": "answer",
            "candidates": candidates
        }
    else:
        return {
            "label_id": top_label,
            "confidence": round(p_top, 4),
            "dist_to_boundary_m": round(dist_orig, 2),
            "status": "abstain",
            "candidates": candidates
        }


def boundarysafe_lookup_latlon(lat, lon, layer, gdf_dict, gps_radius_m=20,
                                n_samples=100, p_thresh=0.90, rng=None):
    """
    BoundarySafe lookup using lat/lon coordinates (user-friendly wrapper).
    
    Transforms EPSG:4326 (WGS84) coordinates to EPSG:2163 (meters) and
    calls boundarysafe_lookup.
    
    Args:
        lat: Latitude in EPSG:4326 (WGS84)
        lon: Longitude in EPSG:4326 (WGS84)
        layer: One of "county", "zcta", "tract"
        gdf_dict: Dictionary with GeoDataFrames for each layer (must be EPSG:2163)
        gps_radius_m: GPS uncertainty radius in meters (default 20)
        n_samples: Number of Monte Carlo samples (default 100)
        p_thresh: Confidence threshold for answering (default 0.90)
        rng: NumPy random generator (optional)
    
    Returns:
        dict with keys:
            - label_id: predicted label
            - confidence: probability of top label
            - dist_to_boundary_m: distance to boundary in meters
            - status: "answer" or "abstain"
            - candidates: list of [label, probability] pairs
            - lat: input latitude
            - lon: input longitude
    
    Example:
        >>> counties = gpd.read_file("counties.shp").to_crs(2163)
        >>> gdf_dict = {"county": counties}
        >>> result = boundarysafe_lookup_latlon(40.7128, -74.0060, "county", gdf_dict)
    """
    # Transform lat/lon (EPSG:4326) to meters (EPSG:2163)
    # Note: always_xy=True means input order is (lon, lat)
    x_m, y_m = _transformer_to_meters.transform(lon, lat)
    
    # Run BoundarySafe
    result = boundarysafe_lookup(
        x_m=x_m, 
        y_m=y_m, 
        layer=layer, 
        gdf_dict=gdf_dict, 
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
    print("  - exact_lookup(x_m, y_m, layer, gdf_dict)")
    print("  - boundarysafe_lookup(x_m, y_m, layer, gdf_dict, ...)")
    print("  - boundarysafe_lookup_latlon(lat, lon, layer, gdf_dict, ...)")
    print()
    print("Example:")
    print("  # Load and project boundaries")
    print("  counties = gpd.read_file('counties.shp').to_crs(2163)")
    print("  gdf_dict = {'county': counties}")
    print()
    print("  # Query with lat/lon")
    print("  result = boundarysafe_lookup_latlon(40.7128, -74.0060, 'county', gdf_dict)")
