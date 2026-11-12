"""EXP16 — National real-world transfer across all 9 Census divisions (USDOT National Address Database).

Ground truth: USDOT National Address Database (NAD; authoritative state/local/tribal address points).
Design (no hand-picking): for each of the 9 Census divisions present in the NAD,
  URBAN county = county with the most NAD address points
  RURAL county = random county (fixed seed) with 2,000–30,000 NAD address points
Per county: up to 100 addresses within 50 m of a tract line + 100 random; Census batch geocoded.
Excluded: points with a unit/sub-address, non-numeric house numbers, and placements that are themselves geocodes
(Placement containing "Linear", "Geocod", "Unknown"). Same measurements as NYC (EXP09/11) and Utah (EXP15).

The NAD text file (TXT.zip, several GB) must be downloaded once from
https://data.transportation.gov/dataset/National-Address-Database-NAD-Text-File/fc2s-wawr
and saved as $BB_WORK/outputs/nad/NAD_TXT.zip (or set NAD_ZIP=/path/to/zip).

    python experiments/exp16_national_transfer.py
Raw -> $BB_WORK/outputs/nad/   Tables, summary -> results/v2_national/
"""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely

from src import config as C
from src.geo import load_layers, locate, dist_to_own_boundary
from src.metrics import wilson
from src.nycdata import census_batch
from src.report import Report
from src.uncertainty import p_straight_empirical

RAW = C.out_dir(C.RAW, "nad")
RES = C.out_dir(C.RESULTS, "v2_national")
rep = Report("EXP16 national transfer across 9 Census divisions (NAD + Census geocoder)", RES)
pd.set_option("display.width", 260, "display.max_columns", 40, "display.max_rows", 200)
NAD_ZIP = os.environ.get("NAD_ZIP", f"{RAW}/NAD_TXT.zip")
KEEP_PER_COUNTY, PER_STRATUM, M, STREET_TOL = 800, 100, 200, 1.5
rng = np.random.default_rng(1616)

DIVISION = {}
for div, states in {
    "New England": "CT ME MA NH RI VT", "Middle Atlantic": "NJ NY PA",
    "East North Central": "IL IN MI OH WI", "West North Central": "IA KS MN MO NE ND SD",
    "South Atlantic": "DE DC FL GA MD NC SC VA WV", "East South Central": "AL KY MS TN",
    "West South Central": "AR LA OK TX", "Mountain": "AZ CO ID MT NV NM UT WY", "Pacific": "AK CA HI OR WA"}.items():
    for s in states.split():
        DIVISION[s] = div

# ----------------------------------------------------------------------------- 1. stream the NAD once
@contextlib.contextmanager
def open_member(zip_path, member):
    """Binary stream of one zip member, nothing written to disk. The official NAD zip is Zip64 + Deflate64:
    stdlib zipfile can't decompress Deflate64 and macOS `unzip` 6.00 can't read the >4 GB Zip64 directory.
    Order: (1) zipfile-deflate64 (pip; patches stdlib zipfile), (2) 7-Zip CLI (brew install sevenzip -> 7zz),
    (3) stdlib zipfile, (4) unzip."""
    try:
        import zipfile_deflate64 as zd  # noqa: F401  (import patches zipfile with Deflate64 support)
        with zd.ZipFile(zip_path).open(member) as fh:
            yield fh
        return
    except ImportError:
        pass
    for exe in ["7zz", "7z", "7za"]:
        if shutil.which(exe):
            proc = subprocess.Popen([exe, "e", "-so", "-bd", zip_path, member], stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, bufsize=1 << 24)
            try:
                yield proc.stdout
            finally:
                proc.stdout.close()
                proc.kill()
                proc.wait()
            return
    try:
        with zipfile.ZipFile(zip_path).open(member) as fh:
            yield fh
        return
    except NotImplementedError:
        pass
    if shutil.which("unzip"):
        proc = subprocess.Popen(["unzip", "-p", zip_path, member], stdout=subprocess.PIPE, bufsize=1 << 24)
        try:
            yield proc.stdout
        finally:
            proc.stdout.close()
            proc.kill()
            proc.wait()
        return
    raise RuntimeError("NAD zip is Zip64+Deflate64: `pip install zipfile-deflate64` or `brew install sevenzip`")


