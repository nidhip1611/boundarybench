"""EXP19 — Reconciled real-data analyses on ONE cohort + flags available at assignment time (no new data, no geocoding).

Cohort used everywhere: the NEAR-LINE STRATUM of Table 2 (addresses sampled because their reference point lies within
50 m of a tract line), after the same exclusions as Table 2 (Utah: reference points placed by geocoding removed).

  P0  Pipeline counts per source: submitted to the Census geocoder, Match / Tie / No_Match, scored, near-line cohort.
  P1  Cohort check: n and wrong per row must equal Table 2.
  P2  Breakdown by region x boundary type (at the reference point) x street side of the geocode, with counts.
  P3  Street vs non-street boundaries on the same cohort (+ pooled Fisher test).
  P4  Along-street / cross-street components of each displacement (relative to the TIGER segment nearest the
      reference point); rates excluding geocodes near an intersection (within 15 m of a segment end) or with an
      ambiguous nearest segment (second-nearest segment within 2 m).
  P5  Flags available at assignment time (from the GEOCODE only): (a) distance d_obs < tau; (b) the tract line
      nearest the geocode does not follow a street (no TIGER centerline within 1.5 m of its nearest boundary point)
      and d_obs < 50 m; (c) a or b. Coverage, errors caught, risk among answered; distance flag at matched coverage.
  P6  Wrong-tract rate by reference placement type (national NAD 'placement', Utah 'PtLocation').

    python experiments/exp19_realdata_reconcile.py
Outputs -> results/v2_realdata_reconcile/
"""
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.stats import fisher_exact

from src import config as C
from src.geo import load_layers, locate
from src.metrics import wilson
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_realdata_reconcile")
rep = Report("EXP19 reconciled real-data cohort, street-side breakdown, along/cross components, assignment-time flags", RES)
pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 400)
TOL, NEAR_END, AMBIG = 1.5, 15.0, 2.0


def as_bool(s):
    return s.astype(str).str.lower().isin(["true", "1", "1.0"])


def ci(k, n):
    lo, hi = wilson(int(k), int(n)) if n else (np.nan, np.nan)
    return f"[{100*max(lo, 0):.2f}, {100*hi:.2f}]"


# ----------------------------------------------------------------------------- data
nyc = pd.read_csv(f"{C.RAW}/nyc/nyc_direction_counterfactual.csv")
nyc["group"] = np.where(nyc["sample"] == "PLUTO", "NYC, PLUTO", "NYC, Address Points")
nyc["region"] = "nyc"
ut = pd.read_csv(f"{C.RAW}/utah/utah_points.csv")
ut = ut[~ut["PtLocation"].fillna("").str.contains("Geocod", case=False)].copy()
ut["group"] = np.where(ut["region"].str.startswith("urban"), "Utah, Salt Lake County", "Utah, six rural counties")
ut["region"] = "utah"
na = pd.read_csv(f"{C.RAW}/nad/national_points.csv")
na["group"] = np.where(na["type"] == "urban", "National, largest-coverage counties", "National, smaller counties")
na["region"] = "nad"
ORDER = ["NYC, PLUTO", "NYC, Address Points", "Utah, Salt Lake County", "Utah, six rural counties",
         "National, largest-coverage counties", "National, smaller counties"]
cols = ["group", "region", "stratum", "wrong", "tx", "ty", "ox", "oy", "d_true", "d_obs", "street_boundary",
        "same_side", "true_to_road_m", "disp_m"]
A = pd.concat([nyc[cols], ut[cols], na[cols]], ignore_index=True)
for c in ["wrong", "street_boundary", "same_side"]:
    A[c] = as_bool(A[c])
pl_n = np.where(nyc["sample"] == "PLUTO", "PLUTO lot point", "NYC address point")
pl_u = ut["PtLocation"].fillna("missing").astype(str).to_numpy()
pl_a = na["placement"].fillna("missing").astype(str).to_numpy() if "placement" in na else np.full(len(na), "n/a")
A["placement"] = np.concatenate([pl_n, pl_u, pl_a])

