"""EXP24 — Simulation checks requested in round-6 reviews (needs EXP01 + EXP03 outputs).

  T1  Strategy comparison with threshold selection separated from evaluation: thresholds chosen on a random half of
      benchmark LOCATIONS (all K observations), coverage and risk measured on the other half; 8 settings x 3 targets.
  H1  Held-out states (same folds as EXP12/EXP20) with a location-clustered calibration rule: Wilson upper bound computed
      on ONE randomly chosen observation per calibration location (independent outcomes for a fixed threshold);
      reported next to the earlier observation-level and location-adjusted rules.
  P1  EPSG:2163 linear-scale error and angular distortion at all 13,000 benchmark locations (by state group).

    python experiments/exp24_sim_clustered.py
Outputs -> results/v2_sim_clustered/
"""
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd
from pyproj import Proj, Transformer

from src import config as C
from src.metrics import rc_curve
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_sim_clustered")
rep = Report("EXP24 simulation: split-sample strategy comparison, one-observation-per-location UCB, projection", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 400)

obs = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(f"{C.RAW}/v2/obs_*.parquet"))], ignore_index=True)
obs = obs.merge(pd.read_parquet(f"{C.RAW}/v2/gaussian_overlay.parquet"), on=["model", "R", "layer", "point_id", "k"],
                how="left", validate="one_to_one")
pts = pd.read_parquet(C.DATA).reset_index(drop=True)
pts["point_id"] = np.arange(len(pts))
obs = obs.merge(pts[["point_id", "statefp"]], on="point_id", how="left")
states = np.array(sorted(obs["statefp"].astype(str).unique()))
perm = np.random.default_rng(1212).permutation(states)
folds = {s: i for i, part in enumerate(np.array_split(perm, 5)) for s in part}
obs["fold"] = obs["statefp"].astype(str).map(folds)
half = np.random.default_rng(2424).random(len(pts)) < 0.5                  # location split for T1
obs["half"] = half[obs["point_id"].to_numpy()]
pick = np.random.default_rng(2425).integers(0, C.K_OBS, len(pts))           # one observation per location for H1
obs["picked"] = obs["k"].to_numpy() == pick[obs["point_id"].to_numpy()]

METHODS = {"Distance rule": ("dist_obs_m", "crisp_idx"), "Monte Carlo": ("mc_p", "mc_idx"),
           "Disk overlay": ("ex_p", "ex_idx"), "Gaussian overlay": ("g_p", "g_idx")}
TARGETS = [0.001, 0.005, 0.01]


