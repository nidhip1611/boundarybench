"""EXP25 — Reference-point sensitivity and block-face definition (round-6 reviews); saved geocodes + cached TIGER edges.

  R0  Addresses without a matched TIGER 2025 edge.
  R1  Stricter reference subsets: by placement type (NAD 'placement', Utah 'PtLocation'; NYC address points vs lots).
  R2  Reference jitter: each reference point moved r = 5, 10, 20 m in a random direction (20 replicates); tract
      disagreement and block-face classification recomputed.
  R3  Block-face definition: distance threshold 30-120 m and edge-end tolerance 1-10 m.
  R4  Table 3 extras: random stratum, worst case with ALL exclusions (Tie, No_Match, >500 m) counted as wrong,
      random-direction CIs (address bootstrap of per-address means over 200 directions).
  R5  Distance flag vs withholding the same share at random.

    python experiments/exp25_reference_sensitivity.py
Outputs -> results/v2_reference_sensitivity/
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely

from src import config as C
from src.geo import load_layers, locate
from src.metrics import wilson
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_reference_sensitivity")
EDG = C.out_dir(C.RAW, "edges")
rep = Report("EXP25 reference-point sensitivity, block-face definition, Table 3 extras", RES)
pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 200)
ORDER = ["NYC, PLUTO", "NYC, Address Points", "Utah, Salt Lake County", "Utah, six rural counties",
         "National, largest-coverage counties", "National, smaller counties"]
M = 50
rng = np.random.default_rng(22)


def as_bool(s):
    return s.astype(str).str.lower().isin(["true", "1", "1.0"])


def wci(k, n):
    lo, hi = wilson(int(k), int(n)) if n else (np.nan, np.nan)
    return f"[{100*max(lo, 0):.2f}, {100*hi:.2f}]"


# ----------------------------------------------------------------------------- scored addresses + Census output
nyc = pd.read_csv(f"{C.RAW}/nyc/nyc_direction_counterfactual.csv")
nyc["group"] = np.where(nyc["sample"] == "PLUTO", "NYC, PLUTO", "NYC, Address Points")
nyc["source"] = nyc["group"]
ut = pd.read_csv(f"{C.RAW}/utah/utah_points.csv")
ut = ut[~ut["PtLocation"].fillna("").str.contains("Geocod", case=False)].copy()
ut["group"] = np.where(ut["region"].str.startswith("urban"), "Utah, Salt Lake County", "Utah, six rural counties")
ut["source"] = "Utah"
na = pd.read_csv(f"{C.RAW}/nad/national_points.csv")
na["group"] = np.where(na["type"] == "urban", "National, largest-coverage counties", "National, smaller counties")
na["source"] = "National"
cols = ["source", "group", "uid", "stratum", "wrong", "tx", "ty", "ox", "oy", "p_random_dir"]
A = pd.concat([nyc[cols], ut[cols], na[cols]], ignore_index=True)
A["wrong"] = as_bool(A["wrong"]); A["near"] = A["stratum"].astype(str).str.startswith("near")
cg = []
for src, path in [("NYC, PLUTO", f"{C.RAW}/nyc/census_geocoded.csv"), ("NYC, Address Points", f"{C.RAW}/nyc/census_geocoded_ap.csv"),
                  ("Utah", f"{C.RAW}/utah/census_geocoded.csv"), ("National", f"{C.RAW}/nad/census_geocoded.csv")]:
    d = pd.read_csv(path, dtype=str); d["source"] = src
    d["uid"] = pd.to_numeric(d["uid"], errors="coerce"); d = d.dropna(subset=["uid"]); d["uid"] = d["uid"].astype(int)
    cg.append(d[d["match"] == "Match"][["source", "uid", "tiger_id", "side", "st", "co"]])
A = A.merge(pd.concat(cg), on=["source", "uid"], how="left")
A["fips"] = A["st"].fillna("").str.zfill(2) + A["co"].fillna("").str.zfill(3)
A["tlid"] = pd.to_numeric(A["tiger_id"], errors="coerce")

# ----------------------------------------------------------------------------- TIGER edges for those counties
parts = []
for f in sorted(A["fips"].dropna().unique()):
    if len(f) != 5 or f == "00000":
        continue
    z = f"{EDG}/tl_2025_{f}_edges.zip"
    if not os.path.exists(z):
        for attempt in range(3):
            try:
                r = requests.get(f"https://www2.census.gov/geo/tiger/TIGER2025/EDGES/tl_2025_{f}_edges.zip", timeout=600)
                r.raise_for_status(); open(z, "wb").write(r.content); break
            except Exception as e:
                print(f"edges {f} attempt {attempt+1}: {e}"); time.sleep(10)
    if os.path.exists(z):
        e = gpd.read_file(f"zip://{z}")
        parts.append(e[["TLID", "geometry"]])
E = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=parts[0].crs).to_crs(C.CRS_M)
E = E.drop_duplicates("TLID").set_index("TLID")
rep.say(f"[M0] edge files: {len(parts)} counties, {len(E):,} edges")
A["has_edge"] = A["tlid"].isin(E.index)
rep.table("[R0] scored addresses without a matched TIGER 2025 edge (TLID not found)", A.groupby(["group", "near"])["has_edge"].apply(lambda x: int((~x).sum())).unstack(), )
ALL = A.copy()
A = A[A["has_edge"]].reset_index(drop=True)
G = shapely.line_merge(np.asarray(E.loc[A["tlid"], "geometry"].values))       # one LineString per edge
G = np.array([g if g.geom_type == "LineString" else max(g.geoms, key=lambda x: x.length) for g in G])
L = shapely.length(G)


def side_of(px, py):
    """+1 if point lies left of the edge's digitized direction, -1 if right (at its nearest point on the edge)."""
    P = shapely.points(px, py)
    t = shapely.line_locate_point(G, P)
    a = shapely.line_interpolate_point(G, np.clip(t - 0.5, 0, L)); b = shapely.line_interpolate_point(G, np.clip(t + 0.5, 0, L))
    ax_, ay_ = shapely.get_x(a), shapely.get_y(a); bx, by = shapely.get_x(b), shapely.get_y(b)
    cr = (bx - ax_) * (py - ay_) - (by - ay_) * (px - ax_)
    return np.sign(cr), t, shapely.distance(G, P)


