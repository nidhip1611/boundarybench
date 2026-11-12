"""EXP12 — Does a risk threshold chosen on some states hold on unseen states? (needs EXP01 + EXP03 outputs)

States are split into 5 folds. For each fold, thresholds are chosen on the other 4 folds to target a maximum error
rate (0.1%, 0.5%, 1%) and then applied unchanged to the held-out states. Two selection rules:
  empirical   largest coverage whose calibration error rate <= target
  certified   largest coverage whose 95% Wilson UPPER bound on the calibration error rate <= target
Methods: distance rule (score = distance to boundary), Monte Carlo, disk overlay, Gaussian overlay.

    python experiments/exp12_heldout_geography.py
Outputs -> results/v2_heldout_geography/
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

RES = C.out_dir(C.RESULTS, "v2_heldout_geography")
rep = Report("EXP12 held-out-geography risk control", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 300)

obs = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(f"{C.RAW}/v2/obs_*.parquet"))], ignore_index=True)
obs = obs.merge(pd.read_parquet(f"{C.RAW}/v2/gaussian_overlay.parquet"), on=["model", "R", "layer", "point_id", "k"],
                how="left", validate="one_to_one")
pts = pd.read_parquet(C.DATA).reset_index(drop=True)
pts["point_id"] = np.arange(len(pts))
if "statefp" not in pts.columns:
    raise KeyError(f"dataset has no statefp column; columns: {list(pts.columns)}")
obs = obs.merge(pts[["point_id", "statefp"]], on="point_id", how="left")
assert obs["statefp"].notna().all() and obs["g_p"].notna().all()

states = np.array(sorted(obs["statefp"].astype(str).unique()))
perm = np.random.default_rng(1212).permutation(states)
folds = {s: i for i, part in enumerate(np.array_split(perm, 5)) for s in part}
obs["fold"] = obs["statefp"].astype(str).map(folds)
rep.say(f"{len(states)} states/territories in 5 folds; points per fold: "
        f"{obs.drop_duplicates('point_id').groupby('fold').size().to_dict()}")

METHODS = {"Distance rule": ("dist_obs_m", "crisp_idx"), "Monte Carlo": ("mc_p", "mc_idx"),
           "Disk overlay": ("ex_p", "ex_idx"), "Gaussian overlay": ("g_p", "g_idx")}
TARGETS = [0.001, 0.005, 0.01]


def wilson_upper(k, n, z=1.96):
    p = k / n
    return (p + z * z / (2 * n) + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def choose(score, wrong, target, certified):
    thr, cov, risk = rc_curve(score, wrong)
    n = cov * len(score)
    r = wilson_upper(risk * n, n) if certified else risk
    ok = np.where(r <= target)[0]
    return thr[ok.max()] if len(ok) else np.inf


rows = []
for (model, R), d in obs.groupby(["model", "R"]):
    t = d["true_idx"].to_numpy()
    for name, (sc, pr) in METHODS.items():
        s = d[sc].to_numpy(); w = d[pr].to_numpy() != t
        for target in TARGETS:
            for rule in ["empirical", "certified"]:
                ans_n = wrong_n = 0; fold_risk = []
                for f in range(5):
                    cal, te = (d["fold"] != f).to_numpy(), (d["fold"] == f).to_numpy()
                    thr = choose(s[cal], w[cal], target, rule == "certified")
                    a = te & (s >= thr)
                    ans_n += a.sum(); wrong_n += w[a].sum()
                    fold_risk.append(w[a].mean() if a.any() else 0.0)
                rows.append({"model": model, "R": R, "method": name, "target_%": 100 * target, "rule": rule,
                             "heldout_coverage_%": 100 * ans_n / len(d),
                             "heldout_risk_%": 100 * wrong_n / max(ans_n, 1),
                             "worst_fold_risk_%": 100 * max(fold_risk),
                             "folds_over_target": int(sum(r > target for r in fold_risk))})
    print(f"{model} R={R} done")
t = pd.DataFrame(rows).round(4); t.to_csv(f"{RES}/H1_heldout_risk_control.csv", index=False)
rep.table("[H1] Thresholds chosen on 4 folds of states, applied to the held-out fold (pooled over the 5 folds).\n"
          "     A method 'holds' if heldout_risk <= target; folds_over_target counts folds (of 5) that exceed it.", t, index=False)
summ = (t.assign(holds=t["heldout_risk_%"] <= t["target_%"])
        .groupby(["method", "rule"]).agg(settings=("holds", "size"), pooled_risk_holds=("holds", "sum"),
                                          total_folds_over_target=("folds_over_target", "sum"),
                                          mean_coverage_pct=("heldout_coverage_%", "mean")).round(2))
summ.to_csv(f"{RES}/H2_summary.csv")
rep.table("[H2] Summary over all 8 error settings × 3 targets", summ)
rep.save()
