"""EXP22 — Mechanism test with the street edge the Census geocoder actually matched (TIGER/Line ID + side it returned).

Downloads TIGER/Line 2025 'All Lines' (EDGES) files for the counties of the matched addresses (~30 files) and uses the
returned TLID and side (L/R relative to the edge's digitized direction).

  M1  Checks: matched edge found; geocode offset from the matched edge; geocode lies on the side the geocoder reports.
  M2  Reference point relative to the matched edge: same side as reported?  projects within the edge (same block
      face) or beyond its ends?  distance to the edge. Wrong-tract cases classified by these.
  M3  Segment-constrained counterfactual: each address is re-placed at M = 50 uniformly random positions ALONG ITS
      MATCHED EDGE, at its own observed offset, (a) on the reported side, (b) on the opposite side. Share of positions
      outside the reference tract -> how much of the low observed rate is explained by staying on the matched block
      face and side.

    python experiments/exp22_matched_edge.py
Outputs -> results/v2_matched_edge/        Edge files -> $BB_WORK/outputs/edges/
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

RES = C.out_dir(C.RESULTS, "v2_matched_edge")
EDG = C.out_dir(C.RAW, "edges")
rep = Report("EXP22 matched-edge mechanism test (Census TLID + side)", RES)
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
cols = ["source", "group", "uid", "stratum", "wrong", "tx", "ty", "ox", "oy"]
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

# ----------------------------------------------------------------------------- M1 checks
rows = []
for g in ORDER + ["ALL"]:
    d = A if g == "ALL" else A[A["group"] == g]
    rows.append({"group": g, "n": len(d), "offset_p50_m": d["offset_m"].median(),
                 "offset_5_8m_%": 100 * d["offset_m"].between(5, 8).mean(),
                 "geocode_on_reported_side_%": 100 * d["geocode_on_reported_side"].mean(),
                 "ref_on_reported_side_%": 100 * d["ref_on_reported_side"].mean(),
                 "ref_within_matched_face_%": 100 * d["ref_within_face"].mean()})
M1 = pd.DataFrame(rows).round(2); M1.to_csv(f"{RES}/M1_checks.csv", index=False)
rep.table("[M1] All scored addresses with a matched edge: offset from the matched edge, side checks, and whether the\n"
          "     reference point lies on the same block face (projects inside the edge, <= 60 m away)", M1, index=False)

# ----------------------------------------------------------------------------- M2 classification of wrong-tract cases
K = A[A["near"]].copy()
K["case"] = np.select([K["ref_to_edge_m"] > 60, K["ref_beyond_end"], ~K["ref_on_reported_side"]],
                      ["reference > 60 m from matched edge", "reference beyond matched edge end", "reference on other side"],
                      "same face, same side")
M2 = K.groupby("case").agg(n=("wrong", "size"), wrong=("wrong", "sum")).reset_index()
M2["wrong_%"] = 100 * M2["wrong"] / M2["n"]; M2["ci"] = [wci(k, n) for k, n in zip(M2["wrong"], M2["n"])]
M2 = M2.round(3); M2.to_csv(f"{RES}/M2_cases.csv", index=False)
rep.table("[M2] Near-line cohort by the reference point's position relative to the edge the geocoder matched", M2, index=False)
rep.table("[M2b] per group", K.groupby(["group", "case"]).agg(n=("wrong", "size"), wrong=("wrong", "sum")).reset_index(), index=False)

# ----------------------------------------------------------------------------- M3 segment-constrained counterfactual
LT = load_layers(["tract"])["tract"]
tid = locate(LT, A["tx"].to_numpy(), A["ty"].to_numpy())
off = np.clip(A["offset_m"].to_numpy(), 0.5, 30)
res = {}
for name, sgn in [("reported side", rep_side), ("opposite side", -rep_side)]:
    wr = np.zeros(len(A))
    curves = shapely.offset_curve(G, sgn * off)                                  # + = left, - = right (shapely >= 2)
    curves = np.array([c if c.geom_type == "LineString" else max(c.geoms, key=lambda x: x.length) if not c.is_empty else g
                       for c, g in zip(curves, G)])
    for _ in range(M):
        p = shapely.line_interpolate_point(curves, rng.random(len(A)), normalized=True)
        wr += locate(LT, shapely.get_x(p), shapely.get_y(p)) != tid
    res[name] = wr / M
A["cf_face_same"], A["cf_face_opp"] = res["reported side"], res["opposite side"]
rows = []
for scope, D in [("near-line", A[A["near"] & (tid[A.index] >= 0)]), ("all scored", A[tid >= 0])]:
    for g in ORDER + ["ALL"]:
        d = D if g == "ALL" else D[D["group"] == g]
        if len(d) == 0:
            continue
        rows.append({"scope": scope, "group": g, "n": len(d), "observed_%": 100 * d["wrong"].mean(),
                     "obs_ci": wci(d["wrong"].sum(), len(d)),
                     "random_position_on_matched_face_%": 100 * d["cf_face_same"].mean(),
                     "same_but_opposite_side_%": 100 * d["cf_face_opp"].mean()})
M3 = pd.DataFrame(rows).round(3); M3.to_csv(f"{RES}/M3_face_counterfactual.csv", index=False)
rep.table(f"[M3] Re-placing each geocode at M = {M} random positions along its matched edge (own offset): reported side vs\n"
          "     opposite side; share outside the reference tract", M3, index=False)
A.drop(columns=["geometry"], errors="ignore").to_csv(f"{RES}/M_points.csv", index=False)
rep.save()