s_obs, t_obs, d_obs_edge = side_of(A["ox"].to_numpy(), A["oy"].to_numpy())
s_ref, t_ref, d_ref_edge = side_of(A["tx"].to_numpy(), A["ty"].to_numpy())
rep_side = np.where(A["side"] == "L", 1, np.where(A["side"] == "R", -1, 0))
A["geocode_on_reported_side"] = s_obs == rep_side
A["ref_on_reported_side"] = s_ref == rep_side
A["offset_m"] = d_obs_edge
A["ref_to_edge_m"] = d_ref_edge
END = 1.0
A["ref_beyond_end"] = (t_ref <= END) | (t_ref >= L - END)                       # projects onto an end point
A["ref_within_face"] = ~A["ref_beyond_end"] & (A["ref_to_edge_m"] <= 60)


from src.geo import load_layers as _ll
LT = _ll(["tract"])["tract"]
ids = np.char.zfill(np.asarray(LT.ids).astype(str), 11)
tid0 = locate(LT, A["tx"].to_numpy(), A["ty"].to_numpy())
cid = locate(LT, A["ox"].to_numpy(), A["oy"].to_numpy())
NEAR = A["near"].to_numpy()


def faces(tx, ty, dist_thr=60.0, end_tol=1.0):
    s_r, t_r, d_r = side_of(tx, ty)
    beyond = (t_r <= end_tol) | (t_r >= L - end_tol)
    on = (~beyond) & (d_r <= dist_thr) & (s_r == rep_side)
    return on


# ----------------------------------------------------------------------------- R1 placement subsets
nat = pd.read_csv(f"{C.RAW}/nad/national_points.csv", usecols=["uid", "placement"]).assign(source="National")
utp = pd.read_csv(f"{C.RAW}/utah/utah_points.csv", usecols=["uid", "PtLocation"]).rename(columns={"PtLocation": "placement"}).assign(source="Utah")
plc = pd.concat([nat, utp]); plc["placement"] = plc["placement"].fillna("missing")
B = ALL.merge(plc, on=["source", "uid"], how="left")
B["placement"] = np.where(B["source"] == "NYC, PLUTO", "PLUTO lot point", np.where(B["source"] == "NYC, Address Points", "NYC address point", B["placement"]))
B["strict"] = B["placement"].str.contains("Rooftop|Structure|address point", case=False, regex=True)
rows = []
for (g, st), d in B[B["near"]].groupby(["group", "strict"]):
    rows.append({"group": g, "reference": "structure/rooftop/address point" if st else "other placement", "n": len(d),
                 "wrong": int(d["wrong"].sum()), "rate_%": 100 * d["wrong"].mean(), "ci": wci(d["wrong"].sum(), len(d)),
                 "random_dir_%": 100 * d["p_random_dir"].mean()})
d = B[B["near"] & B["strict"]]
rows.append({"group": "ALL", "reference": "structure/rooftop/address point", "n": len(d), "wrong": int(d["wrong"].sum()),
             "rate_%": 100 * d["wrong"].mean(), "ci": wci(d["wrong"].sum(), len(d)), "random_dir_%": 100 * d["p_random_dir"].mean()})
R1 = pd.DataFrame(rows).round(3); R1.to_csv(f"{RES}/R1_placement.csv", index=False)
rep.table("[R1] Near-line disagreement by reference placement type", R1, index=False)

# ----------------------------------------------------------------------------- R3 face definition
on0 = faces(A["tx"].to_numpy(), A["ty"].to_numpy())
w = A["wrong"].to_numpy()
rows = []
for thr in (30, 45, 60, 90, 120):
    for tol in (1, 5, 10):
        on = faces(A["tx"].to_numpy(), A["ty"].to_numpy(), thr, tol)
        rows.append({"dist_thr_m": thr, "end_tol_m": tol, "on_face_n": int((on & NEAR).sum()), "on_face_wrong": int((on & NEAR & w).sum()),
                     "off_face_n": int((~on & NEAR).sum()), "off_face_wrong": int((~on & NEAR & w).sum())})
