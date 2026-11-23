"""EXP23 — Finer geography, policy impact and match-quality flags for the real Census geocodes (saved geocodes only).

  B1  Block group and block: wrong-unit rate of the Census-returned block / block group vs the reference point's unit
      (TIGER/Line 2025 TABBLOCK20, downloaded per state), observed vs the same displacement lengths in random
      directions (M = 50), and on/off the matched block face (EXP22).
  Q1  Policy impact: HUD 2026 Qualified Census Tracts (LIHTC). For every wrong-tract address, does QCT status differ
      between the reference tract and the geocoded tract?  How many near-line addresses sit next to a tract with a
      different QCT status?
  F1  Match-quality anatomy: which part of the matched address differs from the input (house number, directional,
      street name/type, ZIP, city only, none) and the wrong-tract rate of each; deployable flags compared at equal
      workload with boundary distance.
  F2  Non_Exact by region and Mantel-Haenszel odds ratio stratified by region.

    python experiments/exp23_blocks_policy_flags.py
Outputs -> results/v2_blocks_policy/      Downloads -> $BB_WORK/outputs/blocks/, outputs/qct/
"""
import io
import json
import os
import re
import sys
import time
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from scipy.stats import chi2

from src import config as C
from src.metrics import wilson
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_blocks_policy")
BLK = C.out_dir(C.RAW, "blocks")
QDIR = C.out_dir(C.RAW, "qct")
rep = Report("EXP23 blocks/block groups, HUD QCT impact, match-quality flags", RES)
pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 300)
ORDER = ["NYC, PLUTO", "NYC, Address Points", "Utah, Salt Lake County", "Utah, six rural counties",
         "National, largest-coverage counties", "National, smaller counties"]
rng = np.random.default_rng(23)


def as_bool(s):
    return s.astype(str).str.lower().isin(["true", "1", "1.0"])


def wci(k, n):
    lo, hi = wilson(int(k), int(n)) if n else (np.nan, np.nan)
    return f"[{100*max(lo, 0):.2f}, {100*hi:.2f}]"


def get(url, path, tries=3):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return True
    for a in range(tries):
        try:
            r = requests.get(url, timeout=900); r.raise_for_status()
            open(path, "wb").write(r.content); return True
        except Exception as e:
            print(f"download {url} attempt {a+1}: {e}"); time.sleep(10)
    return False


# ----------------------------------------------------------------------------- scored addresses + Census output
nyc = pd.read_csv(f"{C.RAW}/nyc/nyc_direction_counterfactual.csv")
nyc["group"] = np.where(nyc["sample"] == "PLUTO", "NYC, PLUTO", "NYC, Address Points"); nyc["source"] = nyc["group"]
ut = pd.read_csv(f"{C.RAW}/utah/utah_points.csv")
ut = ut[~ut["PtLocation"].fillna("").str.contains("Geocod", case=False)].copy()
ut["group"] = np.where(ut["region"].str.startswith("urban"), "Utah, Salt Lake County", "Utah, six rural counties"); ut["source"] = "Utah"
na = pd.read_csv(f"{C.RAW}/nad/national_points.csv")
na["group"] = np.where(na["type"] == "urban", "National, largest-coverage counties", "National, smaller counties"); na["source"] = "National"
cols = ["source", "group", "uid", "stratum", "wrong", "tx", "ty", "ox", "oy", "d_obs"]
A = pd.concat([d[[c for c in cols if c in d.columns]] for d in (nyc, ut, na)], ignore_index=True)
A["wrong"] = as_bool(A["wrong"]); A["near"] = A["stratum"].astype(str).str.startswith("near")
cg = []
for src, path in [("NYC, PLUTO", f"{C.RAW}/nyc/census_geocoded.csv"), ("NYC, Address Points", f"{C.RAW}/nyc/census_geocoded_ap.csv"),
                  ("Utah", f"{C.RAW}/utah/census_geocoded.csv"), ("National", f"{C.RAW}/nad/census_geocoded.csv")]:
    d = pd.read_csv(path, dtype=str); d["source"] = src
    d["uid"] = pd.to_numeric(d["uid"], errors="coerce"); d = d.dropna(subset=["uid"]); d["uid"] = d["uid"].astype(int)
    cg.append(d[d["match"] == "Match"])