# ----------------------------------------------------------------------------- P0 pipeline counts
rows = []
for name, path, scored in [("NYC, PLUTO", f"{C.RAW}/nyc/census_geocoded.csv", (nyc["sample"] == "PLUTO").sum()),
                           ("NYC, Address Points", f"{C.RAW}/nyc/census_geocoded_ap.csv", (nyc["sample"] != "PLUTO").sum()),
                           ("Utah (both regions)", f"{C.RAW}/utah/census_geocoded.csv", len(pd.read_csv(f"{C.RAW}/utah/utah_points.csv"))),
                           ("National (18 counties)", f"{C.RAW}/nad/census_geocoded.csv", len(na))]:
    if os.path.exists(path):
        cg = pd.read_csv(path, dtype=str)
        vc = cg["match"].value_counts().to_dict()
        rows.append({"source": name, "submitted": len(cg), "Match": vc.get("Match", 0), "Tie": vc.get("Tie", 0),
                     "No_Match": vc.get("No_Match", 0), "scored": int(scored),
                     "matched_not_scored": vc.get("Match", 0) - int(scored)})
    else:
        rows.append({"source": name, "submitted": np.nan, "scored": int(scored), "note": f"missing {path}"})
p0 = pd.DataFrame(rows); p0.to_csv(f"{RES}/P0_pipeline.csv", index=False)
rep.table("[P0] Pipeline: addresses submitted, Census match status, scored. Only 'Match' is scored; 'Tie' and 'No_Match'\n"
          "     are excluded; matched_not_scored = displacement > 500 m (treated as a wrong address match) or reference point\n"
          "     outside every tract. Utah scored count is before removing reference points placed by geocoding.", p0, index=False)

# ----------------------------------------------------------------------------- P1 cohort
K = A[A["stratum"].astype(str).str.startswith("near")].copy()
p1 = K.groupby("group").agg(n=("wrong", "size"), wrong=("wrong", "sum")).reindex(ORDER)
p1["wrong_%"] = 100 * p1["wrong"] / p1["n"]
p1.loc["TOTAL"] = [p1["n"].sum(), p1["wrong"].sum(), 100 * p1["wrong"].sum() / p1["n"].sum()]
p1.round(3).to_csv(f"{RES}/P1_cohort.csv")
rep.table("[P1] Near-line cohort (= Table 2 rows; the 18-county row is the sum of the two national groups)", p1.round(3))

# ----------------------------------------------------------------------------- P2 breakdown
K["boundary"] = np.where(K["street_boundary"], "street", "non-street")
K["side"] = np.where(K["true_to_road_m"] > 60, "no street <= 60 m", np.where(K["same_side"], "same side", "opposite side"))


def tab(d, keys):
    t = d.groupby(keys).agg(n=("wrong", "size"), wrong=("wrong", "sum")).reset_index()
    t["wrong_%"] = 100 * t["wrong"] / t["n"]
    t["ci"] = [ci(k, n) for k, n in zip(t["wrong"], t["n"])]
    return t.round(3)


p2 = tab(K, ["group", "boundary", "side"]); p2.to_csv(f"{RES}/P2_breakdown.csv", index=False)
rep.table("[P2] Near-line cohort by region x boundary type (at the reference point) x street side of the geocode", p2, index=False)
p2b = tab(K, ["boundary", "side"]); p2b.to_csv(f"{RES}/P2b_pooled.csv", index=False)
rep.table("[P2b] Same, pooled (rows sum to the cohort total in P1)", p2b, index=False)

# ----------------------------------------------------------------------------- P3 street vs non-street
p3 = tab(K, ["group", "boundary"]); p3.to_csv(f"{RES}/P3_street_vs_nonstreet.csv", index=False)
rep.table("[P3] Near-line cohort: street vs non-street boundary per region", p3, index=False)
a = K.groupby("boundary")["wrong"].agg(["sum", "size"])
k_ns, n_ns = int(a.loc["non-street", "sum"]), int(a.loc["non-street", "size"])
k_s, n_s = int(a.loc["street", "sum"]), int(a.loc["street", "size"])
orr, p = fisher_exact([[k_ns, n_ns - k_ns], [k_s, n_s - k_s]])
rep.say(f"[P3b] pooled near-line cohort: non-street {k_ns}/{n_ns} = {100*k_ns/n_ns:.2f}% vs street {k_s}/{n_s} = "
        f"{100*k_s/n_s:.2f}%; odds ratio {orr:.2f}, Fisher two-sided p = {p:.4f}")