cand_path = f"{RAW}/candidates.parquet"
if not os.path.exists(cand_path):
    assert os.path.exists(NAD_ZIP), f"Download the NAD text file to {NAD_ZIP} first (see docstring)"
    zf = zipfile.ZipFile(NAD_ZIP)
    member = max(zf.namelist(), key=lambda n: zf.getinfo(n).file_size)
    print("reading", member, f"{zf.getinfo(member).file_size / 1e9:.1f} GB")
    with open_member(NAD_ZIP, member) as fh:
        first = io.TextIOWrapper(fh, encoding="utf-8", errors="replace").readline()
    SEP = max([",", "|", "\t"], key=first.count)
    header = [h.strip().strip('"') for h in first.rstrip("\n").split(SEP)]
    print("delimiter:", repr(SEP), "| columns:", header)
    cols = {c.lower(): c for c in header}
    need = {k: cols.get(k) for k in ["add_number", "state", "county", "zip_code", "post_city", "longitude", "latitude",
                                     "placement", "stnam_full", "subaddress", "unit", "st_predir", "st_premod",
                                     "st_pretyp", "st_name", "st_postyp", "st_posdir", "addnum_suf"]}
    missing = [k for k in ["add_number", "state", "county", "longitude", "latitude"] if not need[k]]
    if missing:
        raise KeyError(f"NAD columns not found: {missing}. Header: {header}")
    usecols = [v for v in need.values() if v]
    kept, counts = None, {}
    with open_member(NAD_ZIP, member) as fh:
        reader = pd.read_csv(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"), sep=SEP, usecols=usecols,
                             dtype=str, chunksize=2_000_000)
        for i, ch in enumerate(reader):
            ch.columns = [c.lower() for c in ch.columns]
            ch = ch[ch["add_number"].fillna("").str.fullmatch(r"\d+")]
            for sub in ["subaddress", "unit"]:
                if sub in ch:
                    ch = ch[ch[sub].isna() | (ch[sub].str.strip() == "")]
            if "placement" in ch:
                ch = ch[~ch["placement"].fillna("Unknown").str.contains("Linear|Geocod|Unknown", case=False)]
            ch["state"] = ch["state"].str.strip().str.upper()
            ch = ch[ch["state"].isin(DIVISION)]
            ch["cty"] = ch["state"] + "|" + ch["county"].fillna("").str.strip()
            vc = ch["cty"].value_counts()
            for k, v in vc.items():
                counts[k] = counts.get(k, 0) + int(v)
            ch["u"] = rng.uniform(size=len(ch))
            kept = ch if kept is None else pd.concat([kept, ch], ignore_index=True)
            kept = kept.sort_values("u").groupby("cty", sort=False).head(KEEP_PER_COUNTY)
            print(f"chunk {i}: kept {len(kept):,} rows from {len(counts):,} counties")
    if "stnam_full" not in kept or kept["stnam_full"].isna().all():
        parts = [c for c in ["st_premod", "st_predir", "st_pretyp", "st_name", "st_postyp", "st_posdir"] if c in kept]
        kept["stnam_full"] = kept[parts].fillna("").agg(" ".join, axis=1).str.split().str.join(" ")
    kept["n_county"] = kept["cty"].map(counts)
    kept["division"] = kept["state"].map(DIVISION)
    kept.to_parquet(cand_path, index=False)
    pd.Series(counts).rename("n").to_csv(f"{RAW}/county_counts.csv")
K = pd.read_parquet(cand_path)

# ----------------------------------------------------------------------------- 2. choose urban + rural county per division
cc = K.drop_duplicates("cty")[["cty", "state", "division", "n_county"]]
picks = []
for div, d in cc.groupby("division"):
    urban = d.sort_values("n_county", ascending=False).iloc[0]
    rural_pool = d[(d["n_county"] >= 2000) & (d["n_county"] <= 30000) & (d["cty"] != urban["cty"])]
    picks.append((div, "urban", urban["cty"], urban["n_county"]))
    if len(rural_pool):
        r = rural_pool.sample(1, random_state=16).iloc[0]
        picks.append((div, "rural", r["cty"], r["n_county"]))
P = pd.DataFrame(picks, columns=["division", "type", "county", "nad_points"])
rep.table("[G0] Counties chosen (urban = most NAD points in division; rural = random county with 2k–30k points)", P, index=False)
absent = sorted(set(DIVISION.values()) - set(P["division"]))
if absent:
    rep.say(f"     divisions with no NAD data: {absent}")

LAYERS = load_layers(["county", "tract"])
LT, LC = LAYERS["tract"], LAYERS["county"]