CG = pd.concat(cg, ignore_index=True)
A = A.merge(CG[["source", "uid", "match_type", "input", "out_address", "st", "co", "tract", "block"]], on=["source", "uid"], how="left")
A["st"] = A["st"].fillna("").str.zfill(2); A["co"] = A["co"].fillna("").str.zfill(3)
A["geo_block"] = A["st"] + A["co"] + A["tract"].fillna("").str.zfill(6) + A["block"].fillna("").str.zfill(4)
A["geo_tract"] = A["geo_block"].str[:11]; A["geo_bg"] = A["geo_block"].str[:12]
me = pd.read_csv(f"{C.RESULTS}/v2_matched_edge/M_points.csv", usecols=["source", "uid", "ref_within_face", "ref_on_reported_side"])
A = A.merge(me, on=["source", "uid"], how="left")
A["face"] = np.where(A["ref_within_face"].isna(), "no matched edge",
                     np.where(as_bool(A["ref_within_face"]) & as_bool(A["ref_on_reported_side"]), "on matched face", "off matched face"))
if "d_obs" not in A.columns or A["d_obs"].isna().all():
    A["d_obs"] = np.nan
rep.say(f"[B0] scored addresses: {len(A)} (near-line {int(A['near'].sum())}); Census block code present for "
        f"{100*(A['geo_block'].str.len() == 15).mean():.1f}%")

# ----------------------------------------------------------------------------- B1 blocks
states = sorted(s for s in A["st"].unique() if len(s) == 2 and s != "00")
counties = set(A["st"] + A["co"])
parts = []
for s in states:
    z = f"{BLK}/tl_2025_{s}_tabblock20.zip"
    ok = get(f"https://www2.census.gov/geo/tiger/TIGER2025/TABBLOCK20/tl_2025_{s}_tabblock20.zip", z)
    if not ok:
        z = f"{BLK}/tl_2024_{s}_tabblock20.zip"
        ok = get(f"https://www2.census.gov/geo/tiger/TIGER2024/TABBLOCK20/tl_2024_{s}_tabblock20.zip", z)
    if not ok:
        print(f"no block file for state {s}"); continue
    g = gpd.read_file(f"zip://{z}")
    gcol = "GEOID20" if "GEOID20" in g.columns else "GEOID"
    g = g[(g[gcol].str[:5]).isin(counties)][[gcol, "geometry"]].rename(columns={gcol: "GEOID"})
    parts.append(g.to_crs(C.CRS_M))
    print(f"blocks state {s}: {len(g)} kept")
B = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=parts[0].crs)
rep.say(f"[B0] block polygons loaded: {len(B):,} in {len(parts)} states")
sidx = B.sindex


def block_of(x, y):
    pts = gpd.GeoSeries(gpd.points_from_xy(x, y), crs=B.crs)
    hit = sidx.query(pts, predicate="within")                      # (point_idx, block_idx)
    out = np.full(len(x), "", dtype=object)
    out[hit[0]] = B["GEOID"].to_numpy()[hit[1]]
    return out


A["ref_block"] = block_of(A["tx"].to_numpy(), A["ty"].to_numpy())
A["pip_block"] = block_of(A["ox"].to_numpy(), A["oy"].to_numpy())
ok = (A["ref_block"].str.len() == 15) & (A["geo_block"].str.len() == 15)
rep.say(f"[B0] reference block found for {100*(A['ref_block'].str.len() == 15).mean():.2f}%; Census block = PIP block for "
        f"{100*(A.loc[ok, 'geo_block'] == A.loc[ok, 'pip_block']).mean():.2f}%; tract check: ref-block tract != geocode "
        f"tract reproduces 'wrong' for {100*((A.loc[ok, 'ref_block'].str[:11] != A.loc[ok, 'geo_tract']) == A.loc[ok, 'wrong']).mean():.2f}%")
