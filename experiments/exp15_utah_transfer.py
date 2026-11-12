"""EXP15 — Second real-world region: Utah, urban vs rural (tests the NYC mechanism where streets and tract lines
do not coincide as often).

Ground truth: UGRC statewide address points (Utah Geospatial Resource Center; county Master Address List authorities).
Regions: URBAN = Salt Lake County (49035); RURAL = Sanpete, Sevier, Millard, Uintah, Carbon, Emery (49039, 49041,
49027, 49047, 49007, 49015). Per region: 750 addresses within 50 m of a tract line + 750 random; Census batch geocoded.
Same measurements as EXP09/EXP11: street offset, street vs non-street boundaries, same side of street, wrong-tract
rate, and the random-direction counterfactual. Prediction from the NYC mechanism: more tract crossings where the
tract line does not follow a street (expected more often in rural areas).

    python experiments/exp15_utah_transfer.py        (needs internet the first time)
Raw -> $BB_WORK/outputs/utah/   Tables, figures, summary -> results/v2_utah/
"""
import json
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
from src.geo import load_layers, locate, dist_to_own_boundary
from src.metrics import wilson
from src.nycdata import census_batch
from src.report import Report
from src.uncertainty import p_straight_empirical

RAW = C.out_dir(C.RAW, "utah")
RES = C.out_dir(C.RESULTS, "v2_utah")
rep = Report("EXP15 Utah urban vs rural real-world transfer", RES)
pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 200)
FS = "https://services1.arcgis.com/99lidPhWCzftIe9K/ArcGIS/rest/services/UtahAddressPoints/FeatureServer/0/query"
REGIONS = {"urban (Salt Lake Co.)": ["49035"],
           "rural (6 counties)": ["49039", "49041", "49027", "49047", "49007", "49015"]}
PER_STRATUM, STREET_TOL, M = 750, 1.5, 200
rng = np.random.default_rng(1515)


