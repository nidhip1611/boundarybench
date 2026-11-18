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
  P0b Cohort flow per region: scored, near-line, street / non-street, same / opposite side, wrong.
  P1b Trace of the earlier street-side cohort (d_true < 50 m in ANY stratum) versus the Table 2 cohort (near stratum).
  P5  Screening from the GEOCODE only (src/screening.py): A distance only, B nearest tract line is not a street,
      C distance + boundary type. Same review workload and same risk targets; coverage, risk among answered,
      recall, errors caught, correct addresses withheld; address-level bootstrap CI for C - A.
  P5b Agreement of geocode-based and reference-based boundary type.
  P6  Wrong-tract rate by reference placement type (national NAD 'placement', Utah 'PtLocation').
  P7  Length-preserving direction test: each real displacement re-applied along vs across the street segment
      nearest the reference point (clear segment matches only), vs actual and random-direction rates.
  P8  Held-out geography: rules fitted on five regions, evaluated on the sixth (leave-one-region-out).

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
from src import screening as SC

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
        "same_side", "true_to_road_m", "disp_m", "p_random_dir"]
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

# ----------------------------------------------------------------------------- P1b earlier cohort trace
old = A[A["d_true"] < 50].copy()
old["in_table2"] = old["stratum"].astype(str).str.startswith("near")
p1b = old.groupby(["group", "in_table2"]).agg(n=("wrong", "size"), wrong=("wrong", "sum")).reset_index()
p1b.to_csv(f"{RES}/P1b_old_cohort_trace.csv", index=False)
rep.table("[P1b] Earlier street-side analyses used d_true < 50 m in ANY stratum (near-line sample + random sample points\n"
          "      that happen to lie within 50 m). in_table2=False rows are the extra addresses not in Table 2.", p1b, index=False)
o2 = old.copy(); o2["side"] = np.where(o2["true_to_road_m"] > 60, "no street <= 60 m",
                                       np.where(o2["same_side"], "same side", "opposite side"))
o2["boundary"] = np.where(o2["street_boundary"], "street", "non-street")
rep.table("[P1c] Earlier cohort, pooled (should reproduce the old 27/6,949 same side, 19/84 opposite, 6/264 non-street figures"
          " up to grouping)", o2.groupby(["boundary", "side"])["wrong"].agg(["size", "sum"]).reset_index(), index=False)
rep.say(f"[P1d] earlier cohort total {len(old)} ({int(old['wrong'].sum())} wrong) = Table 2 cohort {int(old['in_table2'].sum())} "
        f"+ {int((~old['in_table2']).sum())} random-stratum addresses; Table 2 near stratum with d_true >= 50 m: "
        f"{int(((A['stratum'].astype(str).str.startswith('near')) & (A['d_true'] >= 50)).sum())}")

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

flow = K.groupby("group").agg(near_line=("wrong", "size"), street=("street_boundary", "sum"),
                              same_side=("side", lambda x: int((x == "same side").sum())),
                              opposite_side=("side", lambda x: int((x == "opposite side").sum())),
                              no_street_60m=("side", lambda x: int((x == "no street <= 60 m").sum())),
                              wrong=("wrong", "sum")).reindex(ORDER)
flow.insert(0, "scored_all_strata", A.groupby("group").size().reindex(ORDER))
flow.insert(3, "non_street", flow["near_line"] - flow["street"])
flow.loc["TOTAL"] = flow.sum()
flow.to_csv(f"{RES}/P0b_cohort_flow.csv")
rep.table("[P0b] Cohort flow (submitted/matched in P0): scored -> near-line -> boundary type -> street side -> wrong", flow)

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
A["nonstreet"] = ~A["obs_street"]
NEARM = A["stratum"].astype(str).str.startswith("near")
agree = (A["obs_street"] == A["street_boundary"])[NEARM]
rep.say(f"[P5b] boundary type from the geocode agrees with boundary type from the reference point for "
        f"{int(agree.sum())}/{len(agree)} = {100*agree.mean():.1f}% of near-line addresses")