A = A[ok].copy()
A["wrong_tract"] = A["ref_block"].str[:11] != A["geo_tract"]
A["wrong_bg"] = A["ref_block"].str[:12] != A["geo_bg"]
A["wrong_block"] = A["ref_block"] != A["geo_block"]
# random-direction counterfactual (M = 50) for near-line addresses
K = A[A["near"]].copy()
L = np.hypot(K["ox"] - K["tx"], K["oy"] - K["ty"]).to_numpy()
cf = {"tract": np.zeros(len(K)), "bg": np.zeros(len(K)), "block": np.zeros(len(K))}
rb = K["ref_block"].to_numpy().astype(str)
for _ in range(50):
    a = rng.uniform(0, 2 * np.pi, len(K))
    b = block_of(K["tx"].to_numpy() + L * np.cos(a), K["ty"].to_numpy() + L * np.sin(a)).astype(str)
    cf["tract"] += np.array([x[:11] != y[:11] for x, y in zip(b, rb)])
    cf["bg"] += np.array([x[:12] != y[:12] for x, y in zip(b, rb)])
    cf["block"] += (b != rb)
for k in cf:
    K[f"rand_{k}"] = cf[k] / 50
rows = []
for scope, D in [("near-line", K), ("all scored", A)]:
    for g in ORDER + ["ALL"]:
        d = D if g == "ALL" else D[D["group"] == g]
        r = {"scope": scope, "group": g, "n": len(d)}
        for u in ["tract", "bg", "block"]:
            k = int(d[f"wrong_{u}"].sum()); r[f"{u}_%"] = 100 * k / len(d); r[f"{u}_ci"] = wci(k, len(d))
            if scope == "near-line":
                r[f"{u}_random_%"] = 100 * d[f"rand_{u}"].mean()
        rows.append(r)
B1 = pd.DataFrame(rows).round(3); B1.to_csv(f"{RES}/B1_units.csv", index=False)
rep.table("[B1] Wrong tract / block group / block (Census-returned unit vs reference point's unit); near-line rows also\n"
          "     show the same displacement lengths in random directions (M = 50)", B1, index=False)
rows = []
for f, d in A[A["near"]].groupby("face"):
    rows.append({"face": f, "n": len(d), **{f"wrong_{u}": int(d[f"wrong_{u}"].sum()) for u in ["tract", "bg", "block"]},
                 "block_%": 100 * d["wrong_block"].mean(), "block_ci": wci(d["wrong_block"].sum(), len(d))})
B2 = pd.DataFrame(rows).round(3); B2.to_csv(f"{RES}/B2_face_units.csv", index=False)
rep.table("[B2] Near-line: wrong unit counts on vs off the matched block face (EXP22)", B2, index=False)

# ----------------------------------------------------------------------------- Q1 HUD 2026 QCT
qct = None
url = ("https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/QUALIFIED_CENSUS_TRACTS_2026/FeatureServer/0/query")
qpath = f"{QDIR}/qct2026_geoids.csv"
if os.path.exists(qpath):
    qct = set(pd.read_csv(qpath, dtype=str)["GEOID"])
else:
    try:
        ids, off = [], 0
        while True:
            r = requests.get(url, params={"where": "1=1", "outFields": "*", "returnGeometry": "false", "f": "json",
                                          "resultOffset": off, "resultRecordCount": 2000}, timeout=300).json()
            feats = r.get("features", [])
            if not feats:
                break
            for f in feats:
                at = f["attributes"]
                g = next((str(v) for k, v in at.items() if isinstance(v, str) and re.fullmatch(r"\d{11}", str(v))), None)
                if g is None:
                    g = next((str(int(v)).zfill(11) for k, v in at.items() if k.upper() in ("GEOID", "GEOID20", "TRACT_ID", "FIPS")
                              and v is not None), None)
                if g:
                    ids.append(g)
            off += len(feats)
            if not r.get("exceededTransferLimit", False) and len(feats) < 2000:
                break
        qct = set(ids)
        pd.DataFrame({"GEOID": sorted(qct)}).to_csv(qpath, index=False)
    except Exception as e:
        print(f"QCT download failed: {e}")
