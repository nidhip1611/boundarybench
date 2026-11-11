"""EXP04b — Why do Census Geocoder errors almost never cross tract lines? (needs EXP04 outputs)

For each NYC address: true point T (PLUTO lot centroid), reported point O (Census Geocoder).
Split the displacement O - T into the component ACROSS the nearest tract boundary (toward it = positive)
and the component ALONG it. Isotropic error would put on average half of the squared displacement across
the boundary and spread angles uniformly over 0–90°.

Then repeat the d/R prediction with the real cross-boundary component instead of a random direction,
and test a distance rule calibrated on that component.

    python experiments/exp04b_nyc_mechanism.py
Outputs -> results/v2_nyc_mechanism/
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely

from src import config as C
from src.geo import load_layers, locate, dist_to_own_boundary
from src.metrics import op_point, wilson
from src.report import Report
from src.uncertainty import p_straight_empirical

RES = C.out_dir(C.RESULTS, "v2_nyc_mechanism")
FIG = C.out_dir(RES, "figures")
rep = Report("EXP04b NYC mechanism: across- vs along-boundary geocoding error", RES)
pd.set_option("display.width", 250, "display.max_columns", 30)

path = f"{C.RAW}/nyc/nyc_analysis_points.csv"
assert os.path.exists(path), "Run experiments/exp04_nyc_real.py first"
nyc = pd.read_csv(path)
L = load_layers(["tract"])["tract"]

tx, ty, ox, oy = (nyc[c].to_numpy() for c in ["tx", "ty", "ox", "oy"])
t_idx = locate(L, tx, ty)
keep = t_idx >= 0
nyc, tx, ty, ox, oy, t_idx = nyc[keep].reset_index(drop=True), tx[keep], ty[keep], ox[keep], oy[keep], t_idx[keep]

# nearest point on own tract boundary -> inward unit normal n (from boundary toward the true point)
P = shapely.get_coordinates(shapely.shortest_line(shapely.points(tx, ty), L.bounds[t_idx]))[1::2]
nx, ny = tx - P[:, 0], ty - P[:, 1]
d_true = np.hypot(nx, ny)
ok = d_true > 0.5                                   # direction undefined for points on the line
nx, ny = nx / np.maximum(d_true, 1e-9), ny / np.maximum(d_true, 1e-9)
vx, vy = ox - tx, oy - ty
toward = -(vx * nx + vy * ny)                       # >0: moved toward / across the boundary
along = np.abs(vx * (-ny) + vy * nx)
disp = np.hypot(vx, vy)
angle = np.degrees(np.arctan2(np.abs(toward), along))   # 0 = parallel to boundary, 90 = perpendicular
crisp = locate(L, ox, oy)
wrong = crisp != t_idx

nyc = nyc.assign(d_true=d_true, toward=toward, along=along, angle=angle, wrong=wrong, ok=ok,
                 d_obs=dist_to_own_boundary(L, ox, oy, crisp))
nyc.to_csv(f"{C.RAW}/nyc/nyc_mechanism_points.csv", index=False)
m = nyc[nyc["ok"]]

rows = []
for st, d in [("all", m), ("random", m[m["stratum"] == "random"]), ("near_50m", m[m["stratum"] == "near_50m"])]:
    rows.append({"sample": st, "n": len(d), "median_disp_m": d["disp_m"].median(),
                 "median_|across|_m": d["toward"].abs().median(), "median_along_m": d["along"].median(),
                 "share_sq_disp_across": float((d["toward"] ** 2).sum() / (d["disp_m"] ** 2).sum()),
                 "share_angle<15deg_%": 100 * (d["angle"] < 15).mean(),
                 "share_angle>75deg_%": 100 * (d["angle"] > 75).mean(),
                 "p95_toward_m": d["toward"].quantile(.95), "share_moved_toward_%": 100 * (d["toward"] > 0).mean()})
t1 = pd.DataFrame(rows).round(3); t1.to_csv(f"{RES}/M1_across_vs_along.csv", index=False)
rep.table("[M1] Displacement across vs along the nearest tract boundary (isotropic expectation: share_sq_disp_across = 0.50,\n"
          "     angle <15° and >75° each ≈ 16.7%)", t1, index=False)

# Prediction with the real across-boundary component (calibration half -> test half)
cal, test = m[m["half"] == "cal"], m[m["half"] == "test"]
c_toward = cal["toward"].to_numpy()
rho = cal["disp_m"].to_numpy()
pred_iso = p_straight_empirical(test["d_true"].to_numpy(), rho)
pred_struct = (c_toward[None, :] > test["d_true"].to_numpy()[:, None]).mean(axis=1)
bins = pd.cut(test["d_true"], [0, 10, 25, 50, 100, np.inf], right=False)
t2 = pd.DataFrame({"bin": bins, "wrong": test["wrong"].to_numpy(), "iso": pred_iso, "struct": pred_struct}) \
    .groupby("bin", observed=True).agg(n=("wrong", "size"), observed_pct=("wrong", "mean"),
                                       isotropic_pred_pct=("iso", "mean"), across_component_pred_pct=("struct", "mean"))
t2[["observed_pct", "isotropic_pred_pct", "across_component_pred_pct"]] *= 100
t2 = t2.round(3); t2.to_csv(f"{RES}/M2_prediction_by_distance.csv")
k, n = int(test["wrong"].sum()), len(test); lo, hi = wilson(k, n)
rep.table("[M2] Test half: observed wrong-tract rate vs prediction from (a) isotropic random-direction displacement,\n"
          "     (b) the real across-boundary component (both estimated on the calibration half)", t2)
rep.say(f"     overall: observed {100*k/n:.2f}% [{100*lo:.2f}, {100*hi:.2f}] | isotropic {100*pred_iso.mean():.2f}% | "
        f"across-component {100*pred_struct.mean():.2f}%")

# Distance rule calibrated on displacement magnitude vs on the across component
rows = []
for name, tau in [("tau = p95 displacement", float(np.quantile(rho, .95))),
                  ("tau = p95 across-component", float(np.quantile(np.maximum(c_toward, 0), .95))),
                  ("tau = p99 across-component", float(np.quantile(np.maximum(c_toward, 0), .99)))]:
    for st in ["random", "near_50m"]:
        d = test[test["stratum"] == st]
        r = op_point(d["d_obs"], np.where(d["wrong"], -1, 1), np.ones(len(d)), tau)
        rows.append({"rule": name, "tau_m": round(tau, 1), "stratum": st, **r})
t3 = pd.DataFrame(rows).round(3); t3.to_csv(f"{RES}/M3_distance_rule_calibration.csv", index=False)
rep.table("[M3] Distance rule on the test half with tau from the calibration half", t3, index=False)

fig, axes = plt.subplots(1, 2, figsize=(8, 3))
axes[0].hist(m["angle"], bins=18, range=(0, 90)); axes[0].axhline(len(m) / 18, color="k", ls=":", label="isotropic")
axes[0].set_xlabel("displacement angle to nearest tract boundary (°)\n0 = parallel, 90 = perpendicular"); axes[0].legend()
axes[1].hist(np.clip(m["toward"], -80, 80), bins=80); axes[1].set_xlabel("across-boundary component (m, + = toward)")
plt.tight_layout(); plt.savefig(f"{FIG}/figM1_mechanism.png", dpi=300); plt.close()
rep.save()
