"""EXP05 — Monte Carlo convergence: is MC-100's weakness just finite-sample noise?

On a fixed set of near-boundary EXP01 observations (uniform R=20 and Gaussian R=50, up to 400 per layer),
compare uniform-disk Monte Carlo with N = 25…5,000 samples against the deterministic disk overlay
(the quantity MC is estimating). 10 seeds for N ≤ 1,000, 3 seeds for N = 5,000.

    python experiments/exp05_mc_convergence.py
Outputs -> results/v2_mc_convergence/
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config as C
from src.geo import load_layers, load_points, locate, dist_to_own_boundary
from src.obs import regenerate
from src.report import Report
from src.uncertainty import monte_carlo, disk_overlay

RES = C.out_dir(C.RESULTS, "v2_mc_convergence")
FIG = C.out_dir(RES, "figures")
rep = Report("EXP05 Monte Carlo convergence vs deterministic disk overlay", RES)
pd.set_option("display.width", 250, "display.max_columns", 30)
LAYERS = load_layers()
pts = load_points(LAYERS)
NS = [25, 50, 100, 250, 500, 1000, 5000]

rows = []
for model, R in [("uniform", 20), ("gaussian", 50)]:
    for lname, (rp, ox, oy) in regenerate(pts, model, R).items():
        L = LAYERS[lname]
        tidx = rp["true_idx"].to_numpy()
        crisp = locate(L, ox, oy)
        d = dist_to_own_boundary(L, ox, oy, crisp)
        near = np.where((d < R) | (crisp < 0))[0]
        sel = np.random.default_rng(5).choice(near, size=min(400, len(near)), replace=False)
        x, y, t = ox[sel], oy[sel], tidx[sel]
        r_top, r_p, r_pt = disk_overlay(L, x, y, float(R), t)
        for N in NS:
            for s in range(10 if N <= 1000 else 3):
                rng = np.random.default_rng(10_000 + s)
                t0 = time.time()
                top, p, pt = monte_carlo(L, x, y, float(R), N, rng, t)
                dt = time.time() - t0
                rows.append({"model": model, "R": R, "layer": lname, "N": N, "seed": s, "n_obs": len(sel),
                             "rmse_p_true": float(np.sqrt(np.mean((pt - r_pt) ** 2))),
                             "rmse_p_top": float(np.sqrt(np.mean((p - r_p) ** 2))),
                             "decision_flip_vs_overlay_%": 100 * float(np.mean((p >= C.THETA) != (r_p >= C.THETA))),
                             "certain_but_wrong_%": 100 * float(np.mean((p >= 0.999) & (top != t))),
                             "overlay_certain_but_wrong_%": 100 * float(np.mean((r_p >= 0.999) & (r_top != t))),
                             "ms_per_1k": 1e6 * dt / len(sel)})
        print(f"{model} R={R} {lname} done ({len(sel)} obs)")
raw = pd.DataFrame(rows); raw.to_csv(f"{RES}/C0_raw_per_seed.csv", index=False)
agg = raw.groupby(["model", "R", "N"]).agg(
    rmse_p_true=("rmse_p_true", "mean"), rmse_sd=("rmse_p_true", "std"), rmse_p_top=("rmse_p_top", "mean"),
    decision_flip_pct=("decision_flip_vs_overlay_%", "mean"), certain_but_wrong_pct=("certain_but_wrong_%", "mean"),
    overlay_certain_but_wrong_pct=("overlay_certain_but_wrong_%", "mean"), ms_per_1k=("ms_per_1k", "mean")).round(4)
agg.to_csv(f"{RES}/C1_convergence.csv")
rep.table("[C1] MC vs disk overlay on near-boundary observations (mean over seeds and layers).\n"
          "     decision_flip = answer/abstain decision at theta=0.90 differs from overlay;\n"
          "     certain_but_wrong = MC gives p>=0.999 to a wrong region", agg)
rep.say("     expected MC RMSE ≈ sqrt(p(1-p)/N): halves when N quadruples")

fig, axes = plt.subplots(1, 2, figsize=(8, 3))
for (model, R), d in agg.reset_index().groupby(["model", "R"]):
    axes[0].loglog(d["N"], d["rmse_p_true"], "o-", label=f"{model} R={R}")
    axes[1].loglog(d["N"], d["ms_per_1k"], "o-", label=f"{model} R={R}")
n = np.array(NS, float)
axes[0].loglog(n, agg["rmse_p_true"].iloc[0] * np.sqrt(NS[0] / n), "k:", label="1/sqrt(N)")
axes[0].set_xlabel("MC samples N"); axes[0].set_ylabel("RMSE vs disk overlay"); axes[0].legend(fontsize=7)
axes[1].set_xlabel("MC samples N"); axes[1].set_ylabel("ms per 1,000 queries")
plt.tight_layout(); plt.savefig(f"{FIG}/figC1_convergence.png", dpi=300); plt.close()
rep.save()