for excl in [["NYC, PLUTO", "NYC, Address Points"]]:
    d = K[~K["group"].isin(excl)]
    b = d.groupby("boundary")["wrong"].agg(["sum", "size"])
    o2, p2_ = fisher_exact([[b.loc["non-street", "sum"], b.loc["non-street", "size"] - b.loc["non-street", "sum"]],
                            [b.loc["street", "sum"], b.loc["street", "size"] - b.loc["street", "sum"]]])
    rep.say(f"[P3c] without NYC: non-street {int(b.loc['non-street','sum'])}/{int(b.loc['non-street','size'])} vs street "
            f"{int(b.loc['street','sum'])}/{int(b.loc['street','size'])}; OR {o2:.2f}, p = {p2_:.4f}")

# ----------------------------------------------------------------------------- roads (cached TIGER zips)
zips = sorted(set(glob.glob(f"{C.RAW}/nyc/roads/tl_2025_*_roads.zip") + glob.glob(f"{C.RAW}/utah/tl_2025_*_roads.zip") +
                  glob.glob(f"{C.RAW}/nad/tl_2025_*_roads.zip")))
rep.say(f"TIGER road files found: {len(zips)}")
parts = [gpd.read_file(f"zip://{z}") for z in zips]
roads = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=parts[0].crs).to_crs(C.CRS_M)
RG = np.array([shapely.get_geometry(g, 0) for g in roads.geometry.to_numpy()])
RT = shapely.STRtree(RG)
LT = load_layers(["tract"])["tract"]


def nearest2(x, y):
    """nearest road index and distance, and distance to the second-nearest road."""
    P = shapely.points(x, y)
    i1, d1 = RT.query_nearest(P, return_distance=True, all_matches=False)
    order = np.argsort(i1[0]); i_r = np.empty(len(x), int); d_r = np.empty(len(x))
    i_r[i1[0][order]] = i1[1][order]; d_r[i1[0][order]] = d1[order]
    cand_p, cand_r = RT.query(P, predicate="dwithin", distance=d_r + AMBIG + 1)
    dd = shapely.distance(P[cand_p], RG[cand_r])
    df = pd.DataFrame({"p": cand_p, "r": cand_r, "d": dd})
    df = df[df["r"].to_numpy() != i_r[df["p"].to_numpy()]]
    second = df.groupby("p")["d"].min().reindex(range(len(x))).fillna(np.inf).to_numpy()
    return i_r, d_r, second


# ----------------------------------------------------------------------------- P4 along / cross components
tx, ty, ox, oy = (K[c].to_numpy() for c in ["tx", "ty", "ox", "oy"])
ri, _, _ = nearest2(tx, ty)
lines = RG[ri]
s = shapely.line_locate_point(lines, shapely.points(tx, ty)); Ln = shapely.length(lines)
s2 = np.where(s + 1.0 <= Ln, s + 1.0, s - 1.0); sgn = np.where(s + 1.0 <= Ln, 1.0, -1.0)
a_ = shapely.get_coordinates(shapely.line_interpolate_point(lines, s))
b_ = shapely.get_coordinates(shapely.line_interpolate_point(lines, s2))
tvec = (b_ - a_) * sgn[:, None]; tvec /= np.maximum(np.linalg.norm(tvec, axis=1, keepdims=True), 1e-9)
v = np.c_[ox - tx, oy - ty]
K["along_m"] = np.abs((v * tvec).sum(1))
K["cross_m"] = np.abs(v[:, 0] * tvec[:, 1] - v[:, 1] * tvec[:, 0])
gi, gd, g2 = nearest2(ox, oy)
gl = RG[gi]; gs = shapely.line_locate_point(gl, shapely.points(ox, oy)); gL = shapely.length(gl)
K["near_intersection"] = np.minimum(gs, gL - gs) < NEAR_END
K["ambiguous_segment"] = (g2 - gd) < AMBIG
p4 = K.groupby("group").agg(n=("wrong", "size"), along_p50=("along_m", "median"), cross_p50=("cross_m", "median"),
                            along_p90=("along_m", lambda x: x.quantile(.9)), cross_p90=("cross_m", lambda x: x.quantile(.9)),
                            near_intersection_pct=("near_intersection", "mean"),
                            ambiguous_pct=("ambiguous_segment", "mean")).reindex(ORDER)
