"""EXP06 — Targeted geometry stress set: junctions, corners, slivers, water edges (vs straight controls).

The original benchmark has few near-boundary points at junctions/corners (EXP02). Here we sample new true
points within 50 m of real boundaries of all three layers, classify their local geometry at R = 50 m,
keep up to 400 points per class per layer, and simulate 20 noisy reports per point at R = 20 and 50 m
(uniform and Gaussian). For each class we compare the observed wrong-region rate with the straight-boundary
prediction, and compare abstention strategies (distance rule vs disk / Gaussian overlay): this is where the
probability methods should beat the distance rule if geometry matters.

    python experiments/exp06_geometry_stress.py
Outputs -> results/v2_geometry_stress/     Stress points -> $BB_WORK/outputs/geometry_stress/points.parquet
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd
import shapely

from src import config as C
from src.geo import load_layers, locate, dist_to_own_boundary
from src.localgeom import classify
from src.metrics import rc_summary
from src.report import Report
from src.stats import point_bootstrap
from src.uncertainty import simulate_obs, p_straight, disk_overlay, gaussian_overlay, gaussian_rmax

RES = C.out_dir(C.RESULTS, "v2_geometry_stress")
RAW = C.out_dir(C.RAW, "geometry_stress")
rep = Report("EXP06 geometry stress set", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)
LAYERS = load_layers()
N_CAND, PER_CLASS, K, MAXD = 40000, 400, 20, 50.0

# ----------------------------------------------------------------------------- 1. build the stress set
pts_path = f"{RAW}/points.parquet"
if not os.path.exists(pts_path):
    parts = []
    for li, (lname, L) in enumerate(LAYERS.items()):
        rng = np.random.default_rng(600 + li)
        pid = rng.integers(0, len(L.geoms), N_CAND)
        ring = shapely.get_exterior_ring(shapely.get_geometry(L.geoms[pid], 0))
        P = shapely.get_coordinates(shapely.line_interpolate_point(ring, rng.uniform(size=N_CAND), normalized=True))
        th = rng.uniform(0, 2 * np.pi, N_CAND); r = MAXD * np.sqrt(rng.uniform(size=N_CAND))
        x, y = P[:, 0] + r * np.cos(th), P[:, 1] + r * np.sin(th)
        own = locate(L, x, y)
        d = dist_to_own_boundary(L, x, y, own)
        ok = (own >= 0) & (d < MAXD)
        x, y, own, d = x[ok], y[ok], own[ok], d[ok]
        cls, n_reg, pieces, bend = classify(L, x, y, own, d, MAXD)
        df = pd.DataFrame({"layer": lname, "x": x, "y": y, "true_idx": own, "d_true": d, "class_R50": cls})
        df = df.sample(frac=1, random_state=1).groupby("class_R50").head(PER_CLASS)
        parts.append(df)
        print(lname, df["class_R50"].value_counts().to_dict())
    sp = pd.concat(parts, ignore_index=True)
    sp["point_id"] = np.arange(len(sp))
    sp.to_parquet(pts_path, index=False)
sp = pd.read_parquet(pts_path)
rep.table("[S0] Stress-set points per layer and geometry class (class at R = 50 m)",
          pd.crosstab(sp["layer"], sp["class_R50"]))

# ----------------------------------------------------------------------------- 2. simulate + evaluate
obs_path = f"{RAW}/obs.parquet"
if not os.path.exists(obs_path):
    out = []
    for model in C.MODELS:
        for R in [20, 50]:
            sig = R / C.GAUSS_K95
            for li, (lname, sub) in enumerate(sp.groupby("layer")):
                L = LAYERS[lname]
                rng = np.random.default_rng(7000 + 10 * R + 100 * C.MODELS.index(model) + li)
                cls_R, *_ = classify(L, sub["x"].to_numpy(), sub["y"].to_numpy(), sub["true_idx"].to_numpy(),
                                     np.minimum(sub["d_true"].to_numpy(), R - 1e-6), R)
                cls_R = np.where(sub["d_true"].to_numpy() < R, cls_R, "far (d >= R)")
                rp = sub.assign(class_R=cls_R).loc[sub.index.repeat(K)].reset_index(drop=True)
                x, y, t = rp["x"].to_numpy(), rp["y"].to_numpy(), rp["true_idx"].to_numpy()
                ox, oy = simulate_obs(x, y, model, R, rng)
                crisp = locate(L, ox, oy)
                dist = dist_to_own_boundary(L, ox, oy, crisp)
                ex_idx, ex_p = crisp.copy(), np.ones(len(rp))
                near = np.where((dist < R) | (crisp < 0))[0]
                a, b, _ = disk_overlay(L, ox[near], oy[near], float(R), t[near]); ex_idx[near], ex_p[near] = a, b
                g_idx, g_p = crisp.copy(), np.ones(len(rp))
                near_g = np.where((dist < gaussian_rmax(sig)) | (crisp < 0))[0]
                a, b, _ = gaussian_overlay(L, ox[near_g], oy[near_g], sig, t[near_g]); g_idx[near_g], g_p[near_g] = a, b
                out.append(pd.DataFrame({"point_id": rp["point_id"], "layer": lname, "model": model, "R": R,
                                         "class_R": rp["class_R"], "d_true": rp["d_true"], "true_idx": t,
                                         "crisp_idx": crisp, "dist_obs_m": dist, "ex_idx": ex_idx, "ex_p": ex_p,
                                         "g_idx": g_idx, "g_p": g_p}))
                print(f"{model} R={R} {lname} n={len(rp):,}")
    pd.concat(out, ignore_index=True).to_parquet(obs_path, index=False)
obs = pd.read_parquet(obs_path)
obs["wrong"] = obs["crisp_idx"] != obs["true_idx"]
obs["p_line"] = 0.0
for model in C.MODELS:
    m = obs["model"] == model
    obs.loc[m, "p_line"] = p_straight(obs.loc[m, "d_true"].to_numpy(), obs.loc[m, "R"].to_numpy(float), model)

rows = []
for (model, R, cls), d in obs.groupby(["model", "R", "class_R"]):
    if cls.startswith("far"):
        continue
    bt = point_bootstrap(d, lambda g: {"obs": 100 * g["wrong"].mean(), "ratio": g["wrong"].mean() / max(g["p_line"].mean(), 1e-12)}, B=300)
    o, ra = bt.set_index("metric").loc["obs"], bt.set_index("metric").loc["ratio"]
    rows.append({"model": model, "R": R, "geom_class": cls, "n_points": d["point_id"].nunique(), "n_obs": len(d),
                 "observed_%": o["value"], "obs_ci": f"[{o['ci_low']:.1f}, {o['ci_high']:.1f}]",
                 "straight_line_%": 100 * d["p_line"].mean(),
                 "obs/pred": ra["value"], "ratio_ci": f"[{ra['ci_low']:.2f}, {ra['ci_high']:.2f}]"})
s1 = pd.DataFrame(rows).round(3); s1.to_csv(f"{RES}/S1_class_vs_straight_line.csv", index=False)
rep.table("[S1] Wrong-region rate by local geometry vs straight-line prediction (95% CI: bootstrap over points)", s1, index=False)

rows = []
for (model, R, cls), d in obs.groupby(["model", "R", "class_R"]):
    if cls.startswith("far"):
        continue
    t = d["true_idx"].to_numpy()
    rows.append({"model": model, "R": R, "geom_class": cls,
                 "AURC_distance_%": rc_summary(d["dist_obs_m"].to_numpy(), d["crisp_idx"].to_numpy() != t)["AURC_%"],
                 "AURC_disk_overlay_%": rc_summary(d["ex_p"].to_numpy(), d["ex_idx"].to_numpy() != t)["AURC_%"],
                 "AURC_gauss_overlay_%": rc_summary(d["g_p"].to_numpy(), d["g_idx"].to_numpy() != t)["AURC_%"]})
s2 = pd.DataFrame(rows).round(3); s2.to_csv(f"{RES}/S2_strategies_by_class.csv", index=False)
rep.table("[S2] Ranking quality (AURC, lower = better) by geometry class: does probability beat distance where geometry is complex?",
          s2, index=False)
rep.save()
