"""EXP17 — Matched operating points for all abstention strategies (needs EXP01 + EXP03 outputs; no new simulation).

Reviewer request: compare strategies at the SAME risk targets, with uncertainty, separately per error model.
For every (error model, R) and every strategy we report the largest coverage whose observed risk is <= 1%, 0.5%, 0.1%
on the benchmark, with 95% CIs from a bootstrap over benchmark points (the K = 5 observations of a point stay together).

    python experiments/exp17_matched_operating_points.py
Outputs -> results/v2_matched/
"""
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd

from src import config as C
from src.metrics import rc_summary
from src.report import Report
from src.stats import point_bootstrap

RES = C.out_dir(C.RESULTS, "v2_matched")
rep = Report("EXP17 matched operating points (coverage at fixed risk targets, bootstrap CIs)", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 300)
B = int(os.environ.get("BB_BOOT", 200))

obs = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(f"{C.RAW}/v2/obs_*.parquet"))], ignore_index=True)
g = pd.read_parquet(f"{C.RAW}/v2/gaussian_overlay.parquet")
obs = obs.merge(g, on=["model", "R", "layer", "point_id", "k"], how="left", validate="one_to_one")
assert obs["g_p"].notna().all(), "Run experiments/exp03_gaussian_overlay.py first"

METHODS = [("Distance rule", "dist_obs_m", "crisp_idx"), ("Monte Carlo (N=100)", "mc_p", "mc_idx"),
           ("Disk overlay", "ex_p", "ex_idx"), ("Gaussian overlay", "g_p", "g_idx")]


def stat(d):
    t = d["true_idx"].to_numpy(); out = {}
    for name, sc, pr in METHODS:
        s = rc_summary(d[sc].to_numpy(), d[pr].to_numpy() != t)
        for k in ["cov@risk<=1%", "cov@risk<=0.5%", "cov@risk<=0.1%", "AURC_%"]:
            out[f"{name}|{k}"] = s[k]
    return out


rows = []
for (model, R), d in obs.groupby(["model", "R"]):
    bt = point_bootstrap(d, stat, B=B, seed=1700 + int(R))
    bt[["method", "metric"]] = bt["metric"].str.split("|", expand=True)
    bt.insert(0, "R", R); bt.insert(0, "model", model)
    rows.append(bt)
    print(f"EXP17 {model} R={R} done")
T = pd.concat(rows, ignore_index=True)
T = T[["model", "R", "method", "metric", "value", "ci_low", "ci_high"]].round(3)
T.to_csv(f"{RES}/M1_matched_operating_points.csv", index=False)
T["cell"] = T.apply(lambda r: f"{r['value']:.1f} [{r['ci_low']:.1f}, {r['ci_high']:.1f}]" if r["metric"] != "AURC_%"
                    else f"{r['value']:.3f} [{r['ci_low']:.3f}, {r['ci_high']:.3f}]", axis=1)
wide = T.pivot_table(index=["model", "R", "method"], columns="metric", values="cell", aggfunc="first")
wide = wide[["cov@risk<=1%", "cov@risk<=0.5%", "cov@risk<=0.1%", "AURC_%"]]
rep.table(f"[M1] Coverage (%) at fixed risk targets and AURC (%), 95% CI from a bootstrap over benchmark points (B = {B}).\n"
          "     Coverage 0 means the target is not reached at any coverage.", wide)
rep.save()
