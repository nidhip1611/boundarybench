"""EXP04 — Real-world check (RQ4): NYC tax-lot centroids vs US Census Geocoder output.

Ground truth: PLUTO lot centroids (NYC Open Data 64uk-42ks; centroid constrained to lie inside the lot),
small residential lots with house numbers.
Reported location: US Census batch geocoder (address-range interpolation), benchmark Public_AR_Current.
Sample: 2,500 lots within 50 m of a tract boundary + 2,500 random lots. R is set from a calibration half
(95th-percentile displacement) and all results are reported on the held-out test half.

    python experiments/exp04_nyc_real.py          (needs internet)
Raw -> $BB_WORK/outputs/nyc/   Tables, figure, summary -> results/v2_nyc/
"""
import csv
import io
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

from src import config as C
from src.geo import load_layers, locate, dist_to_own_boundary
from src.metrics import rc_summary, op_point, wilson
from src.report import Report
from src.uncertainty import disk_overlay, p_straight_empirical

RAW = C.out_dir(C.RAW, "nyc")
RES = C.out_dir(C.RESULTS, "v2_nyc")
FIG = C.out_dir(RES, "figures")
rep = Report("EXP04 NYC real-world check (PLUTO vs Census Geocoder)", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 400)
rng = np.random.default_rng(2026)
LAYERS = load_layers()
LT = LAYERS["tract"]

# ----------------------------------------------------------------------------- 1. PLUTO
pluto_path = f"{RAW}/pluto_subset.csv"
cols = "bbl,address,zipcode,borough,latitude,longitude,landuse,lotarea"
if not os.path.exists(pluto_path):
    try:
        r = requests.get("https://data.cityofnewyork.us/resource/64uk-42ks.csv",
                         params={"$select": cols, "$where": "latitude IS NOT NULL AND zipcode IS NOT NULL",
                                 "$limit": 1000000}, timeout=900)
        r.raise_for_status()
        pl = pd.read_csv(io.StringIO(r.text), dtype=str)
    except Exception as e:
        print("SODA query failed, using full export:", e)
        r = requests.get("https://data.cityofnewyork.us/api/views/64uk-42ks/rows.csv?accessType=DOWNLOAD", timeout=1800)
        r.raise_for_status()
        pl = pd.read_csv(io.StringIO(r.text), dtype=str)
        pl.columns = [c.lower() for c in pl.columns]
        pl = pl[cols.split(",")]
    pl.to_csv(pluto_path, index=False)
pl = pd.read_csv(pluto_path, dtype=str)
n_raw = len(pl)
for c in ["latitude", "longitude", "lotarea", "landuse"]:
    pl[c] = pd.to_numeric(pl[c], errors="coerce")
pl = pl[pl["address"].fillna("").str.match(r"^\d+[A-Z]?(-\d+)?\s+\S")]
pl = pl[pl["landuse"].isin([1, 2, 3, 4]) & pl["lotarea"].between(500, 10000)]
pl = pl.dropna(subset=["latitude", "longitude", "zipcode"]).drop_duplicates("bbl").reset_index(drop=True)
rep.say(f"[N1] PLUTO rows: {n_raw:,} | eligible small residential lots with house numbers: {len(pl):,}")
g = gpd.GeoSeries(gpd.points_from_xy(pl["longitude"], pl["latitude"]), crs=4326).to_crs(C.CRS_M)
pl["tx"], pl["ty"] = g.x.to_numpy(), g.y.to_numpy()
pl["t_tract"] = locate(LT, pl["tx"].to_numpy(), pl["ty"].to_numpy())
pl = pl[pl["t_tract"] >= 0].reset_index(drop=True)
pl["d_tract"] = dist_to_own_boundary(LT, pl["tx"].to_numpy(), pl["ty"].to_numpy(), pl["t_tract"].to_numpy())

