"""EXP21 — Sensitivity checks on the real-data cohort requested by reviewers (saved data only; no new geocoding).

  S1  Address flow per sample and stratum: submitted, Tie, No_Match, matched but excluded (displacement > 500 m or
      reference outside every tract), Utah reference points placed by geocoding, scored. The stratum of an address
      that was not scored is inferred from its sampling block (uids were assigned consecutively per stratum block;
      an excluded uid takes the stratum/group of the scored uids on both sides; 'ambiguous' if they differ).
  S2  Table 2 sensitivity: near-line rates with every excluded near-line Match counted as a wrong tract (worst case).
  S3  Tract returned by the Census geocoder (geographies endpoint, from the matched address range) vs the
      point-in-polygon tract of the returned coordinate, and vs the reference tract.
  S4  18 sampled counties: county-cluster bootstrap CI (real and random-direction rates) vs Wilson.
  S5  Distance bands (d_true): 0-10, 10-25, 25-50 (near-line stratum) and 50-100 m (random stratum only).
  S6  Near-line wrong-tract cases: Census match type, house-number / street mismatch between input and matched address,
      by street-side class.
  S7  Linear-scale and angular distortion of EPSG:2163 at the reference points (distances and rotations were computed
      in EPSG:2163 metres).

    python experiments/exp21_realdata_sensitivity.py
Outputs -> results/v2_realdata_sensitivity/
"""
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd
from pyproj import Proj, Transformer

from src import config as C
from src.geo import load_layers, locate
from src.metrics import wilson
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_realdata_sensitivity")
rep = Report("EXP21 real-data sensitivity: exclusions, Census-returned tract, county clustering, bands, error causes", RES)
pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 400)
ORDER = ["NYC, PLUTO", "NYC, Address Points", "Utah, Salt Lake County", "Utah, six rural counties",
         "National, largest-coverage counties", "National, smaller counties"]


def as_bool(s):
    return s.astype(str).str.lower().isin(["true", "1", "1.0"])


def wci(k, n):
    lo, hi = wilson(int(k), int(n)) if n else (np.nan, np.nan)
    return f"[{100*max(lo, 0):.2f}, {100*hi:.2f}]"


# ----------------------------------------------------------------------------- scored data (all scored, unfiltered)
nyc = pd.read_csv(f"{C.RAW}/nyc/nyc_direction_counterfactual.csv")
nyc["group"] = np.where(nyc["sample"] == "PLUTO", "NYC, PLUTO", "NYC, Address Points")
ut = pd.read_csv(f"{C.RAW}/utah/utah_points.csv")
ut["ref_geocoded"] = ut["PtLocation"].fillna("").str.contains("Geocod", case=False)
ut["group"] = np.where(ut["region"].str.startswith("urban"), "Utah, Salt Lake County", "Utah, six rural counties")
na = pd.read_csv(f"{C.RAW}/nad/national_points.csv")
na["group"] = np.where(na["type"] == "urban", "National, largest-coverage counties", "National, smaller counties")
for d in (nyc, ut, na):
    d["wrong"] = as_bool(d["wrong"])
    d["near"] = d["stratum"].astype(str).str.startswith("near")
nyc["ref_geocoded"] = False; na["ref_geocoded"] = False

SOURCES = [("NYC, PLUTO", f"{C.RAW}/nyc/census_geocoded.csv", nyc[nyc["sample"] == "PLUTO"]),
           ("NYC, Address Points", f"{C.RAW}/nyc/census_geocoded_ap.csv", nyc[nyc["sample"] != "PLUTO"]),
           ("Utah", f"{C.RAW}/utah/census_geocoded.csv", ut),
           ("National", f"{C.RAW}/nad/census_geocoded.csv", na)]

# ----------------------------------------------------------------------------- S1 flow with inferred strata
flow, excl_rows, cg_all = [], [], []
for src, path, sc in SOURCES:
    cg = pd.read_csv(path, dtype=str)
    cg["uid"] = pd.to_numeric(cg["uid"], errors="coerce"); cg = cg.dropna(subset=["uid"]); cg["uid"] = cg["uid"].astype(int)
    cg["source"] = src; cg_all.append(cg)
    ref = sc[["uid", "group", "near"]].drop_duplicates("uid").sort_values("uid")
    ru = ref["uid"].to_numpy(); key = (ref["group"] + "|" + ref["near"].astype(str)).to_numpy()
    scored = set(ru)
    for _, r in cg.iterrows():
        u = r["uid"]
        if u in scored:
            continue
        i = np.searchsorted(ru, u)
        lo = key[i - 1] if i > 0 else None
        hi = key[i] if i < len(ru) else None
        k = lo if hi is None else hi if lo is None else (lo if lo == hi else "ambiguous|ambiguous")
        g, nr = k.split("|")
        status = r["match"] if r["match"] in ("Tie", "No_Match") else "Match, excluded"
        excl_rows.append({"source": src, "uid": u, "group": g, "near": nr, "status": status})
