"""EXP14 — Simplified (cartographic) boundary files: errors with PERFECT locations.

Many users download the Census cartographic boundary files (generalised, clipped to the shoreline) instead of
TIGER/Line. Here the location is exact — no positional error at all — and we only swap the polygon file:
  tract   cb_2024_us_tract_500k
  county  cb_2024_us_county_500k / 5m / 20m
Wrong = cartographic polygon differs from the TIGER label; outside = point falls outside every cartographic polygon
(e.g. clipped water). Benchmark true points (by distance band) and the NYC addresses (true and Census points).

    python experiments/exp14_cartographic_boundaries.py      (needs internet the first time)
Outputs -> results/v2_cartographic/
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely

from src import config as C
from src.geo import Layer, load_layers, load_points, locate
from src.metrics import wilson
from src.report import Report

RES = C.out_dir(C.RESULTS, "v2_cartographic")
RAW = C.out_dir(C.RAW, "cartographic")
rep = Report("EXP14 cartographic boundary files with exact locations", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)
BASE = "https://www2.census.gov/geo/tiger/GENZ2024/shp"
STATES = ["01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16", "17", "18", "19", "20", "21", "22",
          "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "40", "41",
          "42", "44", "45", "46", "47", "48", "49", "50", "51", "53", "54", "55", "56"]


def fetch(name):
    z = os.path.join(RAW, name)
    if not os.path.exists(z):
        r = requests.get(f"{BASE}/{name}", timeout=900); r.raise_for_status()
        open(z, "wb").write(r.content)
    return z


def cb_layer(names):
    parts = [gpd.read_file(f"zip://{fetch(n)}") for n in names]
    gdf = gpd.GeoDataFrame(pd.concat([p.to_crs(parts[0].crs) for p in parts], ignore_index=True),
                           geometry="geometry", crs=parts[0].crs).to_crs(C.CRS_M)
    geoms = gdf.geometry.to_numpy()
    bad = ~shapely.is_valid(geoms)
    if bad.any():
        geoms[bad] = shapely.make_valid(geoms[bad])
    return Layer(gdf["GEOID"].astype(str).to_numpy(), geoms)


try:
    CB = {"tract 500k": cb_layer(["cb_2024_us_tract_500k.zip"])}
except Exception as e:
    print("national tract file unavailable, using per-state files:", e)
    CB = {"tract 500k": cb_layer([f"cb_2024_{s}_tract_500k.zip" for s in STATES])}
for res in ["500k", "5m", "20m"]:
    CB[f"county {res}"] = cb_layer([f"cb_2024_us_county_{res}.zip"])
for k, L in CB.items():
    rep.say(f"{k}: {len(L.ids):,} polygons")

LAYERS = load_layers()
pts = load_points(LAYERS)
BANDS = [-0.01, 10, 25, 50, 100, 500, np.inf]
BLAB = ["0-10m", "10-25m", "25-50m", "50-100m", "100-500m", ">500m"]

rows = []
for key, L in CB.items():
    layer = key.split()[0]
    sub = pts[pts["layer"] == layer]
    idx = locate(L, sub["x"].to_numpy(), sub["y"].to_numpy())
    got = np.where(idx >= 0, L.ids[np.maximum(idx, 0)], "")
    outside = idx < 0
    wrong = ~outside & (got != sub["label_id"].to_numpy())
    band = pd.cut(sub["dist_to_boundary_m"], BANDS, labels=BLAB)
    for b in BLAB + ["all"]:
        m = (band == b).to_numpy() if b != "all" else np.ones(len(sub), bool)
        k, n = int(wrong[m].sum()), int(m.sum()); lo, hi = wilson(k, n)
        rows.append({"file": key, "band": b, "n": n, "wrong_region_%": 100 * k / max(n, 1),
                     "ci": f"[{100*lo:.2f}, {100*hi:.2f}]", "outside_all_polygons_%": 100 * outside[m].mean()})
t1 = pd.DataFrame(rows).round(3); t1.to_csv(f"{RES}/K1_benchmark_exact_points.csv", index=False)
rep.table("[K1] Benchmark TRUE points (no positional error) assigned with cartographic files vs their TIGER label", t1, index=False)

nyc_path = f"{C.RAW}/nyc/nyc_streets_points.csv"
if os.path.exists(nyc_path):
    D = pd.read_csv(nyc_path)
    LT, L = LAYERS["tract"], CB["tract 500k"]
    rows = []
    for smp, d in D.groupby("sample"):
        true_tiger = LT.ids[d["t_idx"].to_numpy()]
        it = locate(L, d["tx"].to_numpy(), d["ty"].to_numpy())
        io_ = locate(L, d["ox"].to_numpy(), d["oy"].to_numpy())
        cb_true = np.where(it >= 0, L.ids[np.maximum(it, 0)], "")
        cb_obs = np.where(io_ >= 0, L.ids[np.maximum(io_, 0)], "")
        rows.append({"sample": smp, "n": len(d),
                     "TIGER: Census point wrong_%": 100 * d["wrong"].mean(),
                     "cartographic: TRUE point wrong_%": 100 * ((cb_true != true_tiger) & (it >= 0)).mean(),
                     "cartographic: Census point wrong_%": 100 * ((cb_obs != true_tiger) & (io_ >= 0)).mean(),
                     "cartographic: Census point outside_%": 100 * (io_ < 0).mean()})
    t2 = pd.DataFrame(rows).round(3); t2.to_csv(f"{RES}/K2_nyc.csv", index=False)
    rep.table("[K2] NYC addresses: tract errors with TIGER vs cartographic (500k) tract polygons", t2, index=False)
rep.save()
