"""Positional-error simulation and uncertainty-aware assignment strategies.

Strategies (each sees only the reported point and an error scale R):
  crisp PIP          plain point-in-polygon on the reported point
  distance rule      abstain if the reported point is closer than tau to its polygon boundary
  Monte Carlo        share of N random samples (uniform disk of radius R) falling in each polygon
  disk overlay       area of polygon ∩ disk(R) / disk area — exact under a uniform-disk error model
  Gaussian overlay   Gaussian-weighted area fractions via equal-probability rings — matched to Gaussian error
"""
import math

import numpy as np
import pandas as pd
import shapely

from . import config as C
from .geo import locate


# ----------------------------------------------------------------------------- error simulation
def simulate_obs(x, y, model, R, rng):
    n = len(x)
    if model == "uniform":
        th = rng.uniform(0, 2 * np.pi, n)
        r = R * np.sqrt(rng.uniform(0, 1, n))
        return x + r * np.cos(th), y + r * np.sin(th)
    s = R / C.GAUSS_K95
    return x + rng.normal(0, s, n), y + rng.normal(0, s, n)


# ----------------------------------------------------------------------------- shared aggregation
def top_from_pairs(n, row, poly, w, true_idx):
    """From (row, polygon, weight) triples: top polygon per row, its weight, weight of the true polygon."""
    top = np.full(n, -1, dtype=np.int64)
    p_top = np.zeros(n)
    p_true = np.zeros(n)
    if len(row) == 0:
        return top, p_top, p_true
    df = pd.DataFrame({"row": row, "poly": poly, "w": w}).groupby(["row", "poly"], as_index=False)["w"].sum()
    best = df.sort_values(["row", "w"], ascending=[True, False]).drop_duplicates("row")
    top[best["row"].to_numpy()] = best["poly"].to_numpy()
    p_top[best["row"].to_numpy()] = best["w"].to_numpy()
    tm = df[df["poly"].to_numpy() == true_idx[df["row"].to_numpy()]]
    p_true[tm["row"].to_numpy()] = tm["w"].to_numpy()
    return top, p_top, p_true


# ----------------------------------------------------------------------------- Monte Carlo
def monte_carlo(L, x, y, R, n, rng, true_idx):
    """Uniform-disk Monte Carlo (identical random-number usage to the V2 run)."""
    M = len(x)
    th = rng.uniform(0, 2 * np.pi, (M, n))
    r = R * np.sqrt(rng.uniform(0, 1, (M, n)))
    lab = locate(L, (x[:, None] + r * np.cos(th)).ravel(), (y[:, None] + r * np.sin(th)).ravel())
    row = np.repeat(np.arange(M), n)
    keep = lab >= 0
    return top_from_pairs(M, row[keep], lab[keep], np.full(keep.sum(), 1.0 / n), true_idx)


def monte_carlo_gaussian(L, x, y, sigma, n, rng, true_idx):
    M = len(x)
    dx, dy = rng.normal(0, sigma, (M, n)), rng.normal(0, sigma, (M, n))
    lab = locate(L, (x[:, None] + dx).ravel(), (y[:, None] + dy).ravel())
    row = np.repeat(np.arange(M), n)
    keep = lab >= 0
    return top_from_pairs(M, row[keep], lab[keep], np.full(keep.sum(), 1.0 / n), true_idx)


# ----------------------------------------------------------------------------- overlays
def disk_pairs(L, x, y, r, quad_segs=64):
    """(row, polygon, area of polygon ∩ disk, disk area) for disks of radius r around (x, y)."""
    disks = shapely.buffer(shapely.points(x, y), r, quad_segs=quad_segs)
    inp, tr = L.tree.query(disks, predicate="intersects")
    disk_area = float(shapely.area(shapely.buffer(shapely.Point(0, 0), r, quad_segs=quad_segs)))
    if len(inp) == 0:
        return inp, tr, np.zeros(0), disk_area
    d = disks[inp]
    b = shapely.bounds(d)
    try:  # clip large polygons to the disk's bounding box first (same result, faster)
        poly = shapely.clip_by_rect(L.geoms[tr], b[:, 0], b[:, 1], b[:, 2], b[:, 3])
    except Exception:
        poly = L.geoms[tr]
    try:
        inter = shapely.intersection(poly, d)
    except Exception:
        inter = shapely.intersection(shapely.make_valid(poly), d)
    return inp, tr, shapely.area(inter), disk_area


def disk_overlay(L, x, y, R, true_idx):
    inp, tr, a, A = disk_pairs(L, x, y, R)
    return top_from_pairs(len(x), inp, tr, a / A, true_idx)


def ring_coefficients(sigma, n_rings=C.N_RINGS, q_max=C.Q_MAX, quad_segs=64):
    """Radii r_k with equal Gaussian mass per ring, and weights c_k such that
    P(polygon) ≈ sum_k c_k * Area(polygon ∩ disk(r_k)) / q_max  (density taken as uniform within each ring)."""
    q = np.linspace(0, q_max, n_rings + 1)[1:]
    r = sigma * np.sqrt(-2 * np.log(1 - q))
    A = np.array([float(shapely.area(shapely.buffer(shapely.Point(0, 0), rk, quad_segs=quad_segs))) for rk in r])
    dens = (q_max / n_rings) / np.diff(np.concatenate([[0.0], A]))
    c = dens - np.concatenate([dens[1:], [0.0]])
    return r, c


def gaussian_overlay(L, x, y, sigma, true_idx):
    r, c = ring_coefficients(sigma)
    rows, polys, ws = [], [], []
    for rk, ck in zip(r, c):
        inp, tr, a, _ = disk_pairs(L, x, y, rk)
        rows.append(inp); polys.append(tr); ws.append(ck * a)
    top, p_top, p_true = top_from_pairs(len(x), np.concatenate(rows), np.concatenate(polys), np.concatenate(ws), true_idx)
    return top, p_top / C.Q_MAX, p_true / C.Q_MAX


def gaussian_rmax(sigma):
    return sigma * math.sqrt(-2 * math.log(1 - C.Q_MAX))


# ----------------------------------------------------------------------------- theory
_erfc = np.vectorize(math.erfc)


def p_straight(d, R, model):
    """P(reported point lands across a straight boundary at distance d from the true point)."""
    d = np.asarray(d, float)
    if model == "uniform":
        u = np.clip(d / R, 0, 1)
        return (np.arccos(u) - u * np.sqrt(1 - u * u)) / np.pi
    s = R / C.GAUSS_K95
    return 0.5 * _erfc(d / (s * np.sqrt(2)))


def p_straight_empirical(d, rho):
    """Same, for an empirical sample of displacement magnitudes rho in uniformly random directions."""
    d = np.asarray(d, float)[:, None]
    r = np.asarray(rho, float)[None, :]
    return np.where(r > d, np.arccos(np.clip(d / np.maximum(r, 1e-9), -1, 1)) / np.pi, 0.0).mean(axis=1)