E = pd.DataFrame(excl_rows)
scored_all = pd.concat([d[["group", "near", "ref_geocoded", "wrong", "uid"]] for d in (nyc, ut, na)])
for g in ORDER + ["ambiguous"]:
    for nr in [True, False]:
        e = E[(E["group"] == g) & (E["near"] == str(nr))]
        s = scored_all[(scored_all["group"] == g) & (scored_all["near"] == nr)]
        row = {"group": g, "stratum": "near-line" if nr else "random",
               "Tie": int((e["status"] == "Tie").sum()), "No_Match": int((e["status"] == "No_Match").sum()),
               "Match_excluded": int((e["status"] == "Match, excluded").sum()),
               "ref_geocoded": int(s["ref_geocoded"].sum()), "scored": int((~s["ref_geocoded"]).sum())}
        row["submitted"] = row["Tie"] + row["No_Match"] + row["Match_excluded"] + row["ref_geocoded"] + row["scored"]
        if row["submitted"]:
            flow.append(row)
S1 = pd.DataFrame(flow)[["group", "stratum", "submitted", "Tie", "No_Match", "Match_excluded", "ref_geocoded", "scored"]]
tot = S1.drop(columns=["group"]).groupby("stratum").sum().reset_index().assign(group="TOTAL")
S1 = pd.concat([S1, tot[S1.columns]], ignore_index=True)
S1["scored_%_of_submitted"] = (100 * S1["scored"] / S1["submitted"]).round(1)
S1.to_csv(f"{RES}/S1_flow.csv", index=False)
rep.table("[S1] Address flow by sample and stratum (stratum of unscored addresses inferred from the sampling block)", S1, index=False)

# ----------------------------------------------------------------------------- S2 worst-case Table 2
K = pd.concat([d.loc[d["near"] & ~d["ref_geocoded"], ["group", "wrong", "p_random_dir"]] for d in (nyc, ut, na)])
rows = []
for g in ORDER + ["18 sampled counties", "TOTAL"]:
    gs = ORDER[4:] if g == "18 sampled counties" else ORDER if g == "TOTAL" else [g]
    k = K[K["group"].isin(gs)]
    x = int(((E["group"].isin(gs)) & (E["near"] == "True") & (E["status"] == "Match, excluded")).sum())
    n, w = len(k), int(k["wrong"].sum())
    if n == 0:
        continue
    rows.append({"row": g, "n": n, "wrong": w, "real_%": 100 * w / n, "ci": wci(w, n), "excluded_near_matches": x,
                 "worst_case_%": 100 * (w + x) / (n + x), "worst_ci": wci(w + x, n + x),
                 "random_dir_%": 100 * k["p_random_dir"].mean()})
S2 = pd.DataFrame(rows).round(3); S2.to_csv(f"{RES}/S2_worst_case.csv", index=False)
rep.table("[S2] Near-line rates if every excluded near-line Match (displacement > 500 m or reference outside tracts)\n"
          "     were a wrong tract (worst case), vs random-direction rate", S2, index=False)

# ----------------------------------------------------------------------------- S3 Census-returned tract
LT = load_layers(["tract"])["tract"]
CG = pd.concat(cg_all, ignore_index=True)
CG["census_geoid"] = (CG["st"].fillna("").str.zfill(2) + CG["co"].fillna("").str.zfill(3) + CG["tract"].fillna("").str.zfill(6))
srcmap = {"NYC, PLUTO": "NYC, PLUTO", "NYC, Address Points": "NYC, Address Points",
          "Utah, Salt Lake County": "Utah", "Utah, six rural counties": "Utah",
          "National, largest-coverage counties": "National", "National, smaller counties": "National"}
parts = []
for d in (nyc, ut, na):
    x = d[~d["ref_geocoded"]].copy()
    x["source"] = x["group"].map(srcmap)
    parts.append(x[["source", "group", "uid", "near", "wrong", "tx", "ty", "ox", "oy"]])
