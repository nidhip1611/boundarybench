"""EXP18 — Extra analyses of the EXISTING real-geocoder samples (needs EXP09/11, EXP15, EXP16 outputs; no new data).

Reviewer requests answered here:
  R1  Wrong-tract counts jointly by boundary type (follows a street / not) x Census point on the same / opposite side
      of its nearest street as the reference address (addresses within 50 m of a tract line).
  R2  Real-data behaviour of the distance rule on Census geocodes: answer only if d_obs >= tau, for several tau;
      coverage, risk, and share of wrong-tract cases flagged. Reported per region and stratum (samples are stratified).
  R3  NYC: the two reference sources on OVERLAPPING addresses (same Census geocode within 0.5 m).
  R4  Random-direction rates for the Table 3 rows with 95% bootstrap CIs over addresses (each address already
      averages M = 200 random rotations).
  R5  Execution environment (for the runtime numbers).

    python experiments/exp18_realdata_mechanism.py
Outputs -> results/v2_realdata_extra/
"""
import os
import platform
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd

from src import config as C
from src.metrics import rc_summary, wilson
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_realdata_extra")
rep = Report("EXP18 real-data mechanism, distance rule on real geocodes, NYC overlap, CIs, environment", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 300)
rng = np.random.default_rng(1818)


def as_bool(s):
    return s.astype(str).str.lower().isin(["true", "1", "1.0"])


# ----------------------------------------------------------------------------- load the three real-data samples
nyc = pd.read_csv(f"{C.RAW}/nyc/nyc_direction_counterfactual.csv")
nyc["group"] = "NYC, " + nyc["sample"].map({"PLUTO": "PLUTO", "AddressPoints": "Address Points"}).fillna(nyc["sample"])
nyc["true_to_road_m"] = nyc.get("true_to_road_m", np.nan)

ut = pd.read_csv(f"{C.RAW}/utah/utah_points.csv")
ut = ut[~ut["PtLocation"].fillna("").str.contains("Geocod", case=False)].copy()      # same as table U5
ut["group"] = np.where(ut["region"].str.startswith("urban"), "Utah, Salt Lake County", "Utah, six rural counties")

na = pd.read_csv(f"{C.RAW}/nad/national_points.csv")
na["group"] = np.where(na["type"] == "urban", "National, largest-coverage counties", "National, smaller counties")

cols = ["group", "stratum", "wrong", "d_true", "d_obs", "street_boundary", "same_side", "true_to_road_m",
        "p_random_dir", "disp_m"]
A = pd.concat([nyc[cols], ut[cols], na[cols]], ignore_index=True)
for c in ["wrong", "street_boundary", "same_side"]:
    A[c] = as_bool(A[c])
ORDER = ["NYC, PLUTO", "NYC, Address Points", "Utah, Salt Lake County", "Utah, six rural counties",
         "National, largest-coverage counties", "National, smaller counties"]
rep.say("Addresses per group: " + str(A.groupby("group").size().reindex(ORDER).to_dict()))

# ----------------------------------------------------------------------------- R1 joint table
near = A[A["d_true"] < 50].copy()
near["side"] = np.where(near["true_to_road_m"] > 60, "no street within 60 m",
                        np.where(near["same_side"], "same side", "opposite side"))
near["boundary"] = np.where(near["street_boundary"], "follows a street", "not a street")


def joint(d):
    k, n = int(d["wrong"].sum()), len(d); lo, hi = wilson(k, n) if n else (np.nan, np.nan)
    return pd.Series({"n": n, "wrong": k, "wrong_%": 100 * k / max(n, 1), "ci": f"[{100*lo:.2f}, {100*hi:.2f}]"})


r1 = near.groupby(["group", "boundary", "side"]).apply(joint).reset_index()
r1["group"] = pd.Categorical(r1["group"], ORDER, ordered=True)
r1 = r1.sort_values(["group", "boundary", "side"]).round(3)
r1.to_csv(f"{RES}/R1_boundary_x_side.csv", index=False)
rep.table("[R1] Addresses within 50 m of a tract line: wrong-tract counts by boundary type x street side of the Census\n"
          "     point (side = relative to the TIGER segment nearest the Census point; boundary 'follows a street' if a TIGER\n"
          "     road centerline lies within 1.5 m of the nearest boundary point)", r1, index=False)
pool = near.groupby(["boundary", "side"]).apply(joint).reset_index().round(3)
pool.to_csv(f"{RES}/R1b_pooled.csv", index=False)
rep.table("[R1b] Same, all regions pooled", pool, index=False)

# ----------------------------------------------------------------------------- R2 distance rule on real geocodes
TAUS = [0, 5, 6, 7, 8, 10, 15, 20, 30, 50]
rows = []
for (grp, st), d in A.groupby(["group", "stratum"]):
    w = d["wrong"].to_numpy(); s = d["d_obs"].to_numpy(); n_w = int(w.sum())
    for tau in TAUS:
        ans = s >= tau
        rows.append({"group": grp, "stratum": st, "tau_m": tau, "n": len(d), "coverage_%": 100 * ans.mean(),
                     "risk_%": 100 * (w[ans].mean() if ans.any() else 0.0),
                     "wrong_flagged": f"{int(w[~ans].sum())}/{n_w}"})
r2 = pd.DataFrame(rows)
r2["group"] = pd.Categorical(r2["group"], ORDER, ordered=True)
r2 = r2.sort_values(["group", "stratum", "tau_m"]).round(3)
r2.to_csv(f"{RES}/R2_distance_rule_real.csv", index=False)
rep.table("[R2] Distance rule on real Census geocodes: answer only if d_obs >= tau (d_obs = distance of the Census point\n"
          "     to the boundary of the tract that contains it). wrong_flagged = wrong-tract cases with d_obs < tau", r2, index=False)