# ----------------------------------------------------------------------------- 2. stratified sample
near_pool = pl.index[pl["d_tract"] < 50].to_numpy()
s_near = rng.choice(near_pool, size=min(2500, len(near_pool)), replace=False)
s_rand = rng.choice(np.setdiff1d(pl.index.to_numpy(), s_near), size=2500, replace=False)
smp = pd.concat([pl.loc[s_near].assign(stratum="near_50m"), pl.loc[s_rand].assign(stratum="random")]).reset_index(drop=True)
smp["uid"] = np.arange(len(smp))
CITY = {"MN": "New York", "BX": "Bronx", "BK": "Brooklyn", "QN": "Queens", "SI": "Staten Island"}
smp["city"] = smp["borough"].map(CITY).fillna("New York")

# ----------------------------------------------------------------------------- 3. Census Geocoder
geo_path = f"{RAW}/census_geocoded.csv"
if not os.path.exists(geo_path):
    out_rows = []
    for start in range(0, len(smp), 2500):
        chunk = smp.iloc[start:start + 2500]
        buf = io.StringIO(); w = csv.writer(buf)
        for _, rr in chunk.iterrows():
            w.writerow([rr["uid"], rr["address"], rr["city"], "NY", str(rr["zipcode"])[:5]])
        for attempt in range(3):
            try:
                resp = requests.post("https://geocoding.geo.census.gov/geocoder/geographies/addressbatch",
                                     files={"addressFile": ("addresses.csv", buf.getvalue().encode(), "text/csv")},
                                     data={"benchmark": "Public_AR_Current", "vintage": "Current_Current"}, timeout=1800)
                resp.raise_for_status()
                break
            except Exception as e:
                print(f"census batch attempt {attempt + 1} failed: {e}"); time.sleep(20)
        else:
            raise RuntimeError("Census Geocoder unavailable")
        out_rows += [rec + [""] * (12 - len(rec)) for rec in csv.reader(io.StringIO(resp.text)) if rec]
        print(f"geocoded {min(start + 2500, len(smp))}/{len(smp)}")
    pd.DataFrame([r[:12] for r in out_rows], columns=["uid", "input", "match", "match_type", "out_address", "coords",
                  "tiger_id", "side", "st", "co", "tract", "block"]).to_csv(geo_path, index=False)
cg = pd.read_csv(geo_path, dtype=str)
cg["uid"] = pd.to_numeric(cg["uid"], errors="coerce")
cg = cg.dropna(subset=["uid"]); cg["uid"] = cg["uid"].astype(int)
rep.say(f"[N2] Census match status: {cg['match'].value_counts().to_dict()} | type: {cg['match_type'].value_counts().to_dict()}")
cg = cg[cg["match"] == "Match"].copy()
xy = cg["coords"].str.split(",", expand=True).astype(float)
cg["lon_c"], cg["lat_c"] = xy[0], xy[1]
cg["census_tract_geoid"] = cg["st"].str.zfill(2) + cg["co"].str.zfill(3) + cg["tract"].str.zfill(6)
nyc = smp.merge(cg[["uid", "match_type", "lon_c", "lat_c", "census_tract_geoid"]], on="uid")
g = gpd.GeoSeries(gpd.points_from_xy(nyc["lon_c"], nyc["lat_c"]), crs=4269).to_crs(C.CRS_M)
nyc["ox"], nyc["oy"] = g.x.to_numpy(), g.y.to_numpy()
nyc["disp_m"] = np.hypot(nyc["ox"] - nyc["tx"], nyc["oy"] - nyc["ty"])
gross = nyc["disp_m"] > 500
rep.say(f"[N2] matched {len(nyc):,} | gross errors (>500 m, likely wrong address match) excluded: {int(gross.sum())}")
nyc = nyc[~gross].reset_index(drop=True)
q = nyc["disp_m"].quantile([.5, .75, .9, .95, .99])
rep.say("[N2] displacement (m): " + " | ".join(f"p{int(k*100)} {v:.1f}" for k, v in q.items()))