# ----------------------------------------------------------------------------- 3. sample + geocode
smp_path = f"{RAW}/sample_geocoded.parquet"
if not os.path.exists(smp_path):
    parts = []
    for div, typ, cty, _ in picks:
        d = K[K["cty"] == cty].copy()
        d["lon"], d["lat"] = pd.to_numeric(d["longitude"], errors="coerce"), pd.to_numeric(d["latitude"], errors="coerce")
        d = d.dropna(subset=["lon", "lat"])
        g = gpd.GeoSeries(gpd.points_from_xy(d["lon"], d["lat"]), crs=4326).to_crs(C.CRS_M)
        d["tx"], d["ty"] = g.x.to_numpy(), g.y.to_numpy()
        ti = locate(LT, d["tx"].to_numpy(), d["ty"].to_numpy())
        d = d[ti >= 0]; ti = ti[ti >= 0]
        d["d_tract"] = dist_to_own_boundary(LT, d["tx"].to_numpy(), d["ty"].to_numpy(), ti)
        near = d[d["d_tract"] < 50].head(PER_STRATUM)
        rand = d.drop(near.index).sample(min(PER_STRATUM, len(d) - len(near)), random_state=1)
        parts += [near.assign(stratum="near_50m", division=div, type=typ),
                  rand.assign(stratum="random", division=div, type=typ)]
    S = pd.concat(parts, ignore_index=True)
    S["uid"] = np.arange(len(S))
    S["street"] = (S["add_number"].astype(str) + " " + S["stnam_full"].fillna("")).str.strip()
    rows = [(u, a, c if isinstance(c, str) else "", st, str(z)[:5] if isinstance(z, str) else "")
            for u, a, c, st, z in zip(S["uid"], S["street"], S.get("post_city", pd.Series([""] * len(S))),
                                       S["state"], S.get("zip_code", pd.Series([""] * len(S))))]
    cg = census_batch(rows, f"{RAW}/census_geocoded.csv")
    rep.say(f"[G1] Census match status: {cg['match'].value_counts().to_dict()}")
    S = S.merge(cg.loc[cg["match"] == "Match", ["uid", "lon_c", "lat_c", "match_type"]], on="uid")
    gc = gpd.GeoSeries(gpd.points_from_xy(S["lon_c"], S["lat_c"]), crs=4269).to_crs(C.CRS_M)
    S["ox"], S["oy"] = gc.x.to_numpy(), gc.y.to_numpy()
    S["disp_m"] = np.hypot(S["ox"] - S["tx"], S["oy"] - S["ty"])
    S = S[S["disp_m"] <= 500]
    S[["uid", "division", "type", "cty", "stratum", "placement", "match_type", "tx", "ty", "ox", "oy", "disp_m"]
      if "placement" in S else ["uid", "division", "type", "cty", "stratum", "match_type", "tx", "ty", "ox", "oy", "disp_m"]
      ].to_parquet(smp_path, index=False)
S = pd.read_parquet(smp_path)

# ----------------------------------------------------------------------------- 4. TIGER roads of the chosen counties
tx, ty, ox, oy = (S[c].to_numpy() for c in ["tx", "ty", "ox", "oy"])
S["county_fips"] = LC.ids[np.maximum(locate(LC, tx, ty), 0)]
road_parts = []
for fips in sorted(S["county_fips"].unique()):
    z = f"{RAW}/tl_2025_{fips}_roads.zip"
    if not os.path.exists(z):
        r = requests.get(f"https://www2.census.gov/geo/tiger/TIGER2025/ROADS/tl_2025_{fips}_roads.zip", timeout=600)
        r.raise_for_status(); open(z, "wb").write(r.content)
    road_parts.append(gpd.read_file(f"zip://{z}").to_crs(C.CRS_M))
roads = pd.concat(road_parts, ignore_index=True)
RG = np.array([shapely.get_geometry(x, 0) for x in roads.geometry.to_numpy()])
RT = shapely.STRtree(RG)


def nearest_road(x, y):
    idx, dist = RT.query_nearest(shapely.points(x, y), return_distance=True, all_matches=False)
    oi = np.full(len(x), -1); od = np.full(len(x), np.nan)
    oi[idx[0]] = idx[1]; od[idx[0]] = dist
    return oi, od


def side(ri, qx, qy, px, py):
    line = RG[ri]
    s = shapely.line_locate_point(line, shapely.points(qx, qy)); Ln = shapely.length(line)
    s2 = np.where(s + 1.0 <= Ln, s + 1.0, s - 1.0)
    a = shapely.get_coordinates(shapely.line_interpolate_point(line, s))
    b = shapely.get_coordinates(shapely.line_interpolate_point(line, s2))
    return np.sign((b[:, 0] - a[:, 0]) * (py - a[:, 1]) - (b[:, 1] - a[:, 1]) * (px - a[:, 0]))


