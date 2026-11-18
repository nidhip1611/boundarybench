"""EXP20 — Held-out-state thresholds reported fold by fold, zero-coverage runs separated, and a cluster-aware
upper confidence bound (same folds, data and thresholds rule as EXP12; needs EXP01 + EXP03 outputs).

UCB (observation)  : Wilson upper bound with n = answered calibration OBSERVATIONS (as in EXP12).
UCB (location)     : Wilson upper bound with n = answered observations / K and k = errors / K, i.e. one effective
                     observation per benchmark location (K = 5 correlated observations per location). More conservative.

    python experiments/exp20_heldout_folds.py
Outputs -> results/v2_heldout_folds/
"""
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd

from src import config as C
from src.metrics import rc_curve
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_heldout_folds")
rep = Report("EXP20 held-out thresholds by fold, zero coverage separated, cluster-aware UCB", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 2000)

obs = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(f"{C.RAW}/v2/obs_*.parquet"))], ignore_index=True)
obs = obs.merge(pd.read_parquet(f"{C.RAW}/v2/gaussian_overlay.parquet"), on=["model", "R", "layer", "point_id", "k"],
                how="left", validate="one_to_one")
pts = pd.read_parquet(C.DATA).reset_index(drop=True)
pts["point_id"] = np.arange(len(pts))
obs = obs.merge(pts[["point_id", "statefp"]], on="point_id", how="left")
states = np.array(sorted(obs["statefp"].astype(str).unique()))
perm = np.random.default_rng(1212).permutation(states)                 # identical folds to EXP12
folds = {s: i for i, part in enumerate(np.array_split(perm, 5)) for s in part}
obs["fold"] = obs["statefp"].astype(str).map(folds)

METHODS = {"Distance rule": ("dist_obs_m", "crisp_idx"), "Monte Carlo": ("mc_p", "mc_idx"),
           "Disk overlay": ("ex_p", "ex_idx"), "Gaussian overlay": ("g_p", "g_idx")}
TARGETS = [0.001, 0.005, 0.01]
K_OBS = C.K_OBS


def wilson_upper(k, n, z=1.96):
    n = np.maximum(n, 1e-12); p = k / n
    return (p + z * z / (2 * n) + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def choose(score, wrong, target, rule):
    thr, cov, risk = rc_curve(score, wrong)
    n = cov * len(score)
    if rule == "empirical":
        r = risk
    elif rule == "UCB (observation)":
        r = wilson_upper(risk * n, n)
    else:                                                               # UCB (location)
        r = wilson_upper(risk * n / K_OBS, n / K_OBS)
    ok = np.where(r <= target)[0]
    return thr[ok.max()] if len(ok) else np.inf


rows = []
for (model, R), d in obs.groupby(["model", "R"]):
    t = d["true_idx"].to_numpy(); fold = d["fold"].to_numpy()
    for name, (sc, pr) in METHODS.items():
        s = d[sc].to_numpy(); w = d[pr].to_numpy() != t
        for target in TARGETS:
            for rule in ["empirical", "UCB (observation)", "UCB (location)"]:
                for f in range(5):
                    cal, te = fold != f, fold == f
                    thr = choose(s[cal], w[cal], target, rule)
                    a = te & (s >= thr)
                    rows.append({"model": model, "R": R, "method": name, "target_%": 100 * target, "rule": rule,
                                 "fold": f, "n_test": int(te.sum()), "answered": int(a.sum()), "errors": int(w[a].sum()),
                                 "coverage_%": 100 * a.sum() / te.sum(),
                                 "risk_%": (100 * w[a].mean()) if a.any() else np.nan})
    print(f"EXP20 {model} R={R} done")
F = pd.DataFrame(rows).round(4)
F.to_csv(f"{RES}/F1_folds.csv", index=False)

F["over"] = (F["risk_%"] > F["target_%"]).astype(int)
P = (F.groupby(["model", "R", "method", "target_%", "rule"])
     .agg(answered=("answered", "sum"), errors=("errors", "sum"), n=("n_test", "sum"),
          zero_cov_folds=("answered", lambda x: int((x == 0).sum())), folds_over=("over", "sum"))
     .reset_index())
P["coverage_%"] = 100 * P["answered"] / P["n"]
P["pooled_risk_%"] = np.where(P["answered"] > 0, 100 * P["errors"] / P["answered"].clip(lower=1), np.nan)
P["status"] = np.where(P["answered"] == 0, "no answers (risk undefined)",
                       np.where(P["pooled_risk_%"] <= P["target_%"], "met", "missed"))
P.round(4).to_csv(f"{RES}/F2_pooled.csv", index=False)
rep.table("[F2] Pooled over the 5 held-out folds, per setting (status: met / missed / no answers)", P.round(4), index=False)

S = (P.groupby(["method", "rule"])
     .apply(lambda g: pd.Series({
         "settings": len(g), "no_answers": int((g["status"] == "no answers (risk undefined)").sum()),
         "met_of_answered": f"{int((g['status'] == 'met').sum())}/{int((g['status'] != 'no answers (risk undefined)').sum())}",
         "fold_cases": 5 * len(g),
         "zero_coverage_fold_cases": int(g["zero_cov_folds"].sum()),
         "folds_over_target": int(g["folds_over"].sum()),
         "mean_coverage_%": round(g["coverage_%"].mean(), 2)}))
     .reset_index())
S.to_csv(f"{RES}/F3_summary.csv", index=False)
rep.table("[F3] Summary over 8 error settings x 3 targets. 'met_of_answered' excludes settings with no answers;\n"
          "     folds_over_target counts fold-setting cases (of fold_cases) whose held-out risk exceeds the target", S, index=False)
show = F[(F["R"] == 50) & (F["target_%"] == 0.1)].round(3)
rep.table("[F1 excerpt] Fold-level results at R = 50 m, target 0.1% (full table: F1_folds.csv)", show, index=False)
rep.save()
