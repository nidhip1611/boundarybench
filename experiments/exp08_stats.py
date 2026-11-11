"""EXP08 — Statistics for the paper (needs EXP01 and EXP03 outputs).

1. Data-flow table: 13,000 benchmark points -> observations -> near-boundary subsets.
2. Headline metrics with 95% CIs from a bootstrap over benchmark points (B = 300).
3. Calibration with equal-mass bins + Wilson CIs, ECE with bootstrap CI, reliability diagrams,
   for the correctly specified overlay (disk for uniform data, Gaussian for Gaussian data) and the other one.

    python experiments/exp08_stats.py
Outputs -> results/v2_stats/
"""
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config as C
from src.metrics import rc_summary, op_point, wilson
from src.report import Report
from src.stats import point_bootstrap

RES = C.out_dir(C.RESULTS, "v2_stats")
FIG = C.out_dir(RES, "figures")
rep = Report("EXP08 statistics: data flow, bootstrap CIs, calibration", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 300)

obs = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(f"{C.RAW}/v2/obs_*.parquet"))], ignore_index=True)
g = pd.read_parquet(f"{C.RAW}/v2/gaussian_overlay.parquet")
obs = obs.merge(g, on=["model", "R", "layer", "point_id", "k"], how="left", validate="one_to_one")
assert obs["g_p"].notna().all(), "Run experiments/exp03_gaussian_overlay.py first"
obs["crisp_wrong"] = obs["crisp_idx"] != obs["true_idx"]

# ----------------------------------------------------------------------------- 1. data flow
base = obs.drop_duplicates("point_id")
flow = pd.crosstab(base["layer"], base["difficulty"], margins=True, margins_name="total")
rep.table("[D1] Benchmark points by layer and difficulty tier", flow)
nf = obs.groupby(["model", "R"]).agg(observations=("point_id", "size"), points=("point_id", "nunique"),
                                     near_boundary_obs=("near", "sum")).reset_index()
nf["obs_per_point"] = nf["observations"] / nf["points"]
rep.table(f"[D2] Observations per setting (total {len(obs):,} = {base['point_id'].nunique():,} points × K × "
          f"{nf.shape[0]} settings); near = reported point closer than R to its boundary", nf, index=False)

# ----------------------------------------------------------------------------- 2. headline metrics with CIs
def headline(d):
    R = d["R"].iloc[0]; t = d["true_idx"].to_numpy()
    out = {"crisp_err_%": 100 * d["crisp_wrong"].mean()}
    for lo, hi in [(0, 10), (10, 25), (25, 50)]:
        m = (d["dist_true_m"] >= lo) & (d["dist_true_m"] < hi)
        out[f"crisp_err_{lo}-{hi}m_%"] = 100 * d.loc[m, "crisp_wrong"].mean() if m.any() else np.nan
    dr = op_point(d["dist_obs_m"], d["crisp_idx"], t, R)
    dk = op_point(d["ex_p"], d["ex_idx"], t, C.THETA)
    out.update({"dist_cov_%": dr["op_coverage_%"], "dist_risk_%": dr["op_risk_%"],
                "disk_cov_%": dk["op_coverage_%"], "disk_risk_%": dk["op_risk_%"]})
    for name, sc, pr in [("dist", "dist_obs_m", "crisp_idx"), ("mc", "mc_p", "mc_idx"),
                         ("disk", "ex_p", "ex_idx"), ("gauss", "g_p", "g_idx")]:
        out[f"AURC_{name}_%"] = rc_summary(d[sc].to_numpy(), d[pr].to_numpy() != t)["AURC_%"]
    return out


rows = []
for (model, R), d in obs.groupby(["model", "R"]):
    bt = point_bootstrap(d, headline, B=300, seed=int(R))
    bt.insert(0, "R", R); bt.insert(0, "model", model)
    rows.append(bt)
    print(f"bootstrap {model} R={R} done")
hl = pd.concat(rows, ignore_index=True).round(4); hl.to_csv(f"{RES}/B1_headline_with_CI.csv", index=False)
rep.table("[B1] Headline metrics with 95% CIs (bootstrap over benchmark points, B = 300)", hl, index=False)

# ----------------------------------------------------------------------------- 3. calibration
def eq_mass(p, c, bins=10):
    q = pd.qcut(p, bins, duplicates="drop")
    tab = pd.DataFrame({"q": q, "p": p, "c": c}).groupby("q", observed=True).agg(n=("c", "size"), mean_p=("p", "mean"),
                                                                                   acc=("c", "mean"), k=("c", "sum"))
    ci = [wilson(int(k), int(n)) for k, n in zip(tab["k"], tab["n"])]
    tab["acc_lo"], tab["acc_hi"] = [a for a, _ in ci], [b for _, b in ci]
    ece = float((tab["n"] / tab["n"].sum() * (tab["mean_p"] - tab["acc"]).abs()).sum())
    return tab.reset_index(drop=True), 100 * ece


cal_rows, rel = [], {}
for (model, R), d in obs.groupby(["model", "R"]):
    nr = d[d["near"]]
    for name, sc, pr in [("Disk overlay", "ex_p", "ex_idx"), ("Gaussian overlay", "g_p", "g_idx")]:
        tab, e = eq_mass(nr[sc].to_numpy(), (nr[pr] == nr["true_idx"]).to_numpy())
        bt = point_bootstrap(nr, lambda x: {"ece": eq_mass(x[sc].to_numpy(), (x[pr] == x["true_idx"]).to_numpy())[1]}, B=200)
        spec = (model == "uniform") == (name == "Disk overlay")
        cal_rows.append({"model": model, "R": R, "method": name, "correctly_specified": spec, "n_near": len(nr),
                         "ECE_eqmass_%": e, "ci_low": bt["ci_low"].iloc[0], "ci_high": bt["ci_high"].iloc[0],
                         "Brier_true": float(((1 - nr[sc + "_true"]) ** 2).mean())})
        rel[(model, R, name)] = tab
cal = pd.DataFrame(cal_rows).round(3); cal.to_csv(f"{RES}/K1_calibration.csv", index=False)
rep.table("[K1] Calibration on near-boundary observations (equal-mass bins, 95% bootstrap CI)", cal, index=False)

fig, axes = plt.subplots(2, 4, figsize=(12, 6), sharex=True, sharey=True)
for i, model in enumerate(C.MODELS):
    for j, R in enumerate(C.RADII):
        ax = axes[i, j]
        for name, col in [("Disk overlay", "C0"), ("Gaussian overlay", "C1")]:
            tab = rel[(model, R, name)]
            ax.errorbar(tab["mean_p"], tab["acc"], yerr=[tab["acc"] - tab["acc_lo"], tab["acc_hi"] - tab["acc"]],
                        fmt="o-", ms=3, color=col, label=name)
        ax.plot([0, 1], [0, 1], "k:", lw=1); ax.set_title(f"{model}, R = {R} m", fontsize=9)
axes[0, 0].legend(fontsize=7)
for ax in axes[1]:
    ax.set_xlabel("predicted top-region probability")
for ax in axes[:, 0]:
    ax.set_ylabel("observed accuracy")
plt.tight_layout(); plt.savefig(f"{FIG}/figK1_reliability.png", dpi=300); plt.close()
rep.save()
