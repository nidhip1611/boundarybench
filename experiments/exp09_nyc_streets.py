"""EXP09 — NYC mechanism with street centerlines + an independent ground truth.

Two real samples, each geocoded with the US Census batch geocoder:
  PLUTO          lot centroids (EXP04 sample)
  AddressPoints  NYC CSCL address points (~5 ft inside the building, on the addressed street front) — independent truth
For each address we test the street-side explanation of the ~6.3 m pile-up seen in EXP04b:
  A  distance from the Census point to the nearest TIGER street centerline (fixed offset?)
  B  does the true tract boundary at that spot follow a street? wrong-tract rate on street vs non-street boundaries
  C  is the Census point on the same side of its street as the true location?
  D  24 map panels for visual inspection
Also repeats the EXP04 headline numbers on the independent AddressPoints sample.

    python experiments/exp09_nyc_streets.py        (needs internet the first time)
Raw -> $BB_WORK/outputs/nyc/   Tables, figures, summary -> results/v2_nyc_streets/
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely

from src import config as C
from src.geo import load_layers, locate, dist_to_own_boundary
from src.metrics import wilson
from src.nycdata import BORO, census_batch, nyc_address_points, tiger_roads
from src.report import Report
from src.uncertainty import p_straight_empirical

RAW = C.out_dir(C.RAW, "nyc")
RES = C.out_dir(C.RESULTS, "v2_nyc_streets")
FIG = C.out_dir(RES, "figures")
rep = Report("EXP09 NYC street mechanism + independent address-point truth", RES)
pd.set_option("display.width", 250, "display.max_columns", 40)
STREET_TOL = 1.5      # a tract boundary "follows a street" if a TIGER road centerline is within 1.5 m of it
OFFSET_BAND = (5.0, 8.0)

LT = load_layers(["tract"])["tract"]
roads = tiger_roads(os.path.join(RAW, "roads"))
RG = np.array([shapely.get_geometry(g, 0) for g in roads.geometry.to_numpy()])   # single LineStrings
RNAME = roads["FULLNAME"].fillna("").astype(str).to_numpy() if "FULLNAME" in roads.columns else np.full(len(RG), "")
RT = shapely.STRtree(RG)
rep.say(f"TIGER road segments (5 NYC counties): {len(RG):,}")


def nearest_road(x, y):
    idx, dist = RT.query_nearest(shapely.points(x, y), return_distance=True, all_matches=False)
    out_i = np.full(len(x), -1); out_d = np.full(len(x), np.nan)
    out_i[idx[0]] = idx[1]; out_d[idx[0]] = dist
    return out_i, out_d


def side(road_i, qx, qy, px, py):
    """Sign of point (px, py) relative to the direction of road road_i at its closest point to (qx, qy)."""
    line = RG[road_i]
    s = shapely.line_locate_point(line, shapely.points(qx, qy))
    L = shapely.length(line)
    s2 = np.where(s + 1.0 <= L, s + 1.0, s - 1.0)
    a = shapely.get_coordinates(shapely.line_interpolate_point(line, s))
    b = shapely.get_coordinates(shapely.line_interpolate_point(line, s2))
    flip = np.where(s + 1.0 <= L, 1.0, -1.0)
    cross = (b[:, 0] - a[:, 0]) * (py - a[:, 1]) - (b[:, 1] - a[:, 1]) * (px - a[:, 0])
    return np.sign(cross * flip)


# ----------------------------------------------------------------------------- samples
samples = {}
pl = pd.read_csv(f"{RAW}/nyc_analysis_points.csv")
samples["PLUTO"] = pl[["uid", "tx", "ty", "ox", "oy", "stratum", "disp_m", "match_type"]].copy()

ap_path = f"{RAW}/ap_sample_geocoded.parquet"
if not os.path.exists(ap_path):
    ap = nyc_address_points(f"{RAW}/nyc_address_points.csv")
    g = gpd.GeoSeries(gpd.points_from_xy(ap["lon"], ap["lat"]), crs=4326).to_crs(C.CRS_M)
    ap["tx"], ap["ty"] = g.x.to_numpy(), g.y.to_numpy()
    ti = locate(LT, ap["tx"].to_numpy(), ap["ty"].to_numpy())
    ap = ap[ti >= 0].reset_index(drop=True); ti = ti[ti >= 0]
    ap["d_tract"] = dist_to_own_boundary(LT, ap["tx"].to_numpy(), ap["ty"].to_numpy(), ti)
    rng = np.random.default_rng(909)
    near = rng.choice(ap.index[ap["d_tract"] < 50].to_numpy(), size=1500, replace=False)
    rand = rng.choice(np.setdiff1d(ap.index.to_numpy(), near), size=1500, replace=False)
    smp = pd.concat([ap.loc[near].assign(stratum="near_50m"), ap.loc[rand].assign(stratum="random")]).reset_index(drop=True)
    smp["uid"] = np.arange(len(smp))
    rows = [(u, f"{h} {s}", BORO.get(b, "New York"), "NY", z)
            for u, h, s, b, z in zip(smp["uid"], smp["hn"], smp["street"], smp["boro"], smp["zip"])]
    cg = census_batch(rows, f"{RAW}/census_geocoded_ap.csv")
    rep.say(f"[A0] AddressPoints rows: {len(ap):,} | Census match status on sample: {cg['match'].value_counts().to_dict()}")
    smp = smp.merge(cg.loc[cg["match"] == "Match", ["uid", "lon_c", "lat_c", "match_type"]], on="uid")
    gc = gpd.GeoSeries(gpd.points_from_xy(smp["lon_c"], smp["lat_c"]), crs=4269).to_crs(C.CRS_M)
    smp["ox"], smp["oy"] = gc.x.to_numpy(), gc.y.to_numpy()
    smp["disp_m"] = np.hypot(smp["ox"] - smp["tx"], smp["oy"] - smp["ty"])
    smp = smp[smp["disp_m"] <= 500]
    smp[["uid", "tx", "ty", "ox", "oy", "stratum", "disp_m", "match_type"]].to_parquet(ap_path, index=False)
samples["AddressPoints"] = pd.read_parquet(ap_path)

# ----------------------------------------------------------------------------- measurements
allrows = []
for name, s in samples.items():
    tx, ty, ox, oy = (s[c].to_numpy() for c in ["tx", "ty", "ox", "oy"])
    t_idx = locate(LT, tx, ty); keep = t_idx >= 0
    s = s[keep].reset_index(drop=True); tx, ty, ox, oy, t_idx = tx[keep], ty[keep], ox[keep], oy[keep], t_idx[keep]
    c_idx = locate(LT, ox, oy)
    d_true = dist_to_own_boundary(LT, tx, ty, t_idx)
    d_obs = dist_to_own_boundary(LT, ox, oy, c_idx)
    P = shapely.get_coordinates(shapely.shortest_line(shapely.points(tx, ty), LT.bounds[t_idx]))[1::2]
    _, dP_road = nearest_road(P[:, 0], P[:, 1])
    rc, dc_road = nearest_road(ox, oy)
    rt, dt_road = nearest_road(tx, ty)
    Q = shapely.get_coordinates(shapely.shortest_line(shapely.points(ox, oy), RG[rc]))[1::2]
    sO = side(rc, Q[:, 0], Q[:, 1], ox, oy)
    sT = side(rc, Q[:, 0], Q[:, 1], tx, ty)
    allrows.append(pd.DataFrame({"sample": name, "uid": s["uid"].to_numpy(), "match_type": s["match_type"].to_numpy(),
                                 "census_road": RNAME[rc], "true_road": RNAME[rt],
                                 "stratum": s["stratum"].to_numpy(), "disp_m": s["disp_m"].to_numpy(),
                                 "tx": tx, "ty": ty, "ox": ox, "oy": oy, "t_idx": t_idx, "c_idx": c_idx,
                                 "wrong": c_idx != t_idx, "d_true": d_true, "d_obs": d_obs,
                                 "street_boundary": dP_road <= STREET_TOL, "dP_road": dP_road,
                                 "census_to_road_m": dc_road, "true_to_road_m": dt_road,
                                 "same_side": sO == sT, "true_within_60m_of_road": dt_road <= 60}))
D = pd.concat(allrows, ignore_index=True)
D.to_csv(f"{RAW}/nyc_streets_points.csv", index=False)

# A + overall: where do Census points sit relative to streets and tract lines?
rows = []
for (smp_, st), d in D.groupby(["sample", "stratum"]):
    k, n = int(d["wrong"].sum()), len(d); lo, hi = wilson(k, n)
    rows.append({"sample": smp_, "stratum": st, "n": n, "wrong_tract_%": 100 * k / n, "ci": f"[{100*lo:.2f}, {100*hi:.2f}]",
                 "median_disp_m": d["disp_m"].median(),
                 "census_to_street_p10/p50/p90": d["census_to_road_m"].quantile([.1, .5, .9]).round(1).tolist(),
                 "census_to_street_in_5-8m_%": 100 * d["census_to_road_m"].between(*OFFSET_BAND).mean(),
                 "census_to_tract_line_in_5-8m_%": 100 * d["d_obs"].between(*OFFSET_BAND).mean(),
                 "census_to_tract_line<5m_%": 100 * (d["d_obs"] < 5).mean(),
                 "true_to_street_p50": round(d["true_to_road_m"].median(), 1)})
t1 = pd.DataFrame(rows).round(3); t1.to_csv(f"{RES}/S1_overview.csv", index=False)
rep.table("[S1] Census points vs streets and tract lines, both ground truths (A)", t1, index=False)

# B: street-following vs non-street tract boundaries (true points within 50 m of a tract line)
rows = []
for (smp_, sb), d in D[D["d_true"] < 50].groupby(["sample", "street_boundary"]):
    k, n = int(d["wrong"].sum()), len(d); lo, hi = wilson(k, n)
    rho = D.loc[D["sample"] == smp_, "disp_m"].to_numpy()
    rows.append({"sample": smp_, "boundary": "follows a street" if sb else "not a street", "n": n,
                 "wrong_tract_%": 100 * k / n, "ci": f"[{100*lo:.2f}, {100*hi:.2f}]",
                 "isotropic_pred_%": 100 * p_straight_empirical(d["d_true"].to_numpy(), rho).mean(),
                 "census_to_tract_line_in_5-8m_%": 100 * d["d_obs"].between(*OFFSET_BAND).mean(),
                 "census_to_tract_line<5m_%": 100 * (d["d_obs"] < 5).mean()})
t2 = pd.DataFrame(rows).round(3); t2.to_csv(f"{RES}/S2_street_vs_nonstreet_boundary.csv", index=False)
rep.table("[S2] True points within 50 m of a tract line: boundary follows a street (TIGER road within "
          f"{STREET_TOL} m) or not (B)", t2, index=False)

# C: same side of the street
rows = []
for (smp_, w), d in D[D["true_within_60m_of_road"]].groupby(["sample", "wrong"]):
    rows.append({"sample": smp_, "assignment": "wrong tract" if w else "correct tract", "n": len(d),
                 "same_side_of_street_%": 100 * d["same_side"].mean()})
t3 = pd.DataFrame(rows).round(3); t3.to_csv(f"{RES}/S3_same_side.csv", index=False)
rep.table("[S3] Census point on the same side of its nearest street as the true location (C)", t3, index=False)

# figures: offset histograms
fig, axes = plt.subplots(1, 2, figsize=(9, 3), sharey=False)
for ax, (smp_, d) in zip(axes, D.groupby("sample")):
    ax.hist(np.clip(d["census_to_road_m"], 0, 40), bins=80, alpha=.7, label="to nearest street centerline")
    ax.hist(np.clip(d["d_obs"], 0, 40), bins=80, alpha=.5, label="to tract line")
    ax.set_title(f"{smp_}: Census point distances"); ax.set_xlabel("m (clipped at 40)")
axes[0].legend(fontsize=7)
plt.tight_layout(); plt.savefig(f"{FIG}/figS1_offsets.png", dpi=300); plt.close()

# D: map panels
pick = []
near = D[(D["sample"] == "AddressPoints") & (D["d_true"] < 50)]
rng = np.random.default_rng(3)
for cond, k in [(near["wrong"], 8), (~near["wrong"] & near["street_boundary"], 8), (~near["wrong"] & ~near["street_boundary"], 8)]:
    idx = near.index[cond.to_numpy()]
    pick += list(rng.choice(idx, size=min(k, len(idx)), replace=False))
fig, axes = plt.subplots(4, 6, figsize=(18, 12))
for ax, i in zip(axes.ravel(), pick):
    r = D.loc[i]; cx, cy = (r.tx + r.ox) / 2, (r.ty + r.oy) / 2; W = max(60, r.disp_m * 1.3)
    box = shapely.box(cx - W, cy - W, cx + W, cy + W)
    for g in shapely.intersection(LT.bounds[LT.tree.query(box, predicate="intersects")], box):
        for part in shapely.get_parts(g):
            if part.geom_type == "LineString":
                xy = shapely.get_coordinates(part); ax.plot(xy[:, 0], xy[:, 1], "k-", lw=2)
    for g in shapely.intersection(RG[RT.query(box, predicate="intersects")], box):
        for part in shapely.get_parts(g):
            if part.geom_type == "LineString":
                xy = shapely.get_coordinates(part); ax.plot(xy[:, 0], xy[:, 1], color="tab:orange", lw=1)
    ax.annotate("", xy=(r.ox, r.oy), xytext=(r.tx, r.ty), arrowprops=dict(arrowstyle="->", color="tab:red"))
    ax.plot(r.tx, r.ty, "o", color="tab:green", ms=6); ax.plot(r.ox, r.oy, "x", color="tab:red", ms=7)
    ax.set_xlim(cx - W, cx + W); ax.set_ylim(cy - W, cy + W); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{'WRONG' if r.wrong else 'ok'} | {'street' if r.street_boundary else 'non-street'} | d={r.d_true:.0f}m",
                 fontsize=8)
for ax in axes.ravel()[len(pick):]:
    ax.axis("off")
fig.suptitle("green = true address point, red x = Census geocode, black = tract line, orange = TIGER streets", fontsize=10)
plt.tight_layout(); plt.savefig(f"{FIG}/figS2_map_panels.png", dpi=200); plt.close()
rep.say(f"[S4] map panels: {len(pick)} cases in figures/figS2_map_panels.png (rows: wrong, correct-street, correct-non-street)")
rep.save()