# ----------------------------------------------------------------------------- 1. address points
def fetch_county(fips):
    path = f"{RAW}/ap_{fips}.parquet"
    if os.path.exists(path):
        return pd.read_parquet(path)
    feats, off = [], 0
    fields = "FullAdd,AddNum,StreetName,City,ZipCode,CountyID,PtLocation,PtType,UnitID"
    for where in [f"CountyID='{fips}'", f"CountyID={fips}"]:
        try:
            while True:
                r = requests.get(FS, params={"where": where, "outFields": fields, "outSR": 4326, "f": "geojson",
                                             "resultOffset": off, "resultRecordCount": 2000}, timeout=300)
                r.raise_for_status()
                js = r.json()
                if "error" in js:
                    raise RuntimeError(js["error"])
                batch = js.get("features", [])
                feats += batch
                off += len(batch)
                if len(batch) < 2000:
                    break
                time.sleep(0.2)
            break
        except Exception as e:
            print(f"query failed for {fips} with where={where}: {e}"); feats, off = [], 0
    if not feats:
        raise RuntimeError(f"No address points for county {fips}")
    rows = [{**f["properties"], "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]}
            for f in feats if f.get("geometry")]
    df = pd.DataFrame(rows)
    df.to_parquet(path, index=False)
    print(f"county {fips}: {len(df):,} address points")
    return df


LT = load_layers(["tract"])["tract"]
pts = []
for region, counties in REGIONS.items():
    df = pd.concat([fetch_county(c) for c in counties], ignore_index=True).assign(region=region)
    pts.append(df)
ap = pd.concat(pts, ignore_index=True)
n_raw = len(ap)
ap = ap[ap["UnitID"].isna() | (ap["UnitID"].astype(str).str.strip().isin(["", "None"]))]       # one point per address
ap = ap[ap["AddNum"].astype(str).str.match(r"^\d+$") & ap["FullAdd"].notna() & ap["ZipCode"].notna()]
ap = ap.drop_duplicates(["FullAdd", "ZipCode"]).reset_index(drop=True)
g = gpd.GeoSeries(gpd.points_from_xy(ap["lon"], ap["lat"]), crs=4326).to_crs(C.CRS_M)
ap["tx"], ap["ty"] = g.x.to_numpy(), g.y.to_numpy()
ti = locate(LT, ap["tx"].to_numpy(), ap["ty"].to_numpy())
ap = ap[ti >= 0].reset_index(drop=True); ti = ti[ti >= 0]
ap["d_tract"] = dist_to_own_boundary(LT, ap["tx"].to_numpy(), ap["ty"].to_numpy(), ti)
rep.say(f"[U0] UGRC address points downloaded: {n_raw:,} | usable (no units, numeric house number): {len(ap):,}")
rep.table("[U0b] Point placement types (PtLocation) by region",
          pd.crosstab(ap["PtLocation"].fillna("unknown"), ap["region"]))

# ----------------------------------------------------------------------------- 2. sample + Census geocoding
smp_path = f"{RAW}/sample_geocoded.parquet"
if not os.path.exists(smp_path):
    parts = []
    for region, d in ap.groupby("region"):
        near = rng.choice(d.index[d["d_tract"] < 50].to_numpy(), size=min(PER_STRATUM, (d["d_tract"] < 50).sum()), replace=False)
        rand = rng.choice(np.setdiff1d(d.index.to_numpy(), near), size=PER_STRATUM, replace=False)
        parts += [d.loc[near].assign(stratum="near_50m"), d.loc[rand].assign(stratum="random")]
    smp = pd.concat(parts).reset_index(drop=True)
    smp["uid"] = np.arange(len(smp))
    rows = [(u, a, c if isinstance(c, str) and c else "", "UT", str(z)[:5])
            for u, a, c, z in zip(smp["uid"], smp["FullAdd"], smp["City"], smp["ZipCode"])]
    cg = census_batch(rows, f"{RAW}/census_geocoded.csv")
    rep.say(f"[U1] Census match status: {cg['match'].value_counts().to_dict()}")
    smp = smp.merge(cg.loc[cg["match"] == "Match", ["uid", "lon_c", "lat_c", "match_type"]], on="uid")
    gc = gpd.GeoSeries(gpd.points_from_xy(smp["lon_c"], smp["lat_c"]), crs=4269).to_crs(C.CRS_M)
    smp["ox"], smp["oy"] = gc.x.to_numpy(), gc.y.to_numpy()
    smp["disp_m"] = np.hypot(smp["ox"] - smp["tx"], smp["oy"] - smp["ty"])
    smp = smp[smp["disp_m"] <= 500]
    smp[["uid", "region", "stratum", "PtLocation", "match_type", "tx", "ty", "ox", "oy", "disp_m"]].to_parquet(smp_path, index=False)
S = pd.read_parquet(smp_path)

# ----------------------------------------------------------------------------- 3. TIGER roads for the counties
parts = []
for fips in sum(REGIONS.values(), []):
    z = f"{RAW}/tl_2025_{fips}_roads.zip"
    if not os.path.exists(z):
        r = requests.get(f"https://www2.census.gov/geo/tiger/TIGER2025/ROADS/tl_2025_{fips}_roads.zip", timeout=600)
        r.raise_for_status(); open(z, "wb").write(r.content)
    parts.append(gpd.read_file(f"zip://{z}"))
roads = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=parts[0].crs).to_crs(C.CRS_M)
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