rows = []
for (grp, st), d in A.groupby(["group", "stratum"]):
    s = rc_summary(d["d_obs"].to_numpy(), d["wrong"].to_numpy())
    rows.append({"group": grp, "stratum": st, "n": len(d), **{k: s[k] for k in ["err_full_cov_%", "AURC_%",
                 "cov@risk<=1%", "cov@risk<=0.5%", "cov@risk<=0.1%"]}})
r2b = pd.DataFrame(rows); r2b["group"] = pd.Categorical(r2b["group"], ORDER, ordered=True)
r2b = r2b.sort_values(["group", "stratum"]).round(3)
r2b.to_csv(f"{RES}/R2b_distance_rule_real_rc.csv", index=False)
rep.table("[R2b] Risk-coverage of the d_obs ranking on real Census geocodes (per region and stratum)", r2b, index=False)
pn = A[A["stratum"].str.startswith("near")]
rows = []
for tau in TAUS:
    ans = pn["d_obs"].to_numpy() >= tau; w = pn["wrong"].to_numpy()
    rows.append({"tau_m": tau, "n": len(pn), "coverage_%": 100 * ans.mean(), "risk_%": 100 * w[ans].mean(),
                 "wrong_flagged": f"{int(w[~ans].sum())}/{int(w.sum())}"})
r2c = pd.DataFrame(rows).round(3); r2c.to_csv(f"{RES}/R2c_pooled_near.csv", index=False)
rep.table("[R2c] Same, all near-line samples pooled", r2c, index=False)

# ----------------------------------------------------------------------------- R3 NYC overlap
P = nyc[nyc["sample"] == "PLUTO"].reset_index(drop=True)
Q = nyc[nyc["sample"] == "AddressPoints"].reset_index(drop=True)
try:
    from scipy.spatial import cKDTree
    dist, j = cKDTree(Q[["ox", "oy"]].to_numpy()).query(P[["ox", "oy"]].to_numpy(), k=1)
    m = dist <= 0.5
    pairs = pd.DataFrame({"pluto_wrong": as_bool(P.loc[m, "wrong"]).to_numpy(),
                          "ap_wrong": as_bool(Q.loc[j[m], "wrong"]).to_numpy(),
                          "truth_gap_m": np.hypot(P.loc[m, "tx"].to_numpy() - Q.loc[j[m], "tx"].to_numpy(),
                                                  P.loc[m, "ty"].to_numpy() - Q.loc[j[m], "ty"].to_numpy()),
                          "pluto_disp": P.loc[m, "disp_m"].to_numpy(), "ap_disp": Q.loc[j[m], "disp_m"].to_numpy()})
    rep.say(f"[R3] NYC overlap: {len(pairs)} PLUTO addresses share a Census geocode (<= 0.5 m) with an Address Points "
            f"address (of {len(P)} PLUTO, {len(Q)} Address Points).")
    if len(pairs):
        rep.say(f"     wrong tract on overlap: PLUTO {int(pairs['pluto_wrong'].sum())}/{len(pairs)}, "
                f"Address Points {int(pairs['ap_wrong'].sum())}/{len(pairs)}; median distance between the two reference "
                f"points {pairs['truth_gap_m'].median():.1f} m; median displacement PLUTO {pairs['pluto_disp'].median():.1f} m, "
                f"Address Points {pairs['ap_disp'].median():.1f} m")
        pairs.to_csv(f"{RES}/R3_nyc_overlap.csv", index=False)
except Exception as e:      # noqa: BLE001
    rep.say(f"[R3] NYC overlap could not be computed: {e}")

# ----------------------------------------------------------------------------- R4 CIs for random-direction rates
rows = []
for grp in ORDER:
    d = A[(A["group"] == grp) & A["stratum"].str.startswith("near")]
    if grp.startswith("National"):
        continue
    x = d["p_random_dir"].to_numpy()
    bs = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(1000)]
    rows.append({"row": grp, "n": len(x), "random_dir_%": 100 * x.mean(),
                 "ci": f"[{100*np.percentile(bs, 2.5):.2f}, {100*np.percentile(bs, 97.5):.2f}]"})
d = A[A["group"].str.startswith("National") & A["stratum"].str.startswith("near")]
x = d["p_random_dir"].to_numpy(); bs = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(1000)]
rows.append({"row": "National, 18 counties", "n": len(x), "random_dir_%": 100 * x.mean(),
             "ci": f"[{100*np.percentile(bs, 2.5):.2f}, {100*np.percentile(bs, 97.5):.2f}]"})
r4 = pd.DataFrame(rows).round(3); r4.to_csv(f"{RES}/R4_random_direction_ci.csv", index=False)
rep.table("[R4] Random-direction wrong-tract rate, near-line addresses (each address: mean over M = 200 random rotations;\n"
          "     95% CI: bootstrap over addresses, B = 1000)", r4, index=False)

# ----------------------------------------------------------------------------- R5 environment
def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:       # noqa: BLE001
        return ""


try:
    import shapely  # noqa: E402
    shp_v = shapely.__version__
except ImportError:
    shp_v = "n/a"
env = {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
       "cpu": sh("sysctl -n machdep.cpu.brand_string") or platform.processor(),
       "cores": sh("sysctl -n hw.ncpu") or str(os.cpu_count()), "memory_bytes": sh("sysctl -n hw.memsize"),
       "numpy": np.__version__, "pandas": pd.__version__, "shapely": shp_v}
pd.Series(env).to_csv(f"{RES}/R5_environment.csv")
rep.say("[R5] Environment: " + "; ".join(f"{k}={v}" for k, v in env.items()))
rep.save()