p4[["near_intersection_pct", "ambiguous_pct"]] *= 100
p4.round(2).to_csv(f"{RES}/P4_components.csv")
rep.table("[P4] Displacement components relative to the TIGER segment nearest the reference point (m), near-line cohort", p4.round(2))
p4w = K.groupby("wrong").agg(n=("wrong", "size"), along_p50=("along_m", "median"), cross_p50=("cross_m", "median")).round(2)
rep.table("[P4b] Components for correct vs wrong-tract geocodes (pooled)", p4w)
clean = K[~K["near_intersection"] & ~K["ambiguous_segment"]]
p4c = tab(clean, ["group"]); p4c.to_csv(f"{RES}/P4c_excl_intersections.csv", index=False)
rep.table(f"[P4c] Near-line cohort EXCLUDING geocodes within {NEAR_END:.0f} m of a segment end or with an ambiguous nearest "
          f"segment (second-nearest within {AMBIG:.0f} m): wrong-tract rate", p4c, index=False)
rep.table("[P4d] Same exclusion, pooled boundary x side", tab(clean, ["boundary", "side"]), index=False)

# ----------------------------------------------------------------------------- P5 flags from the geocode only
def obs_boundary_is_street(d):
    c_idx = locate(LT, d["ox"].to_numpy(), d["oy"].to_numpy())
    out = np.zeros(len(d), bool); m = c_idx >= 0
    P = shapely.points(d["ox"].to_numpy()[m], d["oy"].to_numpy()[m])
    Q = shapely.get_coordinates(shapely.shortest_line(P, LT.bounds[c_idx[m]]))[1::2]
    _, dq, _ = nearest2(Q[:, 0], Q[:, 1])
    out[m] = dq <= TOL
    return out


A["obs_street"] = obs_boundary_is_street(A)
rows = []
for scope, D in [("near-line cohort", A[A["stratum"].astype(str).str.startswith("near")]),
                 ("all scored addresses", A)]:
    w = D["wrong"].to_numpy(); d = D["d_obs"].to_numpy(); nst = ~D["obs_street"].to_numpy()
    flags = {"d_obs < 7 m": d < 7, "non-street line within 50 m (geocode)": nst & (d < 50),
             "either": (d < 7) | (nst & (d < 50))}
    for name, f in flags.items():
        rows.append({"scope": scope, "flag": name, "n": len(D), "flagged_%": 100 * f.mean(),
                     "errors_caught": f"{int(w[f].sum())}/{int(w.sum())}",
                     "risk_answered_%": 100 * (w[~f].mean() if (~f).any() else np.nan)})
    cov = 1 - (nst & (d < 50)).mean()                       # distance flag at the coverage of the street flag
    tau = np.quantile(d, 1 - cov) if cov < 1 else 0.0
    f = d < tau
    rows.append({"scope": scope, "flag": f"d_obs < {tau:.1f} m (matched coverage)", "n": len(D), "flagged_%": 100 * f.mean(),
                 "errors_caught": f"{int(w[f].sum())}/{int(w.sum())}",
                 "risk_answered_%": 100 * (w[~f].mean() if (~f).any() else np.nan)})
    rows.append({"scope": scope, "flag": "none", "n": len(D), "flagged_%": 0.0, "errors_caught": f"0/{int(w.sum())}",
                 "risk_answered_%": 100 * w.mean()})
p5 = pd.DataFrame(rows).round(3); p5.to_csv(f"{RES}/P5_assignment_time_flags.csv", index=False)
rep.table("[P5] Flags computed from the geocode only (information available at assignment time)", p5, index=False)
agree = (A["obs_street"] == A["street_boundary"])[A["stratum"].astype(str).str.startswith("near")].mean()
rep.say(f"[P5b] boundary type from the geocode agrees with boundary type from the reference point for {100*agree:.1f}% "
        f"of near-line addresses")

# ----------------------------------------------------------------------------- P6 placement type
K["placement"] = A.loc[K.index, "placement"].to_numpy()
p6 = tab(K, ["group", "placement"]); p6 = p6[p6["n"] >= 20]
p6.to_csv(f"{RES}/P6_placement.csv", index=False)
rep.table("[P6] Near-line cohort by reference placement type (groups with n >= 20)", p6, index=False)
rep.save()
