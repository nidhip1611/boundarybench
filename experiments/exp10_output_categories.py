"""EXP10 — Formal output categories: ANSWER / ABSTAIN (competing region) / ABSTAIN (unassigned mass).

For near-boundary EXP01 observations, the overlay returns a probability for every candidate region plus the
UNASSIGNED mass (part of the uncertainty region outside every polygon: water, coastline, ZCTA gaps). With theta = 0.90:
  ANSWER                  top region >= theta
  ABSTAIN-competing       top region < theta and most of the missing mass is another region
  ABSTAIN-unassigned      top region < theta and most of the missing mass is outside every region
Settings: uniform R = 20 and 50 (disk overlay), Gaussian R = 20 (Gaussian overlay).

    python experiments/exp10_output_categories.py
Outputs -> results/v2_output_categories/
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd

from src import config as C
from src.geo import load_layers, load_points, locate, dist_to_own_boundary
from src.obs import regenerate
from src.report import Report
from src.uncertainty import disk_pairs, radial_quadrature, gaussian_rmax

RES = C.out_dir(C.RESULTS, "v2_output_categories")
rep = Report("EXP10 output categories: answer / abstain (competing) / abstain (unassigned)", RES)
pd.set_option("display.width", 250, "display.max_columns", 30)
LAYERS = load_layers()
pts = load_points(LAYERS)


def overlay_pairs(L, x, y, model, R):
    if model == "uniform":
        inp, tr, a, A = disk_pairs(L, x, y, float(R))
        return inp, tr, a / A
    r, wk = radial_quadrature(R / C.GAUSS_K95)
    parts = [disk_pairs(L, x, y, rk) for rk in r]
    return (np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts]),
            np.concatenate([ck * p[2] for ck, p in zip(wk, parts)]))


rows = []
for model, R in [("uniform", 20), ("uniform", 50), ("gaussian", 20)]:
    reach = R if model == "uniform" else gaussian_rmax(R / C.GAUSS_K95)
    for lname, (rp, ox, oy) in regenerate(pts, model, R).items():
        L = LAYERS[lname]
        t = rp["true_idx"].to_numpy()
        crisp = locate(L, ox, oy)
        near = np.where((dist_to_own_boundary(L, ox, oy, crisp) < reach) | (crisp < 0))[0]
        inp, tr, w = overlay_pairs(L, ox[near], oy[near], model, R)
        df = pd.DataFrame({"row": inp, "poly": tr, "w": w}).groupby(["row", "poly"], as_index=False)["w"].sum()
        tot = df.groupby("row")["w"].sum().reindex(range(len(near)), fill_value=0).to_numpy()
        best = df.sort_values(["row", "w"], ascending=[True, False]).drop_duplicates("row").set_index("row")
        p_top = best["w"].reindex(range(len(near)), fill_value=0).to_numpy()
        top = best["poly"].reindex(range(len(near)), fill_value=-1).to_numpy()
        unassigned = np.clip(1 - tot, 0, 1)
        competing = np.clip(tot - p_top, 0, 1)
        answer = p_top >= C.THETA
        cat = np.where(answer, "ANSWER", np.where(unassigned >= competing, "ABSTAIN-unassigned", "ABSTAIN-competing"))
        rows.append({"model": model, "R": R, "layer": lname, "n_near": len(near),
                     "mean_unassigned_%": 100 * unassigned.mean(), "obs_with_unassigned>1%_%": 100 * (unassigned > .01).mean(),
                     "ANSWER_%": 100 * answer.mean(), "ABSTAIN-competing_%": 100 * (cat == "ABSTAIN-competing").mean(),
                     "ABSTAIN-unassigned_%": 100 * (cat == "ABSTAIN-unassigned").mean(),
                     "answer_risk_%": 100 * float((top[answer] != t[near][answer]).mean()) if answer.any() else np.nan})
        print(f"{model} R={R} {lname} done")
t = pd.DataFrame(rows).round(3); t.to_csv(f"{RES}/O1_output_categories.csv", index=False)
rep.table("[O1] Near-boundary observations by output category (theta = 0.90). UNASSIGNED = probability mass outside\n"
          "     every region (water, coastline, ZCTA gaps), reported separately instead of being renormalised.", t, index=False)
rep.save()