xt = pd.crosstab(A.loc[NEARM, "street_boundary"], A.loc[NEARM, "obs_street"], rownames=["ref: street"], colnames=["geocode: street"])
rep.table("[P5b] reference-based (rows) x geocode-based (cols) boundary type, near-line cohort", xt)

p5rows, p5risk, p5ci = [], [], []
for scope, D in [("near-line cohort", A[NEARM]), ("all scored addresses", A)]:
    d, ns, w = D["d_obs"].to_numpy(), D["nonstreet"].to_numpy(), D["wrong"].to_numpy()
    wl7 = (d < 7).mean(); wlB = ns.mean()
    for wl_name, wl in [("= d_obs<7 m", wl7), ("= rule B", wlB), ("10%", .10), ("25%", .25), ("50%", .50)]:
        wC = SC.best_w(d, ns, w, wl)
        for rule, f in [("A distance only", SC.flag_lowest(d, wl)),
                        (f"C distance + boundary type (w={wC:g}, in-sample)", SC.flag_lowest(SC.score_C(d, ns, wC), wl))]:
            p5rows.append({"scope": scope, "workload": wl_name, "rule": rule, **SC.summarize(f, w)})
        lo, med, hi = SC.bootstrap_diff(d, ns, w, wl, wC)
        p5ci.append({"scope": scope, "workload": wl_name, "w": wC, "C_minus_A_caught_median": med,
                     "ci95": f"[{lo:.0f}, {hi:.0f}]"})
    p5rows.append({"scope": scope, "workload": "rule B", "rule": "B non-street boundary only", **SC.summarize(ns, w)})
    p5rows.append({"scope": scope, "workload": "d_obs<7 m", "rule": "A d_obs < 7 m (paper)", **SC.summarize(d < 7, w)})
    p5rows.append({"scope": scope, "workload": "0", "rule": "none (assign all)", **SC.summarize(np.zeros(len(d), bool), w)})
    for tgt in (0.5, 0.25, 0.1):
        wC = SC.best_w(d, ns, w, wl7)
        for rule, sc in [("A distance only", d), (f"C (w={wC:g})", SC.score_C(d, ns, wC))]:
            p5risk.append({"scope": scope, "risk_target_%": tgt, "rule": rule, **SC.coverage_at_risk(sc, w, tgt)})
p5 = pd.DataFrame(p5rows).round(3); p5.to_csv(f"{RES}/P5_screening_matched_workload.csv", index=False)
rep.table("[P5] Screening from the geocode only, same review workload (C's w is chosen in-sample here; P8 is held-out)",
          p5, index=False)
p5c = pd.DataFrame(p5ci).round(2); p5c.to_csv(f"{RES}/P5_bootstrap_C_minus_A.csv", index=False)
rep.table("[P5c] Address-level bootstrap (2,000 reps): extra errors caught by C over A at the same workload", p5c, index=False)
p5r = pd.DataFrame(p5risk).round(3); p5r.to_csv(f"{RES}/P5_matched_risk.csv", index=False)
rep.table("[P5d] Coverage at matched risk targets (answer safest first)", p5r, index=False)

# ----------------------------------------------------------------------------- P6 placement type
K["placement"] = A.loc[K.index, "placement"].to_numpy()
p6 = tab(K, ["group", "placement"]); p6 = p6[p6["n"] >= 20]
p6.to_csv(f"{RES}/P6_placement.csv", index=False)
rep.table("[P6] Near-line cohort by reference placement type (groups with n >= 20)", p6, index=False)
# ----------------------------------------------------------------------------- P7 length-preserving along vs across
tid = locate(LT, tx, ty)
mag = np.hypot(ox - tx, oy - ty)
nvec = np.c_[-tvec[:, 1], tvec[:, 0]]
q = (~K["near_intersection"] & ~K["ambiguous_segment"] & (K["true_to_road_m"] <= 60)).to_numpy() & (tid >= 0)
rates = {}
for name, vec in [("along", tvec), ("across", nvec)]:
    wr = np.zeros(len(K))
    for sgn_ in (1, -1):
        cx, cy = tx + sgn_ * mag * vec[:, 0], ty + sgn_ * mag * vec[:, 1]
        wr += (locate(LT, cx, cy) != tid)
    rates[name] = wr / 2
