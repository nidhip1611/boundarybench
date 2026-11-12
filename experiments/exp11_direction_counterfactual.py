"""EXP11 — Real-error counterfactual: same displacement LENGTHS, random DIRECTIONS (needs EXP09 outputs).

For every NYC address (both ground truths: PLUTO lot centroids and NYC Address Points) we keep the real Census
displacement length and rotate it to 200 random directions. If the real wrong-tract rate is far below the
random-direction rate, the protection comes from the direction of geocoding errors, not from their size.

    python experiments/exp11_direction_counterfactual.py
Outputs -> results/v2_direction_counterfactual/
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd

from src import config as C
from src.geo import load_layers, locate
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_direction_counterfactual")
rep = Report("EXP11 direction counterfactual (real lengths, random directions)", RES)
pd.set_option("display.width", 250, "display.max_columns", 30)
M, B = 200, 1000

path = f"{C.RAW}/nyc/nyc_streets_points.csv"
assert os.path.exists(path), "Run experiments/exp09_nyc_streets.py first"
D = pd.read_csv(path)
LT = load_layers(["tract"])["tract"]
rng = np.random.default_rng(1111)

tx, ty, t_idx = D["tx"].to_numpy(), D["ty"].to_numpy(), D["t_idx"].to_numpy()
rho = np.hypot(D["ox"] - D["tx"], D["oy"] - D["ty"]).to_numpy()
th = rng.uniform(0, 2 * np.pi, (len(D), M))
lab = locate(LT, (tx[:, None] + rho[:, None] * np.cos(th)).ravel(), (ty[:, None] + rho[:, None] * np.sin(th)).ravel())
D["p_random_dir"] = (lab.reshape(len(D), M) != t_idx[:, None]).mean(axis=1)
D["actual_wrong"] = D["wrong"].astype(float)
D.to_csv(f"{C.RAW}/nyc/nyc_direction_counterfactual.csv", index=False)


def boot(a, b):
    """Bootstrap over addresses: CI of mean(a), mean(b) and of the ratio mean(b)/mean(a)."""
    n = len(a); idx = rng.integers(0, n, (B, n))
    ma, mb = a[idx].mean(1), b[idx].mean(1)
    ratio = np.where(ma > 0, mb / np.maximum(ma, 1e-12), np.nan)
    q = lambda v: np.nanpercentile(v, [2.5, 97.5]).round(3).tolist()
    return q(100 * ma), q(100 * mb), q(ratio)


rows = []
for key, d in list(D.groupby(["sample", "stratum"])) + [(("all", "all"), D)]:
    a, b = d["actual_wrong"].to_numpy(), d["p_random_dir"].to_numpy()
    ca, cb, cr = boot(a, b)
    rows.append({"sample": key[0], "stratum": key[1], "n": len(d), "median_disp_m": round(float(np.median(rho[d.index])), 1),
                 "actual_wrong_%": 100 * a.mean(), "actual_ci": ca,
                 "random_direction_wrong_%": 100 * b.mean(), "random_ci": cb,
                 "random/actual": (b.mean() / a.mean()) if a.mean() > 0 else np.inf, "ratio_ci": cr})
t1 = pd.DataFrame(rows).round(3); t1.to_csv(f"{RES}/D1_actual_vs_random_direction.csv", index=False)
rep.table(f"[D1] Wrong-tract rate: real Census displacement vs the SAME lengths in random directions ({M} draws/address;\n"
          f"     95% CIs: bootstrap over addresses, B = {B})", t1, index=False)

D["band"] = pd.cut(D["d_true"], [0, 10, 25, 50, 100, np.inf], right=False)
t2 = (D.groupby(["sample", "band"], observed=True)
      .agg(n=("actual_wrong", "size"), actual_wrong_pct=("actual_wrong", "mean"), random_dir_wrong_pct=("p_random_dir", "mean")))
t2[["actual_wrong_pct", "random_dir_wrong_pct"]] *= 100
t2 = t2.round(3); t2.to_csv(f"{RES}/D2_by_distance.csv")
rep.table("[D2] Same comparison by the true address's distance to the tract line", t2)
rep.save()