def wilson_upper(k, n, z=1.96):
    n = np.maximum(n, 1e-12); p = k / n
    return (p + z * z / (2 * n) + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def choose(score, wrong, target, ucb):
    thr, cov, risk = rc_curve(score, wrong)
    n = cov * len(score)
    r = wilson_upper(risk * n, n) if ucb else risk
    ok = np.where(r <= target)[0]
    return thr[ok.max()] if len(ok) else np.inf


# ----------------------------------------------------------------------------- T1 split-sample comparison
rows = []
for (model, R), d in obs.groupby(["model", "R"]):
    t = d["true_idx"].to_numpy(); h = d["half"].to_numpy()
    for name, (sc, pr) in METHODS.items():
        s = d[sc].to_numpy(); w = d[pr].to_numpy() != t
        for target in TARGETS:
            for sel, ev in [(h, ~h), (~h, h)]:
                thr = choose(s[sel], w[sel], target, ucb=False)
                a = ev & (s >= thr)
                rows.append({"model": model, "R": R, "method": name, "target_%": 100 * target,
                             "coverage_%": 100 * a.sum() / ev.sum(), "risk_%": 100 * w[a].mean() if a.any() else np.nan})
T1 = (pd.DataFrame(rows).groupby(["model", "R", "method", "target_%"]).mean().reset_index().round(3))
T1.to_csv(f"{RES}/T1_split_sample.csv", index=False)
piv = T1.pivot_table(index=["model", "R", "target_%"], columns="method", values="coverage_%").round(2)
piv["max_gap_dist_vs_overlays"] = (piv["Distance rule"] - piv[["Disk overlay", "Gaussian overlay"]].max(axis=1)).abs().round(2)
rep.table("[T1] Coverage (%) when thresholds are chosen on one half of the locations and measured on the other half\n"
          "     (empirical rule; mean of both directions of the split)", piv)
rr = T1.pivot_table(index=["model", "R", "target_%"], columns="method", values="risk_%").round(3)
rep.table("[T1b] Risk (%) on the evaluation half", rr)

# ----------------------------------------------------------------------------- H1 one observation per location
rows = []
for (model, R), d in obs.groupby(["model", "R"]):
    t = d["true_idx"].to_numpy(); fold = d["fold"].to_numpy(); pk = d["picked"].to_numpy()
    for name, (sc, pr) in METHODS.items():
        s = d[sc].to_numpy(); w = d[pr].to_numpy() != t
        for target in TARGETS:
            for f in range(5):
                cal = (fold != f) & pk; te = fold == f
                thr = choose(s[cal], w[cal], target, ucb=True)
                a = te & (s >= thr)
                rows.append({"model": model, "R": R, "method": name, "target_%": 100 * target, "fold": f,
                             "n_test": int(te.sum()), "answered": int(a.sum()), "errors": int(w[a].sum()),
                             "risk_%": 100 * w[a].mean() if a.any() else np.nan})
H = pd.DataFrame(rows)
H.round(4).to_csv(f"{RES}/H1_folds.csv", index=False)
H["over"] = (H["risk_%"] > H["target_%"]).astype(int)
P = (H.groupby(["model", "R", "method", "target_%"])
     .agg(answered=("answered", "sum"), errors=("errors", "sum"), n=("n_test", "sum"),
          zero_cov=("answered", lambda x: int((x == 0).sum())), over=("over", "sum")).reset_index())
P["coverage_%"] = 100 * P["answered"] / P["n"]
P["pooled_risk_%"] = np.where(P["answered"] > 0, 100 * P["errors"] / P["answered"].clip(lower=1), np.nan)
P["met"] = (P["answered"] > 0) & (P["pooled_risk_%"] <= P["target_%"])
P.round(4).to_csv(f"{RES}/H1_pooled.csv", index=False)
S = P.groupby("method").agg(settings=("met", "size"), met=("met", "sum"), no_answers=("answered", lambda x: int((x == 0).sum())),
                            fold_cases_over=("over", "sum"), zero_cov_fold_cases=("zero_cov", "sum"),
                            mean_coverage=("coverage_%", "mean")).reset_index().round(2)
S.to_csv(f"{RES}/H1_summary.csv", index=False)
rep.table("[H1] Held-out states, UCB on one observation per calibration location (120 fold cases per method)", S, index=False)
wm = H.loc[H["over"] == 1].groupby("method")["risk_%"].max()
rep.say("[H1b] worst exceeding fold risk by method: " + "; ".join(f"{k} {v:.3f}%" for k, v in wm.items()) if len(wm) else "[H1b] no fold exceeded its target")
rep.table("[H1c] Distance rule at the 0.1% target, per fold (errors/answered)",
          H[(H["method"] == "Distance rule") & (H["target_%"] == 0.1)][["model", "R", "fold", "errors", "answered", "risk_%"]].round(4),
          index=False)

# ----------------------------------------------------------------------------- P1 projection distortion
if {"lon", "lat"}.issubset(pts.columns):
    lon, lat = pts["lon"].to_numpy(), pts["lat"].to_numpy()
else:
    lon, lat = Transformer.from_crs(C.CRS_M, 4326, always_xy=True).transform(pts["x"].to_numpy(), pts["y"].to_numpy())
f = Proj(f"EPSG:{C.CRS_M}").get_factors(lon, lat)
pts["scale_err_%"] = 100 * np.maximum(np.abs(np.asarray(f.meridional_scale) - 1), np.abs(np.asarray(f.parallel_scale) - 1))
pts["ang_deg"] = np.asarray(f.angular_distortion)
pts["grp"] = np.where(pts["statefp"].astype(str) == "02", "Alaska", np.where(pts["statefp"].astype(str) == "15", "Hawaii", "other states + DC"))
P1 = pts.groupby("grp").agg(n=("statefp", "size"), median_scale_err=("scale_err_%", "median"), max_scale_err=("scale_err_%", "max"),
                            max_angular_deg=("ang_deg", "max")).round(3)
P1.loc["ALL"] = [len(pts), pts["scale_err_%"].median(), pts["scale_err_%"].max(), pts["ang_deg"].max()]
P1.to_csv(f"{RES}/P1_projection.csv")
rep.table("[P1] EPSG:2163 distortion at the 13,000 benchmark locations (linear scale error %, angular distortion deg)", P1.round(3))
rep.say(f"[P1b] locations with scale error > 2%: {int((pts['scale_err_%'] > 2).sum())}; > 5%: {int((pts['scale_err_%'] > 5).sum())}")
rep.save()
