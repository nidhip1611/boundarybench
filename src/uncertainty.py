"""Positional-error simulation and uncertainty-aware assignment strategies.

Strategies (each sees only the reported point and an error scale R):
  crisp PIP          plain point-in-polygon on the reported point
  distance rule      abstain if the reported point is closer than tau to its polygon boundary
  Monte Carlo        share of N random samples (uniform disk of radius R) falling in each polygon
  disk overlay       area of polygon ∩ disk(R) / disk area — exact under a uniform-disk error model
  Gaussian overlay   Gaussian-weighted area fractions (radial Gauss-Legendre quadrature) — matched to Gaussian error
"""
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
    poly = L.geoms[tr]
    try:
        inter = shapely.intersection(poly, d)
    except Exception:
        inter = shapely.intersection(shapely.make_valid(poly), d)
    return inp, tr, shapely.area(inter), disk_area


def disk_overlay(L, x, y, R, true_idx):
    inp, tr, a, A = disk_pairs(L, x, y, R)
    return top_from_pairs(len(x), inp, tr, a / A, true_idx)


def radial_quadrature(sigma, n=C.GAUSS_NODES, rmax_sig=C.GAUSS_RMAX_SIG, quad_segs=64):
    """Radii r_k and weights w_k so that, for an isotropic Gaussian with std sigma,
    P(polygon) ≈ sum_k w_k * Area(polygon ∩ disk(r_k)).
    Derivation: P = ∫ phi(r) dA(r) = ∫ A(r) * (r / sigma^2) * phi(r) dr (integration by parts, phi = 2-D density),
    evaluated with Gauss-Legendre on [0, rmax]; weights are normalised so a polygon covering everything gets P = 1."""
    x, w = np.polynomial.legendre.leggauss(n)
    b = rmax_sig * sigma
    r = b / 2 * (x + 1)
    w = w * b / 2 * (r / sigma ** 2) * np.exp(-r * r / (2 * sigma * sigma)) / (2 * np.pi * sigma * sigma)
    A = np.array([float(shapely.area(shapely.buffer(shapely.Point(0, 0), rk, quad_segs=quad_segs))) for rk in r])
    return r, w / float((w * A).sum())


def gaussian_overlay(L, x, y, sigma, true_idx):
    r, wk = radial_quadrature(sigma)
    rows, polys, ws = [], [], []
    for rk, ck in zip(r, wk):
        inp, tr, a, _ = disk_pairs(L, x, y, rk)
        rows.append(inp); polys.append(tr); ws.append(ck * a)
    return top_from_pairs(len(x), np.concatenate(rows), np.concatenate(polys), np.concatenate(ws), true_idx)


def gaussian_rmax(sigma):
    """Beyond this distance from every boundary the Gaussian overlay returns P = 1 (missing mass ~4e-6)."""
    return C.GAUSS_RMAX_SIG * sigma


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