if qct:
    rep.say(f"[Q0] HUD 2026 QCT list: {len(qct):,} tracts (source: HUD ArcGIS FeatureServer QUALIFIED_CENSUS_TRACTS_2026)")
    W = A[A["wrong_tract"]].copy()
    W["qct_ref"] = W["ref_block"].str[:11].isin(qct); W["qct_geo"] = W["geo_tract"].isin(qct)
    W["flip"] = W["qct_ref"] != W["qct_geo"]
    q = W.groupby("near").agg(wrong_tract=("flip", "size"), qct_status_flips=("flip", "sum"),
                              ref_qct=("qct_ref", "sum"), geo_qct=("qct_geo", "sum")).reset_index()
    q.to_csv(f"{RES}/Q1_qct_flips.csv", index=False)
    rep.table("[Q1] Wrong-tract addresses whose HUD 2026 QCT status flips (reference tract vs geocoded tract)", q, index=False)
    W[["group", "uid", "near", "ref_block", "geo_tract", "qct_ref", "qct_geo", "flip"]].to_csv(f"{RES}/Q1b_cases.csv", index=False)
    nl = A[A["near"]]
    rep.say(f"[Q2] near-line addresses whose reference tract is a QCT: {int(nl['ref_block'].str[:11].isin(qct).sum())}/{len(nl)}; "
            f"all scored: {int(A['ref_block'].str[:11].isin(qct).sum())}/{len(A)}")
else:
    rep.say("[Q0] QCT list unavailable; Q1 skipped")

# ----------------------------------------------------------------------------- F1 match-quality anatomy
DIRS = {"N": "N", "S": "S", "E": "E", "W": "W", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W", "NE": "NE", "NW": "NW",
        "SE": "SE", "SW": "SW", "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW"}
TYPES = {"STREET": "ST", "ST": "ST", "AVENUE": "AVE", "AVE": "AVE", "AV": "AVE", "ROAD": "RD", "RD": "RD", "LANE": "LN",
         "LN": "LN", "DRIVE": "DR", "DR": "DR", "PLACE": "PL", "PL": "PL", "BOULEVARD": "BLVD", "BLVD": "BLVD",
         "HIGHWAY": "HWY", "HWY": "HWY", "SQUARE": "SQ", "SQ": "SQ", "CIRCLE": "CIR", "CIR": "CIR", "COURT": "CT", "CT": "CT",
         "TERRACE": "TER", "TER": "TER", "PARKWAY": "PKWY", "PKWY": "PKWY", "WAY": "WAY", "TRAIL": "TRL", "TRL": "TRL",
         "US": "", "STATE": "", "RTE": "HWY", "ROUTE": "HWY", "SR": "HWY"}


def parse(a):
    parts = [p.strip() for p in str(a).upper().split(",")]
    street = parts[0] if parts else ""; city = parts[1] if len(parts) > 1 else ""; z = parts[-1][:5] if len(parts) > 3 else ""
    tok = street.replace(".", " ").split()
    hn = tok[0] if tok and re.match(r"^\d", tok[0]) else ""
    rest = tok[1:] if hn else tok
    dirs = [DIRS[t] for t in rest if t in DIRS]
    core = []
    for t in rest:
        if t in DIRS:
            continue
        t = TYPES.get(t, t)
        t = re.sub(r"^(\d+)(ST|ND|RD|TH)$", r"\1", t)
        if t:
            core.append(t)
    return hn, dirs, " ".join(core), z, city


def category(i, o):
    hi, di, ci, zi, cti = parse(i); ho, do, co_, zo, cto = parse(o)
    if hi != ho:
        return "house number differs"
    if di != do:
        return "directional differs"
    if ci != co_:
        return "street name/type differs"
    if zi and zo and zi != zo:
        return "ZIP differs"
    if cti != cto:
        return "city name only"
    return "no difference"