A = pd.concat(parts, ignore_index=True)
A = A.merge(CG[["source", "uid", "census_geoid", "match_type", "input", "out_address"]], on=["source", "uid"], how="left")
ids = np.char.zfill(np.asarray(LT.ids).astype(str), 11)
ti, ci_ = locate(LT, A["tx"].to_numpy(), A["ty"].to_numpy()), locate(LT, A["ox"].to_numpy(), A["oy"].to_numpy())
A["ref_geoid"] = np.where(ti >= 0, ids[np.maximum(ti, 0)], "")
A["pip_geoid"] = np.where(ci_ >= 0, ids[np.maximum(ci_, 0)], "")
A["census_eq_pip"] = A["census_geoid"] == A["pip_geoid"]
A["census_wrong"] = A["census_geoid"] != A["ref_geoid"]
A["pip_wrong_check"] = A["pip_geoid"] != A["ref_geoid"]
rep.say(f"[S3a] check: PIP-based wrong flag reproduces the saved flag for {100*(A['pip_wrong_check'] == A['wrong']).mean():.2f}% "
        f"of scored addresses; Census tract code present for {100*(A['census_geoid'].str.len() == 11).mean():.1f}%")
rows = []
for scope, D in [("near-line", A[A["near"]]), ("all scored", A)]:
    for g in ORDER + ["ALL"]:
        d = D if g == "ALL" else D[D["group"] == g]
        rows.append({"scope": scope, "group": g, "n": len(d), "census_tract_eq_PIP_%": 100 * d["census_eq_pip"].mean(),
                     "disagree_n": int((~d["census_eq_pip"]).sum()),
                     "PIP_wrong": int(d["wrong"].sum()), "census_tract_wrong": int(d["census_wrong"].sum()),
                     "census_wrong_%": 100 * d["census_wrong"].mean(), "census_ci": wci(d["census_wrong"].sum(), len(d))})
S3 = pd.DataFrame(rows).round(3); S3.to_csv(f"{RES}/S3_census_tract.csv", index=False)
rep.table("[S3] Tract returned by the Census geocoder vs point-in-polygon tract of its coordinate, and wrong-tract counts\n"
          "     for each (reference = tract of the reference point)", S3, index=False)
both = A[A["near"]]
rep.table("[S3b] near-line: PIP wrong (rows) x Census-returned tract wrong (cols)",
          pd.crosstab(both["wrong"], both["census_wrong"], rownames=["PIP wrong"], colnames=["Census tract wrong"]))

# ----------------------------------------------------------------------------- S4 county cluster bootstrap
nn = na[na["near"]].copy()
rng = np.random.default_rng(21)
cs = nn["cty"].unique()
real_b, rand_b = [], []
by = {c: nn[nn["cty"] == c] for c in cs}
for _ in range(5000):
    pick = rng.choice(cs, len(cs))
    d = pd.concat([by[c] for c in pick])
    real_b.append(100 * d["wrong"].mean()); rand_b.append(100 * d["p_random_dir"].mean())
S4 = pd.DataFrame([{"row": "18 sampled counties, near-line", "n": len(nn), "counties": len(cs),
                    "real_%": 100 * nn["wrong"].mean(), "wilson_ci": wci(nn["wrong"].sum(), len(nn)),
                    "county_cluster_ci": f"[{np.percentile(real_b, 2.5):.2f}, {np.percentile(real_b, 97.5):.2f}]",
                    "random_dir_%": 100 * nn["p_random_dir"].mean(),
                    "random_cluster_ci": f"[{np.percentile(rand_b, 2.5):.2f}, {np.percentile(rand_b, 97.5):.2f}]"}]).round(3)
S4.to_csv(f"{RES}/S4_county_cluster.csv", index=False)
rep.table("[S4] 18 sampled counties: county-cluster bootstrap (5,000 reps) vs Wilson", S4, index=False)
pc = nn.groupby("cty").agg(n=("wrong", "size"), wrong=("wrong", "sum"), random_dir=("p_random_dir", "mean")).reset_index()
pc.to_csv(f"{RES}/S4b_per_county.csv", index=False)
rep.say(f"[S4b] per-county near-line real rate: min {100*(pc['wrong']/pc['n']).min():.2f}%, max {100*(pc['wrong']/pc['n']).max():.2f}%; "
        f"real < random-direction in {int(((pc['wrong']/pc['n']) < pc['random_dir']).sum())}/{len(pc)} counties")

# ----------------------------------------------------------------------------- S5 distance bands
B = pd.concat([d.loc[~d["ref_geocoded"], ["group", "near", "wrong", "d_true", "p_random_dir"]] for d in (nyc, ut, na)])
B["band"] = pd.cut(B["d_true"], [0, 10, 25, 50, 100, np.inf], right=False, labels=["0-10", "10-25", "25-50", "50-100", ">=100"])
rows = []
for (band, nr), d in B.groupby(["band", "near"], observed=True):
    rows.append({"d_true_band_m": band, "stratum": "near-line" if nr else "random", "n": len(d), "wrong": int(d["wrong"].sum()),
                 "real_%": 100 * d["wrong"].mean(), "ci": wci(d["wrong"].sum(), len(d)), "random_dir_%": 100 * d["p_random_dir"].mean()})
