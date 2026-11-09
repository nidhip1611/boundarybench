"""EXP01 — V2 main experiment (RQ1–RQ3).

Each benchmark point is the TRUE location. K noisy reported locations are simulated per point
(uniform disk / Gaussian, R in {5,10,20,50} m). Every method sees only the reported point and is
scored against the true region.

    python experiments/exp01_v2_main.py            # full run (13,000 points × 5 obs × 8 settings)
    python experiments/exp01_v2_main.py --quick    # 500-point smoke test

Raw per-observation files -> $BB_WORK/outputs/v2/   Tables, figures, summary.txt -> results/v2/
"""
import argparse
import glob
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely

from src import config as C
from src.geo import load_layers, load_points, locate, dist_to_own_boundary
from src.metrics import rc_curve, rc_summary, op_point, ece
from src.report import Report
from src.uncertainty import simulate_obs, monte_carlo, disk_overlay

ap = argparse.ArgumentParser()
ap.add_argument("--quick", action="store_true")
args = ap.parse_args()
TAG = "v2_quick" if args.quick else "v2"
RAW = C.out_dir(C.RAW, TAG)
RES = C.out_dir(C.RESULTS, TAG)
FIG = C.out_dir(RES, "figures")
K_OBS = 2 if args.quick else C.K_OBS
rep_ = Report("EXP01 V2 main experiment" + (" (QUICK)" if args.quick else ""), RES)

# ----------------------------------------------------------------------------- data
LAYERS = load_layers()
pts = load_points(LAYERS)
if args.quick:
    take = []
    for _, d in pts.groupby(["layer", "difficulty"]):
        take.append(d.sample(min(len(d), max(1, int(500 * len(d) / len(pts)))), random_state=0))
    pts = pd.concat(take).sort_index().reset_index(drop=True)
rep_.say(f"points: {len(pts):,} | K = {K_OBS} | settings = {len(C.MODELS) * len(C.RADII)}")

# ----------------------------------------------------------------------------- sanity check
rng = np.random.default_rng(7)
L = LAYERS["tract"]; sub = pts[pts["layer"] == "tract"]; R = 20.0
ox, oy = simulate_obs(sub["x"].to_numpy(), sub["y"].to_numpy(), "uniform", R, rng)
idx = locate(L, ox, oy); d = dist_to_own_boundary(L, ox, oy, idx)
near = np.where((d < R) | (idx < 0))[0][:300]
tidx = sub["true_idx"].to_numpy()[near]
_, _, ex_true = disk_overlay(L, ox[near], oy[near], R, tidx)
_, _, mc_true = monte_carlo(L, ox[near], oy[near], R, 5000, rng, tidx)
mae = float(np.abs(ex_true - mc_true).mean())
rep_.say(f"SANITY: disk overlay vs 5,000-sample MC on {len(near)} obs, MAE = {mae:.4f} -> {'PASS' if mae < 0.02 else 'CHECK'}")

# ----------------------------------------------------------------------------- main loop (checkpointed)
timing = []
for model in C.MODELS:
    for R in C.RADII:
        path = f"{RAW}/obs_{model}_R{R}.parquet"
        if os.path.exists(path):
            print(f"skip {model} R={R} (exists)")
            continue
        parts = []
        for li, (lname, sub) in enumerate(pts.groupby("layer")):
            L = LAYERS[lname]
            rng = np.random.default_rng(1000 * R + 100 * C.MODELS.index(model) + li)
            rep = sub.loc[sub.index.repeat(K_OBS)].reset_index(drop=True)
            rep["k"] = np.tile(np.arange(K_OBS), len(sub))
            x, y, tidx = rep["x"].to_numpy(), rep["y"].to_numpy(), rep["true_idx"].to_numpy()
            ox, oy = simulate_obs(x, y, model, R, rng)
            n = len(rep)
            t = time.time(); crisp = locate(L, ox, oy); t_crisp = time.time() - t
            t = time.time(); dist = dist_to_own_boundary(L, ox, oy, crisp); t_dist = time.time() - t
            near = np.where((dist < R) | (crisp < 0))[0]
            mc_top, mc_p, mc_pt = crisp.copy(), np.ones(n), (crisp == tidx).astype(float)
            ex_top, ex_p, ex_pt = crisp.copy(), np.ones(n), (crisp == tidx).astype(float)
            t = time.time(); a, b, c = monte_carlo(L, ox[near], oy[near], R, C.N_MC, rng, tidx[near]); t_mc = time.time() - t
            mc_top[near], mc_p[near], mc_pt[near] = a, b, c
            t = time.time(); a, b, c = disk_overlay(L, ox[near], oy[near], R, tidx[near]); t_ex = time.time() - t
            ex_top[near], ex_p[near], ex_pt[near] = a, b, c
            parts.append(pd.DataFrame({
                "point_id": rep["point_id"], "k": rep["k"], "layer": lname, "difficulty": rep["difficulty"],
                "split": rep["split"], "dist_true_m": rep["dist_to_boundary_m"], "model": model, "R": R,
                "err_m": np.hypot(ox - x, oy - y), "true_idx": tidx, "crisp_idx": crisp, "dist_obs_m": dist,
                "near": np.isin(np.arange(n), near), "mc_idx": mc_top, "mc_p": mc_p, "mc_p_true": mc_pt,
                "ex_idx": ex_top, "ex_p": ex_p, "ex_p_true": ex_pt}))
            timing.append({"model": model, "R": R, "layer": lname, "n_obs": n, "n_near": len(near),
                           "t_crisp_s": t_crisp, "t_dist_s": t_dist, "t_mc_s": t_mc, "t_exact_s": t_ex})
            print(f"{model:8s} R={R:>2} {lname:6s} n={n:,} near={len(near):,} mc={t_mc:.1f}s overlay={t_ex:.1f}s")
        pd.concat(parts, ignore_index=True).to_parquet(path, index=False)
        tp = f"{RAW}/timing.csv"
        pd.DataFrame(timing).to_csv(tp, mode="a", header=not os.path.exists(tp), index=False)
        timing = []