K["cf_along"], K["cf_across"] = rates["along"], rates["across"]
Q7 = K[q]
rng = np.random.default_rng(7)


def bci(x):
    x = np.asarray(x, float); bs = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(1000)]
    return f"{100*x.mean():.2f} [{100*np.percentile(bs, 2.5):.2f}, {100*np.percentile(bs, 97.5):.2f}]"


rows = []
for g in ORDER + ["ALL"]:
    d = Q7 if g == "ALL" else Q7[Q7["group"] == g]
    n_all = len(K) if g == "ALL" else int((K["group"] == g).sum())
    if len(d) == 0:
        continue
    rows.append({"group": g, "qualifying": len(d), "of_cohort_%": 100 * len(d) / n_all,
                 "actual_wrong_%": bci(d["wrong"]), "along_street_%": bci(d["cf_along"]),
                 "across_street_%": bci(d["cf_across"]), "random_direction_%": bci(d["p_random_dir"])})
p7 = pd.DataFrame(rows).round(2); p7.to_csv(f"{RES}/P7_along_vs_across.csv", index=False)
rep.table("[P7] Same displacement length, re-oriented along vs across the street segment nearest the reference point\n"
          "     (clear segment matches: not within 15 m of a segment end, no second segment within 2 m, reference <= 60 m\n"
          "     from a road). Mean over both signs; 95% address-level bootstrap CI.", p7, index=False)

# ----------------------------------------------------------------------------- P8 held-out geography
p8 = []
for scope, D in [("near-line cohort", A[NEARM]), ("all scored addresses", A)]:
    wl7 = (D["d_obs"] < 7).mean()
    for wl in (wl7, .25, .10):
        h = SC.heldout(D[["group", "d_obs", "nonstreet", "wrong"]], ORDER, wl)
        h.insert(0, "scope", scope); p8.append(h)
p8 = pd.concat(p8).round(3); p8.to_csv(f"{RES}/P8_heldout_regions.csv", index=False)
rep.table("[P8] Held-out regions: thresholds (and w) fitted on the other five regions, applied unchanged", p8, index=False)
pool = (p8.groupby(["scope", "workload_target_%", "rule"])
        .agg(n=("n", "sum"), errors_total=("errors_total", "sum"), errors_caught=("errors_caught", "sum"),
             correct_withheld=("correct_withheld", "sum"), errors_answered=("errors_answered", "sum")).reset_index())
pool["reviewed_%"] = 100 * (pool["errors_caught"] + pool["correct_withheld"]) / pool["n"]
pool["recall_%"] = 100 * pool["errors_caught"] / pool["errors_total"]
pool["risk_answered_%"] = 100 * pool["errors_answered"] / (pool["n"] - pool["errors_caught"] - pool["correct_withheld"])
pool = pool.round(3); pool.to_csv(f"{RES}/P8b_heldout_pooled.csv", index=False)
rep.table("[P8b] Held-out results pooled over the six held-out regions", pool, index=False)
wins = p8[p8["rule"].isin(["C distance + boundary type", "A, same held-out workload as C"])].pivot_table(
    index=["scope", "workload_target_%", "held_out"], columns="rule", values="errors_caught").reset_index()
wins["C_minus_A"] = wins["C distance + boundary type"] - wins["A, same held-out workload as C"]
wins.to_csv(f"{RES}/P8c_heldout_C_vs_A.csv", index=False)
rep.table("[P8c] Held-out errors caught: C vs A at C's held-out review share, per region", wins.round(0), index=False)

rep.save()