NL = A[A["near"]].copy()
NL["diff"] = [category(i, o) for i, o in zip(NL["input"], NL["out_address"])]
NL["non_exact"] = NL["match_type"].astype(str).str.lower().str.startswith("non")
F1 = NL.groupby(["non_exact", "diff"]).agg(n=("wrong_tract", "size"), wrong=("wrong_tract", "sum")).reset_index()
F1["wrong_%"] = 100 * F1["wrong"] / F1["n"]; F1["ci"] = [wci(k, n) for k, n in zip(F1["wrong"], F1["n"])]
F1 = F1.round(3); F1.to_csv(f"{RES}/F1_match_anatomy.csv", index=False)
rep.table("[F1] Near-line: which part of the matched address differs from the input, by match type; wrong-tract rate", F1, index=False)
NL[NL["wrong_tract"]][["group", "uid", "match_type", "diff", "input", "out_address"]].to_csv(f"{RES}/F1b_error_cases.csv", index=False)

flags = {"Non_Exact": NL["non_exact"].to_numpy(),
         "house no./directional/street differs": NL["diff"].isin(["house number differs", "directional differs",
                                                                  "street name/type differs"]).to_numpy(),
         "house no./directional differs": NL["diff"].isin(["house number differs", "directional differs"]).to_numpy()}
wv = NL["wrong_tract"].to_numpy(); dob = NL["d_obs"].to_numpy() if NL["d_obs"].notna().all() else None
rows = []
for name, f in flags.items():
    r = {"flag": name, "reviewed_%": 100 * f.mean(), "caught": int(wv[f].sum()), "of": int(wv.sum()),
         "risk_answered_%": 100 * wv[~f].mean()}
    if dob is not None:
        k = int(round(f.mean() * len(f))); fl = np.zeros(len(f), bool); fl[np.argsort(dob, kind="stable")[:k]] = True
        r["distance_same_workload_caught"] = int(wv[fl].sum()); r["distance_risk_answered_%"] = 100 * wv[~fl].mean()
    rows.append(r)
F1c = pd.DataFrame(rows).round(3); F1c.to_csv(f"{RES}/F1c_flags.csv", index=False)
rep.table("[F1c] Assignment-time flags from the geocoder's own output vs boundary distance at the same workload", F1c, index=False)
rows = []
for g in ORDER:
    d = NL[NL["group"] == g]
    for name, f in flags.items():
        ff = f[NL["group"].to_numpy() == g]
        rows.append({"group": g, "flag": name, "n": len(d), "reviewed_%": 100 * ff.mean(), "caught": int(d["wrong_tract"].to_numpy()[ff].sum()),
                     "errors": int(d["wrong_tract"].sum())})
F1d = pd.DataFrame(rows).round(2); F1d.to_csv(f"{RES}/F1d_flags_by_region.csv", index=False)
rep.table("[F1d] Flags by region (near-line)", F1d, index=False)

# ----------------------------------------------------------------------------- F2 Mantel-Haenszel for Non_Exact
num = den = 0.0; a_sum = e_sum = v_sum = 0.0; rows = []
for g in ORDER:
    d = NL[NL["group"] == g]
    a = int((d["non_exact"] & d["wrong_tract"]).sum()); b = int((d["non_exact"] & ~d["wrong_tract"]).sum())
    c = int((~d["non_exact"] & d["wrong_tract"]).sum()); dd = int((~d["non_exact"] & ~d["wrong_tract"]).sum()); n = a + b + c + dd
    rows.append({"group": g, "nonexact_wrong": a, "nonexact_n": a + b, "exact_wrong": c, "exact_n": c + dd})
    if n:
        num += a * dd / n; den += b * c / n
        m1, n1, m0 = a + c, a + b, b + dd
        e_sum += n1 * m1 / n; v_sum += (n1 * (c + dd) * m1 * m0) / (n * n * (n - 1)) if n > 1 else 0; a_sum += a
mh_or = num / den if den else np.inf
cmh = (abs(a_sum - e_sum) - 0.5) ** 2 / v_sum if v_sum else np.nan
F2 = pd.DataFrame(rows); F2.to_csv(f"{RES}/F2_nonexact_by_region.csv", index=False)
rep.table("[F2] Non_Exact vs Exact by region (near-line)", F2, index=False)
rep.say(f"[F2b] Mantel-Haenszel OR stratified by region = {mh_or:.2f}; CMH chi2 = {cmh:.2f}, p = {chi2.sf(cmh, 1):.4f}")

rep.save()