# ----------------------------------------------------------------------------- analysis
obs = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(f"{RAW}/obs_*.parquet"))], ignore_index=True)
BINS = [-0.01, 10, 25, 50, 100, 500, np.inf]
BLAB = ["0-10m", "10-25m", "25-50m", "50-100m", "100-500m", ">500m"]
obs["dist_bin"] = pd.cut(obs["dist_true_m"], BINS, labels=BLAB)
obs["crisp_wrong"] = obs["crisp_idx"] != obs["true_idx"]
METHODS = {"Crisp PIP": (None, "crisp_idx"), "Distance rule": ("dist_obs_m", "crisp_idx"),
           "Monte Carlo": ("mc_p", "mc_idx"), "Disk overlay": ("ex_p", "ex_idx")}


def score(d, col):
    return np.ones(len(d)) if col is None else d[col].to_numpy()


t1 = (obs.groupby(["model", "R", "layer", "dist_bin"], observed=True)["crisp_wrong"].mean().mul(100).round(2)
      .unstack("dist_bin").reindex(columns=BLAB))
t1b = obs.groupby(["model", "R", "layer", "difficulty"])["crisp_wrong"].mean().mul(100).round(2).unstack("difficulty")
t1.to_csv(f"{RES}/T1_crisp_error_by_distance.csv"); t1b.to_csv(f"{RES}/T1b_crisp_error_by_difficulty.csv")

rows = []
for (model, R, layer), d in obs.groupby(["model", "R", "layer"]):
    nr = d[d["near"]]
    rows.append({"model": model, "R": R, "layer": layer, "crisp_error_%": 100 * d["crisp_wrong"].mean(),
                 "share_near_boundary_%": 100 * d["near"].mean(),
                 "disk_ECE_near_%": ece(nr["ex_p"], nr["ex_idx"] == nr["true_idx"]) if len(nr) else np.nan,
                 "disk_Brier_true_near": float(((1 - nr["ex_p_true"]) ** 2).mean()) if len(nr) else np.nan,
                 "obs_err_beyond_R_%": 100 * (d["err_m"] > R).mean()})
t2 = pd.DataFrame(rows).round(3); t2.to_csv(f"{RES}/T2_error_model_sensitivity.csv", index=False)


def compare(groups):
    rows = []
    for key, d in groups:
        key = key if isinstance(key, tuple) else (key,)
        for name, (sc, pr) in METHODS.items():
            s, p = score(d, sc), d[pr].to_numpy()
            row = dict(zip(["model", "R", "layer"][:len(key)], key), method=name,
                       **rc_summary(s, p != d["true_idx"].to_numpy()))
            if name != "Crisp PIP":
                row.update(op_point(s, p, d["true_idx"], key[1] if name == "Distance rule" else C.THETA))
            rows.append(row)
    return pd.DataFrame(rows).round(3)