S5 = pd.DataFrame(rows).round(3); S5.to_csv(f"{RES}/S5_bands.csv", index=False)
rep.table("[S5] Real vs random-direction rate by true boundary distance (near-line stratum < 50 m by design)", S5, index=False)
for lim in (25, 50, 100):
    d = B[B["d_true"] < lim]
    rep.say(f"[S5b] all scored with d_true < {lim} m: n={len(d)}, real {100*d['wrong'].mean():.2f}% {wci(d['wrong'].sum(), len(d))}, "
            f"random-direction {100*d['p_random_dir'].mean():.2f}%")

# ----------------------------------------------------------------------------- S6 causes of near-line errors
NL = pd.concat([d.loc[d["near"] & ~d["ref_geocoded"], ["group", "uid", "wrong", "same_side", "true_to_road_m"]]
                .assign(source=lambda x: x["group"].map(srcmap)) for d in (nyc, ut, na)])
NL["same_side"] = as_bool(NL["same_side"])
NL["side"] = np.where(NL["true_to_road_m"] > 60, "no street <= 60 m", np.where(NL["same_side"], "same side", "opposite side"))
W = NL[NL["wrong"]].merge(CG[["source", "uid", "match_type", "input", "out_address"]], on=["source", "uid"], how="left")


def hn(s):
    m = re.match(r"\s*(\d+)", str(s)); return m.group(1) if m else ""


def street(s):
    s = str(s).upper().split(",")[0]; s = re.sub(r"^\s*\d+[A-Z]?\s+", "", s); return re.sub(r"\s+", " ", s).strip()


W["hn_differs"] = [hn(a) != hn(b) for a, b in zip(W["input"], W["out_address"])]
W["street_differs"] = [street(a) != street(b) for a, b in zip(W["input"], W["out_address"])]
W["non_exact"] = W["match_type"].astype(str).str.lower().str.startswith("non")
S6 = W.groupby("side").agg(n=("wrong", "size"), non_exact=("non_exact", "sum"), house_number_differs=("hn_differs", "sum"),
                           street_text_differs=("street_differs", "sum")).reset_index()
S6.to_csv(f"{RES}/S6_error_causes.csv", index=False)
W[["group", "uid", "side", "match_type", "input", "out_address"]].to_csv(f"{RES}/S6b_error_cases.csv", index=False)
rep.table("[S6] Near-line wrong-tract cases by street side: Census match type and input vs matched address\n"
          "     (street_text_differs is a raw text comparison and also flags abbreviations; see S6b for each case)", S6, index=False)
allnl = NL.merge(CG[["source", "uid", "match_type"]], on=["source", "uid"], how="left")
allnl["non_exact"] = allnl["match_type"].astype(str).str.lower().str.startswith("non")
rep.say(f"[S6c] near-line Non_Exact share: {100*allnl['non_exact'].mean():.2f}% overall; wrong-tract rate "
        f"{100*allnl.loc[allnl['non_exact'], 'wrong'].mean():.2f}% (n={int(allnl['non_exact'].sum())}) vs "
        f"{100*allnl.loc[~allnl['non_exact'], 'wrong'].mean():.2f}% for Exact")

# ----------------------------------------------------------------------------- S7 projection distortion
tr = Transformer.from_crs(C.CRS_M, 4326, always_xy=True)
lon, lat = tr.transform(A["tx"].to_numpy(), A["ty"].to_numpy())
f = Proj(f"EPSG:{C.CRS_M}").get_factors(lon, lat)
A["scale_err_%"] = 100 * np.maximum(np.abs(np.asarray(f.meridional_scale) - 1), np.abs(np.asarray(f.parallel_scale) - 1))
A["angular_dist_deg"] = np.asarray(f.angular_distortion)
S7 = A.groupby("group").agg(median_scale_err_pct=("scale_err_%", "median"), max_scale_err_pct=("scale_err_%", "max"),
                            max_angular_distortion_deg=("angular_dist_deg", "max")).reindex(ORDER).round(3)
S7.to_csv(f"{RES}/S7_projection.csv")
rep.table("[S7] EPSG:2163 linear-scale error (max of meridional/parallel, %) and angular distortion at reference points", S7)

rep.save()
