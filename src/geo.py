"""Boundary layers, benchmark points and basic point-in-polygon operations (shapely 2, vectorised)."""
import glob
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from . import config as C


class Layer:
    """One administrative layer: polygon ids, geometries, spatial index, boundaries."""

    def __init__(self, ids, geoms):
        self.ids, self.geoms = ids, geoms
        shapely.prepare(self.geoms)
        self.tree = shapely.STRtree(self.geoms)
        self.bounds = shapely.boundary(self.geoms)
        self.id2idx = {g: i for i, g in enumerate(ids)}


def _read(paths, id_col):
    if not paths:
        raise FileNotFoundError(f"No shapefiles found — check BB_TIGER ({C.TIGER})")
    gdf = pd.concat([gpd.read_file(p, engine="pyogrio", columns=[id_col]) for p in paths], ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=4269).to_crs(C.CRS_M)
    geoms = gdf.geometry.to_numpy()
    bad = ~shapely.is_valid(geoms)
    if bad.any():
        geoms[bad] = shapely.make_valid(geoms[bad])
    return gdf[id_col].astype(str).to_numpy(), geoms


def load_layers(names=("county", "zcta", "tract"), verbose=True):
    files = {
        "county": glob.glob(os.path.join(C.TIGER, "COUNTY", "*.shp")),
        "zcta": glob.glob(os.path.join(C.TIGER, "ZCTA520", "*.shp")),
        "tract": sorted(glob.glob(os.path.join(C.TIGER, "TRACT", "*.shp"))),
    }
    layers = {}
    for n in names:
        layers[n] = Layer(*_read(files[n], C.LAYER_ID[n]))
        if verbose:
            print(f"{n}: {len(layers[n].ids):,} polygons")
    return layers


def load_points(layers):
    """BoundaryBench points (true locations) projected to metres, with the index of their true polygon."""
    pts = pd.read_parquet(C.DATA).reset_index(drop=True)
    pts["point_id"] = np.arange(len(pts))
    pts["label_id"] = [str(v).split(".")[0].zfill(C.LABEL_WIDTH[l]) for v, l in zip(pts["label_id"], pts["layer"])]
    g = gpd.GeoSeries(gpd.points_from_xy(pts["lon"], pts["lat"]), crs=4269).to_crs(C.CRS_M)
    pts["x"], pts["y"] = g.x.to_numpy(), g.y.to_numpy()
    pts["true_idx"] = [layers[l].id2idx.get(v, -1) for l, v in zip(pts["layer"], pts["label_id"])]
    missing = int((pts["true_idx"] < 0).sum())
    if missing:
        print(f"warning: {missing} labels not found in TIGER layers (dropped)")
    return pts[pts["true_idx"] >= 0].reset_index(drop=True)


def locate(L, x, y):
    """Index of the polygon containing each point (-1 if none)."""
    out = np.full(len(x), -1, dtype=np.int64)
    if len(x) == 0:
        return out
    inp, tr = L.tree.query(shapely.points(x, y), predicate="within")
    out[inp] = tr
    return out


def dist_to_own_boundary(L, x, y, idx):
    """Distance from each point to the boundary of its containing polygon (0 if outside every polygon)."""
    d = np.zeros(len(x))
    m = idx >= 0
    if m.any():
        d[m] = shapely.distance(shapely.points(x[m], y[m]), L.bounds[idx[m]])
    return d