tx, ty, ox, oy = (S[c].to_numpy() for c in ["tx", "ty", "ox", "oy"])
t_idx = locate(LT, tx, ty); c_idx = locate(LT, ox, oy)
S["wrong"] = c_idx != t_idx
S["d_true"] = dist_to_own_boundary(LT, tx, ty, t_idx)
S["d_obs"] = dist_to_own_boundary(LT, ox, oy, c_idx)
P = shapely.get_coordinates(shapely.shortest_line(shapely.points(tx, ty), LT.bounds[t_idx]))[1::2]
S["dP_road"] = nearest_road(P[:, 0], P[:, 1])[1]
S["street_boundary"] = S["dP_road"] <= STREET_TOL
rc, S["census_to_road_m"] = nearest_road(ox, oy)
S["true_to_road_m"] = nearest_road(tx, ty)[1]
Q = shapely.get_coordinates(shapely.shortest_line(shapely.points(ox, oy), RG[rc]))[1::2]
S["same_side"] = side(rc, Q[:, 0], Q[:, 1], ox, oy) == side(rc, Q[:, 0], Q[:, 1], tx, ty)
th = rng.uniform(0, 2 * np.pi, (len(S), M)); rho = S["disp_m"].to_numpy()
lab = locate(LT, (tx[:, None] + rho[:, None] * np.cos(th)).ravel(), (ty[:, None] + rho[:, None] * np.sin(th)).ravel())
S["p_random_dir"] = (lab.reshape(len(S), M) != t_idx[:, None]).mean(axis=1)
S.to_csv(f"{RAW}/utah_points.csv", index=False)

# ----------------------------------------------------------------------------- 4. tables
rows = []
for (region, st), d in S.groupby(["region", "stratum"]):
    k, n = int(d["wrong"].sum()), len(d); lo, hi = wilson(k, n)
    rows.append({"region": region, "stratum": st, "n": n, "median_disp_m": d["disp_m"].median(),
                 "wrong_tract_%": 100 * k / n, "ci": f"[{100*lo:.2f}, {100*hi:.2f}]",
                 "random_direction_%": 100 * d["p_random_dir"].mean(),
                 "isotropic_pred_%": 100 * p_straight_empirical(d["d_true"].to_numpy(), S["disp_m"].to_numpy()).mean(),
                 "census_to_street_p10/p50/p90": d["census_to_road_m"].quantile([.1, .5, .9]).round(1).tolist(),
                 "census_to_street_5-8m_%": 100 * d["census_to_road_m"].between(5, 8).mean(),
                 "true_to_street_p50": round(d["true_to_road_m"].median(), 1),
                 "non_exact_match_%": 100 * (d["match_type"] != "Exact").mean()})
u1 = pd.DataFrame(rows).round(3); u1.to_csv(f"{RES}/U1_overview.csv", index=False)
rep.table("[U1] Utah: wrong-tract rate (real), same lengths in random directions, isotropic prediction, street offset", u1, index=False)

rows = []
for (region, sb), d in S[S["d_true"] < 50].groupby(["region", "street_boundary"]):
    k, n = int(d["wrong"].sum()), len(d); lo, hi = wilson(k, n)
    rows.append({"region": region, "boundary": "follows a street" if sb else "not a street", "n": n,
                 "wrong_tract_%": 100 * k / n, "ci": f"[{100*lo:.2f}, {100*hi:.2f}]",
                 "random_direction_%": 100 * d["p_random_dir"].mean(),
                 "census_to_tract_line_5-8m_%": 100 * d["d_obs"].between(5, 8).mean()})
u2 = pd.DataFrame(rows).round(3); u2.to_csv(f"{RES}/U2_street_vs_nonstreet.csv", index=False)
rep.table(f"[U2] Within 50 m of a tract line: boundary follows a street (TIGER road within {STREET_TOL} m) or not", u2, index=False)

u3 = (S[S["true_to_road_m"] <= 60].groupby(["region", "wrong"])["same_side"].agg(["size", "mean"])
      .rename(columns={"size": "n", "mean": "same_side_share"}).round(4))
u3.to_csv(f"{RES}/U3_same_side.csv")
rep.table("[U3] Census point on the same side of its nearest street as the true address", u3)

u4 = S.groupby(["region", "PtLocation"], dropna=False).agg(n=("wrong", "size"), wrong_pct=("wrong", "mean"),
                                                            median_disp_m=("disp_m", "median"))
u4["wrong_pct"] *= 100
u4 = u4[u4["n"] >= 30].round(3); u4.to_csv(f"{RES}/U4_by_point_location.csv")
rep.table("[U4] By how the true address point was placed (PtLocation; groups with n >= 30)", u4)
rep.save()