R3 = pd.DataFrame(rows); R3.to_csv(f"{RES}/R3_face_definition.csv", index=False)
rep.table("[R3] Near-line block-face split under alternative definitions (distance threshold, edge-end tolerance)", R3, index=False)

# ----------------------------------------------------------------------------- R2 reference jitter
rng2 = np.random.default_rng(25)
rows = []
for r in (5, 10, 20):
    dis, onw, onn, offw, offn, moved = [], [], [], [], [], []
    for _ in range(20):
        a = rng2.uniform(0, 2 * np.pi, len(A))
        jx, jy = A["tx"].to_numpy() + r * np.cos(a), A["ty"].to_numpy() + r * np.sin(a)
        jt = locate(LT, jx, jy)
        wr = (jt != cid) & (jt >= 0)
        on = faces(jx, jy)
        dis.append(100 * wr[NEAR].mean()); onn.append((on & NEAR).sum()); onw.append((on & NEAR & wr).sum())
        offn.append((~on & NEAR).sum()); offw.append((~on & NEAR & wr).sum()); moved.append(100 * (on != on0)[NEAR].mean())
    rows.append({"jitter_m": r, "disagreement_%": np.mean(dis), "range": f"{np.min(dis):.2f}-{np.max(dis):.2f}",
                 "on_face_n": np.mean(onn), "on_face_wrong": np.mean(onw), "off_face_n": np.mean(offn), "off_face_wrong": np.mean(offw),
                 "face_class_changed_%": np.mean(moved)})
R2 = pd.DataFrame(rows).round(2); R2.to_csv(f"{RES}/R2_jitter.csv", index=False)
rep.table("[R2] Reference points jittered by r metres (20 replicates; near-line, addresses with a matched edge)", R2, index=False)

# ----------------------------------------------------------------------------- R4 Table 3 extras
S1 = pd.read_csv(f"{C.RESULTS}/v2_realdata_sensitivity/S1_flow.csv")
ORD = ORDER + ["18 sampled counties", "All"]
rows = []
rngb = np.random.default_rng(26)
for g in ORD:
    gs = ORDER[4:] if g == "18 sampled counties" else ORDER if g == "All" else [g]
    for stratum in ("near-line", "random"):
        d = ALL[ALL["group"].isin(gs) & (ALL["near"] == (stratum == "near-line"))]
        f = S1[S1["group"].isin(gs) & (S1["stratum"] == stratum)]
        excl = int(f[["Tie", "No_Match", "Match_excluded"]].sum().sum())
        n, k = len(d), int(d["wrong"].sum())
        pr = d["p_random_dir"].to_numpy()
        bs = [pr[rngb.integers(0, len(pr), len(pr))].mean() for _ in range(2000)]
        rows.append({"row": g, "stratum": stratum, "n": n, "wrong": k, "rate_%": 100 * k / n, "ci": wci(k, n),
                     "all_exclusions": excl, "all_excl_as_wrong_%": 100 * (k + excl) / (n + excl),
                     "random_dir_%": 100 * pr.mean(), "random_dir_ci": f"[{100*np.percentile(bs, 2.5):.2f}, {100*np.percentile(bs, 97.5):.2f}]"})
R4 = pd.DataFrame(rows).round(3); R4.to_csv(f"{RES}/R4_table3_extras.csv", index=False)
rep.table("[R4] Table 3 extras: both strata; worst case counting Tie, No_Match and >500 m matches as wrong; random-direction\n"
          "     CI = address bootstrap of per-address means over 200 directions", R4, index=False)

# ----------------------------------------------------------------------------- R5 distance flag vs random withholding
NL = ALL[ALL["near"]]
dob = pd.concat([pd.read_csv(f"{C.RAW}/nyc/nyc_direction_counterfactual.csv", usecols=["uid", "sample", "d_obs"]).assign(
    source=lambda x: np.where(x["sample"] == "PLUTO", "NYC, PLUTO", "NYC, Address Points")).drop(columns="sample"),
    pd.read_csv(f"{C.RAW}/utah/utah_points.csv", usecols=["uid", "d_obs"]).assign(source="Utah"),
    pd.read_csv(f"{C.RAW}/nad/national_points.csv", usecols=["uid", "d_obs"]).assign(source="National")])
NL = NL.merge(dob, on=["source", "uid"], how="left")
fl = NL["d_obs"] < 7
rep.say(f"[R5] d_obs < 7 m withholds {100*fl.mean():.2f}% and catches {int(NL.loc[fl, 'wrong'].sum())}/{int(NL['wrong'].sum())} "
        f"= {100*NL.loc[fl, 'wrong'].sum()/NL['wrong'].sum():.1f}% of errors; withholding the same share at random catches "
        f"{100*fl.mean():.1f}% in expectation ({fl.mean()*NL['wrong'].sum():.1f} errors)")
rep.save()