t3p = compare(obs.groupby(["model", "R"])); t3p.to_csv(f"{RES}/T3_pooled.csv", index=False)
t3 = compare(obs.groupby(["model", "R", "layer"])); t3.to_csv(f"{RES}/T3_strategy_comparison.csv", index=False)
tim = pd.read_csv(f"{RAW}/timing.csv").drop_duplicates(["model", "R", "layer"], keep="last")
tt = tim.groupby("R")[["n_obs", "t_crisp_s", "t_dist_s", "t_mc_s", "t_exact_s"]].sum()
for c in ["t_crisp_s", "t_dist_s", "t_mc_s", "t_exact_s"]:
    tt[c.replace("_s", "_ms_per_1k")] = 1e6 * tt[c] / tt["n_obs"]
tt = tt.rename(columns={"t_exact_s": "t_overlay_s", "t_exact_ms_per_1k": "t_overlay_ms_per_1k"}).round(2)
tt.to_csv(f"{RES}/T4_runtime.csv")

# ----------------------------------------------------------------------------- figures
plt.rcParams.update({"font.size": 9})
fig, axes = plt.subplots(1, 2, figsize=(8, 3), sharey=True)
for ax, model in zip(axes, C.MODELS):
    for layer in ["county", "zcta", "tract"]:
        s = t1.loc[(model, 20, layer)]
        ax.plot(range(len(s)), s.to_numpy(), marker="o", label=layer)
    ax.set_xticks(range(len(BLAB))); ax.set_xticklabels(BLAB, rotation=30)
    ax.set_title(f"{model} error, R = 20 m"); ax.set_xlabel("true distance to boundary")
axes[0].set_ylabel("crisp PIP wrong region (%)"); axes[0].legend()
plt.tight_layout(); plt.savefig(f"{FIG}/fig1_error_vs_distance.png", dpi=300); plt.close()

fig, axes = plt.subplots(1, 2, figsize=(8, 3), sharey=True)
for ax, model in zip(axes, C.MODELS):
    d = obs[(obs["model"] == model) & (obs["R"] == 20)]
    for name, (sc, pr) in METHODS.items():
        if sc is None:
            continue
        _, cov, risk = rc_curve(score(d, sc), d[pr].to_numpy() != d["true_idx"].to_numpy())
        ax.plot(100 * cov, 100 * risk, label=name)
    ax.scatter([100], [100 * d["crisp_wrong"].mean()], color="k", zorder=5, label="Crisp PIP")
    ax.set_xlim(70, 100.5); ax.set_title(f"{model} error, R = 20 m"); ax.set_xlabel("coverage (%)")
axes[0].set_ylabel("risk = wrong / answered (%)"); axes[0].legend(fontsize=7)
plt.tight_layout(); plt.savefig(f"{FIG}/fig2_risk_coverage.png", dpi=300); plt.close()

fig, ax = plt.subplots(figsize=(4.5, 3))
for (model, layer), d in t2.groupby(["model", "layer"]):
    ax.plot(d["R"], d["crisp_error_%"], marker="o", ls="-" if model == "uniform" else "--", label=f"{layer} ({model})")
ax.set_xlabel("R (m)"); ax.set_ylabel("crisp PIP wrong region (%)"); ax.legend(fontsize=6)
plt.tight_layout(); plt.savefig(f"{FIG}/fig3_error_vs_radius.png", dpi=300); plt.close()

fig, ax = plt.subplots(figsize=(3.5, 3.2))
for model in C.MODELS:
    d = obs[(obs["model"] == model) & (obs["R"] == 20) & obs["near"]]
    b = pd.cut(d["ex_p"], np.linspace(0, 1, 11), include_lowest=True)
    g = d.assign(c=(d["ex_idx"] == d["true_idx"])).groupby(b, observed=True).agg(p=("ex_p", "mean"), acc=("c", "mean"))
    ax.plot(g["p"], g["acc"], marker="o", label=model)
ax.plot([0, 1], [0, 1], "k:", lw=1); ax.set_xlabel("disk-overlay top-region probability"); ax.set_ylabel("observed accuracy")
ax.legend(); plt.tight_layout(); plt.savefig(f"{FIG}/fig4_calibration.png", dpi=300); plt.close()

# ----------------------------------------------------------------------------- summary
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 400)
rep_.say(f"observations: {len(obs):,}")
rep_.table("[T1] Crisp PIP wrong-region rate (%) by true distance band", t1)
rep_.table("[T1b] Crisp PIP wrong-region rate (%) by difficulty tier", t1b)
rep_.table("[T2] Error-model sensitivity & disk-overlay calibration", t2, index=False)
rep_.table("[T3] Strategy comparison, pooled over layers (Distance rule tau = R; MC / overlay theta = 0.90)", t3p, index=False)
rep_.table("[T3-by-layer]", t3, index=False)
rep_.table("[T4] Runtime (ms per 1,000 queries; distance pre-filter applied to MC and overlay)", tt)
rep_.save()