t_idx = locate(LT, tx, ty); c_idx = locate(LT, ox, oy)
S["wrong"] = c_idx != t_idx
S["d_true"] = dist_to_own_boundary(LT, tx, ty, t_idx)
S["d_obs"] = dist_to_own_boundary(LT, ox, oy, c_idx)
Pn = shapely.get_coordinates(shapely.shortest_line(shapely.points(tx, ty), LT.bounds[t_idx]))[1::2]
S["street_boundary"] = nearest_road(Pn[:, 0], Pn[:, 1])[1] <= STREET_TOL
rc, S["census_to_road_m"] = nearest_road(ox, oy)
S["true_to_road_m"] = nearest_road(tx, ty)[1]
Q = shapely.get_coordinates(shapely.shortest_line(shapely.points(ox, oy), RG[rc]))[1::2]
S["same_side"] = side(rc, Q[:, 0], Q[:, 1], ox, oy) == side(rc, Q[:, 0], Q[:, 1], tx, ty)
th = rng.uniform(0, 2 * np.pi, (len(S), M)); rho = S["disp_m"].to_numpy()
lab = locate(LT, (tx[:, None] + rho[:, None] * np.cos(th)).ravel(), (ty[:, None] + rho[:, None] * np.sin(th)).ravel())
S["p_random_dir"] = (lab.reshape(len(S), M) != t_idx[:, None]).mean(axis=1)
S.to_csv(f"{RAW}/national_points.csv", index=False)

# ----------------------------------------------------------------------------- 5. tables
def summarise(groups, label):
    rows = []
    for key, d in groups:
        key = key if isinstance(key, tuple) else (key,)
        k, n = int(d["wrong"].sum()), len(d); lo, hi = wilson(k, n)
        rows.append({**dict(zip(label, key)), "n": n, "median_disp_m": round(d["disp_m"].median(), 1),
                     "wrong_tract_%": 100 * k / n, "ci": f"[{100*lo:.2f}, {100*hi:.2f}]",
                     "random_direction_%": 100 * d["p_random_dir"].mean(),
                     "census_to_street_5-8m_%": 100 * d["census_to_road_m"].between(5, 8).mean(),
                     "census_to_street_p50": round(d["census_to_road_m"].median(), 1),
                     "same_side_%": 100 * d.loc[d["true_to_road_m"] <= 60, "same_side"].mean(),
                     "near_line_follows_street_%": 100 * d.loc[d["d_true"] < 50, "street_boundary"].mean(),
                     "non_exact_%": 100 * (d["match_type"] != "Exact").mean()})
    return pd.DataFrame(rows).round(3)


g1 = summarise(S.groupby(["division", "type"]), ["division", "type"]); g1.to_csv(f"{RES}/G1_by_county.csv", index=False)
rep.table("[G2] Per chosen county (division × urban/rural): real wrong-tract rate vs same lengths in random directions,\n"
          "     street offset, same side of street, share of nearby tract lines that follow a street", g1, index=False)
g2 = summarise(S.groupby("type"), ["type"]); g2.to_csv(f"{RES}/G2_urban_vs_rural.csv", index=False)
rep.table("[G3] Pooled urban vs rural", g2, index=False)
g3 = summarise(S.groupby(["stratum"]), ["stratum"])
rep.table("[G4] Pooled by stratum (all counties)", g3, index=False)

rows = []
for (typ, sb), d in S[S["d_true"] < 50].groupby(["type", "street_boundary"]):
    k, n = int(d["wrong"].sum()), len(d); lo, hi = wilson(k, n)
    rows.append({"type": typ, "boundary": "follows a street" if sb else "not a street", "n": n,
                 "wrong_tract_%": 100 * k / n, "ci": f"[{100*lo:.2f}, {100*hi:.2f}]",
                 "random_direction_%": 100 * d["p_random_dir"].mean()})
g4 = pd.DataFrame(rows).round(3); g4.to_csv(f"{RES}/G5_street_vs_nonstreet.csv", index=False)
rep.table("[G5] Within 50 m of a tract line: street vs non-street boundaries (the key test of the mechanism)", g4, index=False)
if "placement" in S:
    g5 = S.groupby("placement").agg(n=("wrong", "size"), wrong_pct=("wrong", "mean"), median_disp=("disp_m", "median"))
    g5["wrong_pct"] *= 100
    rep.table("[G6] By NAD placement type (groups n >= 30)", g5[g5["n"] >= 30].round(3))
rep.save()
