"""Regenerate the exact EXP01 reported locations (same seeds and ordering as experiments/exp01_v2_main.py)."""
import numpy as np

from . import config as C
from .uncertainty import simulate_obs


def regenerate(pts, model, R, K=C.K_OBS):
    """Return {layer: (rep, ox, oy)}; rep has one row per observation (point_id, k, x, y, true_idx, ...)."""
    out = {}
    for li, (lname, sub) in enumerate(pts.groupby("layer")):
        rng = np.random.default_rng(1000 * R + 100 * C.MODELS.index(model) + li)
        rep = sub.loc[sub.index.repeat(K)].reset_index(drop=True)
        rep["k"] = np.tile(np.arange(K), len(sub))
        ox, oy = simulate_obs(rep["x"].to_numpy(), rep["y"].to_numpy(), model, R, rng)
        out[lname] = (rep, ox, oy)
    return out
