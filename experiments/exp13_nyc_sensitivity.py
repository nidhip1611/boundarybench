"""EXP13 — NYC sensitivity checks and failure taxonomy (needs EXP09 outputs).

1. Street-boundary tolerance: a tract line "follows a street" if a TIGER road is within 1, 1.5, 2, 3 or 5 m.
   Wrong-tract rate and the 5–8 m pile-up for street vs non-street boundaries, Fisher exact test, odds ratio.
2. Census match quality: Exact vs Non_Exact matches.
3. Failure taxonomy: every wrong-tract case, classified by an algorithmic rule:
     opposite side of street   Census point on the other side of its nearest street from the true address
     moved along same street   same side, same nearest street name for both points (slid past a crossing tract line)
     different street          same side, but the Census point's nearest street differs from the true address's
   with match quality and boundary type as extra columns.

    python experiments/exp13_nyc_sensitivity.py
Outputs -> results/v2_nyc_sensitivity/
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd

from src import config as C
from src.metrics import wilson
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_nyc_sensitivity")
rep = Report("EXP13 NYC sensitivity + failure taxonomy", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)
path = f"{C.RAW}/nyc/nyc_streets_points.csv"
assert os.path.exists(path), "Run experiments/exp09_nyc_streets.py first"
D = pd.read_csv(path)
assert {"match_type", "census_road", "true_road"} <= set(D.columns), "Rerun EXP09 (needs match_type / road names)"


def fisher_two_sided(a, b, c, d):
    """2x2 table [[a, b], [c, d]]; exact two-sided p-value."""
    n1, n2, k, n = a + b, c + d, a + c, a + b + c + d
    pmf = lambda x: math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)
    p0 = pmf(a)
    lo, hi = max(0, k - n2), min(k, n1)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= p0 * (1 + 1e-9)))


rows = []
near = D[D["d_true"] < 50]
for smp, dd in near.groupby("sample"):
    for tol in [1.0, 1.5, 2.0, 3.0, 5.0]:
        st = dd["dP_road"] <= tol
        a, b = int(dd.loc[~st, "wrong"].sum()), int((~st).sum() - dd.loc[~st, "wrong"].sum())
        c, d_ = int(dd.loc[st, "wrong"].sum()), int(st.sum() - dd.loc[st, "wrong"].sum())
        orr = ((a + .5) * (d_ + .5)) / ((b + .5) * (c + .5))
        rows.append({"sample": smp, "tol_m": tol, "n_street": int(st.sum()), "n_nonstreet": int((~st).sum()),
                     "wrong_street_%": 100 * c / max(c + d_, 1), "wrong_nonstreet_%": 100 * a / max(a + b, 1),
                     "odds_ratio_nonstreet_vs_street": orr, "fisher_p": fisher_two_sided(a, b, c, d_),
                     "pileup_5-8m_street_%": 100 * dd.loc[st, "d_obs"].between(5, 8).mean(),
                     "pileup_5-8m_nonstreet_%": 100 * dd.loc[~st, "d_obs"].between(5, 8).mean() if (~st).any() else np.nan})
t1 = pd.DataFrame(rows).round(4); t1.to_csv(f"{RES}/N1_street_tolerance.csv", index=False)
rep.table("[N1] Street-boundary tolerance sensitivity (true points within 50 m of a tract line)", t1, index=False)

rows = []
for (smp, mt), dd in D.groupby(["sample", "match_type"]):
    k, n = int(dd["wrong"].sum()), len(dd); lo, hi = wilson(k, n)
    rows.append({"sample": smp, "match_type": mt, "n": n, "wrong_%": 100 * k / n, "ci": f"[{100*lo:.2f}, {100*hi:.2f}]",
                 "median_disp_m": dd["disp_m"].median(), "census_to_street_5-8m_%": 100 * dd["census_to_road_m"].between(5, 8).mean()})
t2 = pd.DataFrame(rows).round(3); t2.to_csv(f"{RES}/N2_match_quality.csv", index=False)
rep.table("[N2] Census Exact vs Non_Exact matches", t2, index=False)

W = D[D["wrong"]].copy()
W["cause"] = np.where(~W["same_side"], "opposite side of street",
             np.where(W["census_road"].fillna("").str.upper() == W["true_road"].fillna("").str.upper(),
                      "moved along same street", "different street"))
W["boundary"] = np.where(W["dP_road"] <= 1.5, "street", "non-street")
cols = ["sample", "stratum", "cause", "boundary", "match_type", "disp_m", "d_true", "d_obs", "census_to_road_m",
        "true_road", "census_road"]
W[cols].round(1).to_csv(f"{RES}/N3_failure_cases.csv", index=False)
rep.table("[N3] Failure taxonomy: counts by cause", W.groupby(["sample", "cause"]).size().unstack(fill_value=0))
rep.table("[N3b] Failure taxonomy: cause × match quality", W.groupby(["cause", "match_type"]).size().unstack(fill_value=0))
rep.table("[N3c] All failure cases", W[cols].round(1), index=False)
rep.save()
