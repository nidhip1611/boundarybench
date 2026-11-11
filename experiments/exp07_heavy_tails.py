"""EXP07 — Robustness to heavy-tailed positional error (SIMULATION, not validation).

Error models (isotropic; R = radius containing 95% of errors, given to every method):
  t3            bivariate Student-t, 3 d.f. (in the spirit of Zimmerman et al. 2007)
  contaminated  90% Gaussian + 10% Gaussian with 5x the scale
  lognormal     radial lognormal, median 61 m, p90 242 m, random direction
                (scale of the street-geocoding errors reported by Strickland et al. 2007)
On all 13,000 benchmark points, K = 5. Checks whether the d-based straight-line prediction still holds
(using the model's own radial distribution) and how distance rule / disk overlay behave when misspecified.

    python experiments/exp07_heavy_tails.py
Outputs -> results/v2_heavy_tails/
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd

from src import config as C
from src.geo import load_layers, load_points, locate, dist_to_own_boundary
from src.metrics import rc_summary, op_point
from src.report import Report
from src.uncertainty import disk_overlay, p_straight_empirical

RES = C.out_dir(C.RESULTS, "v2_heavy_tails")
RAW = C.out_dir(C.RAW, "heavy_tails")
rep = Report("EXP07 heavy-tailed error robustness (simulation)", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)
LAYERS = load_layers()
pts = load_points(LAYERS)
K = 5
NU = 3
LN_MU, LN_SD = math.log(61.0), (math.log(242.0) - math.log(61.0)) / 1.2816


def t_scale(R):           # bivariate t: |X|^2 / (2 s^2) ~ F(2, nu); P(F > x) = (1 + 2x/nu)^(-nu/2)
    x95 = (NU / 2) * (0.05 ** (-2 / NU) - 1)
    return R / math.sqrt(2 * x95)


def contam_sigma(R):      # 0.9 exp(-R^2/2s^2) + 0.1 exp(-R^2/2(5s)^2) = 0.05, solved by bisection
    lo, hi = 1e-3 * R, 10 * R
    for _ in range(200):
        s = (lo + hi) / 2
        tail = 0.9 * math.exp(-R * R / (2 * s * s)) + 0.1 * math.exp(-R * R / (50 * s * s))
        lo, hi = (s, hi) if tail < 0.05 else (lo, s)
    return s


def sample(model, R, n, rng):
    if model == "t3":
        s = t_scale(R); w = rng.chisquare(NU, n)
        return rng.normal(0, s, n) * np.sqrt(NU / w), rng.normal(0, s, n) * np.sqrt(NU / w)
    if model == "contaminated":
        s = contam_sigma(R) * np.where(rng.uniform(size=n) < 0.9, 1.0, 5.0)
        return rng.normal(0, 1, n) * s, rng.normal(0, 1, n) * s
    r = np.exp(rng.normal(LN_MU, LN_SD, n)); th = rng.uniform(0, 2 * np.pi, n)
    return r * np.cos(th), r * np.sin(th)


LN_R95 = float(np.exp(LN_MU + 1.6449 * LN_SD))
SETTINGS = [("t3", 20), ("t3", 50), ("contaminated", 20), ("contaminated", 50), ("lognormal", round(LN_R95, 1))]

rows_cfg, rows_bin, rows_m = [], [], []
for si, (model, R) in enumerate(SETTINGS):
    rng = np.random.default_rng(900 + si)
    dx, dy = sample(model, R, 200000, rng)
    rho = np.hypot(dx, dy)
    rows_cfg.append({"model": model, "R_95_m": R, "check_share_beyond_R_%": 100 * (rho > R).mean(),
                     "median_m": np.median(rho), "p99_m": np.quantile(rho, .99), "p99.9_m": np.quantile(rho, .999)})
    grid = np.linspace(0, max(3 * R, 1500.0), 601)
    curve = np.concatenate([p_straight_empirical(grid[i:i + 50], rho[:20000]) for i in range(0, len(grid), 50)])
    parts = []
    for lname, sub in pts.groupby("layer"):
        L = LAYERS[lname]
        rp = sub.loc[sub.index.repeat(K)].reset_index(drop=True)
        ex, ey = sample(model, R, len(rp), rng)
        x, y, t = rp["x"].to_numpy(), rp["y"].to_numpy(), rp["true_idx"].to_numpy()
        ox, oy = x + ex, y + ey
        crisp = locate(L, ox, oy)
        dist = dist_to_own_boundary(L, ox, oy, crisp)
        ex_idx, ex_p = crisp.copy(), np.ones(len(rp))
        near = np.where((dist < R) | (crisp < 0))[0]
        a, b, _ = disk_overlay(L, ox[near], oy[near], float(R), t[near]); ex_idx[near], ex_p[near] = a, b
        parts.append(pd.DataFrame({"point_id": rp["point_id"], "layer": lname, "d_true": rp["dist_to_boundary_m"],
                                   "true_idx": t, "crisp_idx": crisp, "dist_obs_m": dist, "ex_idx": ex_idx, "ex_p": ex_p,
                                   "err_m": np.hypot(ex, ey)}))
    d = pd.concat(parts, ignore_index=True)
    d.to_parquet(f"{RAW}/obs_{model}_R{R}.parquet", index=False)
    d["wrong"] = d["crisp_idx"] != d["true_idx"]
    d["pred"] = np.interp(d["d_true"].to_numpy(), grid, curve, right=0.0)
    d["dR"] = pd.cut(d["d_true"] / R, [0, .25, .5, .75, 1, 1.5, 2, 3, np.inf], right=False)
    b = d.groupby("dR", observed=True).agg(n=("wrong", "size"), observed_pct=("wrong", "mean"), predicted_pct=("pred", "mean"))
    b[["observed_pct", "predicted_pct"]] *= 100
    b.insert(0, "R", R); b.insert(0, "model", model); rows_bin.append(b.reset_index())
    t = d["true_idx"].to_numpy()
    for name, s, p, thr in [("Crisp PIP", np.ones(len(d)), d["crisp_idx"].to_numpy(), None),
                            ("Distance rule", d["dist_obs_m"].to_numpy(), d["crisp_idx"].to_numpy(), R),
                            ("Disk overlay", d["ex_p"].to_numpy(), d["ex_idx"].to_numpy(), C.THETA)]:
        row = {"model": model, "R": R, "method": name, **rc_summary(s, p != t)}
        if thr is not None:
            row.update(op_point(s, p, t, thr))
        rows_m.append(row)
    print(f"{model} R={R} done")

cfg = pd.DataFrame(rows_cfg).round(2); cfg.to_csv(f"{RES}/H0_error_models.csv", index=False)
hb = pd.concat(rows_bin, ignore_index=True).round(3); hb.to_csv(f"{RES}/H1_dR_observed_vs_predicted.csv", index=False)
hm = pd.DataFrame(rows_m).round(3); hm.to_csv(f"{RES}/H2_strategies.csv", index=False)
rep.table("[H0] Error models (R = 95% radius; heavier tails = larger p99 / p99.9 relative to R)", cfg, index=False)
rep.table("[H1] Wrong-region rate by d/R: observed vs straight-line prediction using each model's own radial distribution", hb, index=False)
rep.table("[H2] Strategies under heavy tails (methods assume a uniform disk of radius R: misspecified by design)", hm, index=False)
rep.save()