# ----------------------------------------------------------------------------- 4. calibration / test
nyc["half"] = np.where(rng.uniform(size=len(nyc)) < 0.5, "cal", "test")
rho = nyc.loc[nyc["half"] == "cal", "disp_m"].to_numpy()
R_HAT = float(np.quantile(rho, 0.95))
rep.say(f"[N3] R from calibration half (p95 displacement): {R_HAT:.1f} m")
test = nyc[nyc["half"] == "test"].reset_index(drop=True)
res_rows, bin_rows = [], []
for lname in ["tract", "zcta", "county"]:
    L = LAYERS[lname]
    tx, ty, ox, oy = (test[c].to_numpy() for c in ["tx", "ty", "ox", "oy"])
    t_idx = locate(L, tx, ty); keep = t_idx >= 0
    tx, ty, ox, oy, t_idx = tx[keep], ty[keep], ox[keep], oy[keep], t_idx[keep]
    strat = test["stratum"].to_numpy()[keep]
    d_true = dist_to_own_boundary(L, tx, ty, t_idx)
    crisp = locate(L, ox, oy); wrong = crisp != t_idx
    d_obs = dist_to_own_boundary(L, ox, oy, crisp)
    near = np.where((d_obs < R_HAT) | (crisp < 0))[0]
    ex_idx, ex_p = crisp.copy(), np.ones(len(crisp))
    a, b, _ = disk_overlay(L, ox[near], oy[near], R_HAT, t_idx[near])
    ex_idx[near], ex_p[near] = a, b
    pred = p_straight_empirical(d_true, rho)
    for st in ["random", "near_50m"]:
        m = strat == st
        k, n = int(wrong[m].sum()), int(m.sum()); lo, hi = wilson(k, n)
        res_rows.append({"layer": lname, "stratum": st, "n": n, "wrong_%": 100 * k / max(n, 1),
                         "ci_low_%": 100 * lo, "ci_high_%": 100 * hi, "straight_line_pred_%": 100 * pred[m].mean(),
                         **{f"dist_{k_}": v for k_, v in op_point(d_obs[m], crisp[m], t_idx[m], R_HAT).items()},
                         **{f"disk_{k_}": v for k_, v in op_point(ex_p[m], ex_idx[m], t_idx[m], C.THETA).items()},
                         "dist_AURC_%": rc_summary(d_obs[m], wrong[m])["AURC_%"],
                         "disk_AURC_%": rc_summary(ex_p[m], ex_idx[m] != t_idx[m])["AURC_%"]})
    bt = pd.DataFrame({"bin": pd.cut(d_true, [0, 10, 25, 50, 100, 250, np.inf], right=False), "wrong": wrong, "pred": pred}) \
        .groupby("bin", observed=True).agg(n=("wrong", "size"), observed_pct=("wrong", "mean"), straight_line_pct=("pred", "mean"))
    bt[["observed_pct", "straight_line_pct"]] *= 100
    bt.insert(0, "layer", lname); bin_rows.append(bt.reset_index())
    if lname == "tract":
        ct = test["census_tract_geoid"].to_numpy()[keep]
        agree = np.mean([c >= 0 and LT.ids[c] == g_ for c, g_ in zip(crisp, ct)])
        rep.say(f"[N4] Census-returned tract equals our TIGER lookup of the Census point: {100 * agree:.2f}%")
c6 = pd.DataFrame(res_rows).round(3); c6.to_csv(f"{RES}/N5_results.csv", index=False)
c7 = pd.concat(bin_rows, ignore_index=True).round(3); c7.to_csv(f"{RES}/N6_by_distance.csv", index=False)
nyc.to_csv(f"{RAW}/nyc_analysis_points.csv", index=False)
rep.table("[N5] Test half: real wrong-region rate, straight-line prediction (real displacements, random direction),\n"
          "     distance rule (tau = R) and disk overlay (theta = 0.90) at R_hat. 'random' = population-like sample.", c6, index=False)
rep.table("[N6] Test half: wrong-region rate by true distance to boundary", c7, index=False)

fig, ax = plt.subplots(figsize=(4.5, 3))
ax.hist(np.clip(nyc["disp_m"], 0, 200), bins=80)
ax.axvline(R_HAT, color="k", ls="--", label=f"R = p95 = {R_HAT:.0f} m")
ax.set_xlabel("Census Geocoder displacement from lot centroid (m)"); ax.set_ylabel("addresses"); ax.legend()
plt.tight_layout(); plt.savefig(f"{FIG}/figN1_displacement.png", dpi=300); plt.close()
rep.save()
