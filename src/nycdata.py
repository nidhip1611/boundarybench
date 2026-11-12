"""Download helpers for the NYC real-world experiments (EXP04, EXP09)."""
import csv
import io
import os
import time
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from . import config as C

NYC_COUNTIES = ["36005", "36047", "36061", "36081", "36085"]   # Bronx, Kings, New York, Queens, Richmond
BORO = {"1": "New York", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island",
        "MN": "New York", "BX": "Bronx", "BK": "Brooklyn", "QN": "Queens", "SI": "Staten Island"}


def tiger_roads(folder):
    """TIGER/Line 2025 all-roads centerlines for the five NYC counties, in the metric CRS."""
    os.makedirs(folder, exist_ok=True)
    parts = []
    for fips in NYC_COUNTIES:
        z = os.path.join(folder, f"tl_2025_{fips}_roads.zip")
        if not os.path.exists(z):
            r = requests.get(f"https://www2.census.gov/geo/tiger/TIGER2025/ROADS/tl_2025_{fips}_roads.zip", timeout=600)
            r.raise_for_status()
            open(z, "wb").write(r.content)
        parts.append(gpd.read_file(f"zip://{z}"))
    roads = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(roads, geometry="geometry", crs=parts[0].crs).to_crs(C.CRS_M)


def census_batch(rows, path, chunk=2500):
    """rows: list of (uid, street, city, state, zip). Cached Census batch geocoding -> DataFrame."""
    if not os.path.exists(path):
        out = []
        for s in range(0, len(rows), chunk):
            buf = io.StringIO(); w = csv.writer(buf)
            for r in rows[s:s + chunk]:
                w.writerow(r)
            for attempt in range(3):
                try:
                    resp = requests.post("https://geocoding.geo.census.gov/geocoder/geographies/addressbatch",
                                         files={"addressFile": ("a.csv", buf.getvalue().encode(), "text/csv")},
                                         data={"benchmark": "Public_AR_Current", "vintage": "Current_Current"},
                                         timeout=1800)
                    resp.raise_for_status()
                    break
                except Exception as e:
                    print(f"census batch attempt {attempt + 1} failed: {e}"); time.sleep(20)
            else:
                raise RuntimeError("Census Geocoder unavailable")
            out += [rec + [""] * (12 - len(rec)) for rec in csv.reader(io.StringIO(resp.text)) if rec]
            print(f"geocoded {min(s + chunk, len(rows))}/{len(rows)}")
        pd.DataFrame([r[:12] for r in out], columns=["uid", "input", "match", "match_type", "out_address", "coords",
                     "tiger_id", "side", "st", "co", "tract", "block"]).to_csv(path, index=False)
    cg = pd.read_csv(path, dtype=str)
    cg["uid"] = pd.to_numeric(cg["uid"], errors="coerce")
    cg = cg.dropna(subset=["uid"]); cg["uid"] = cg["uid"].astype(int)
    m = cg["match"] == "Match"
    xy = cg.loc[m, "coords"].str.split(",", expand=True).astype(float)
    cg.loc[m, "lon_c"], cg.loc[m, "lat_c"] = xy[0], xy[1]
    return cg


def _pick(cols, candidates, what):
    for c in candidates:
        if c in cols:
            return c
    raise KeyError(f"Could not find the {what} column. Available columns: {sorted(cols)}")


def nyc_address_points(path):
    """NYC Address Points (CSCL; placed ~5 ft inside the building footprint along the addressed street front).
    Returns DataFrame [hn, street, zip, boro, lon, lat]."""
    if not os.path.exists(path):
        urls = ["https://data.cityofnewyork.us/api/views/uf93-f8nk/rows.csv?accessType=DOWNLOAD",       # current (2025+)
                "https://data.cityofnewyork.us/api/v3/views/uf93-f8nk/export.csv?accessType=DOWNLOAD",
                "https://data.cityofnewyork.us/resource/g6pj-hd8k.csv?$limit=2000000",                      # legacy ids
                "https://data.cityofnewyork.us/api/views/g6pj-hd8k/rows.csv?accessType=DOWNLOAD",
                "https://data.cityofnewyork.us/api/views/emzr-v3pi/rows.csv?accessType=DOWNLOAD"]
        for u in urls:
            try:
                r = requests.get(u, timeout=1800); r.raise_for_status()
                open(path, "wb").write(r.content); break
            except Exception as e:
                print("address points download failed:", u, e)
        else:
            raise RuntimeError("NYC Address Points download failed")
    ap = pd.read_csv(path, dtype=str)
    ap.columns = [c.strip().lower().replace(" ", "_") for c in ap.columns]
    cols = set(ap.columns)
    hn = _pick(cols, ["h_no", "house_number", "housenum", "house_no", "hnum", "addr_hn", "hn", "house_num"], "house number")
    st = _pick(cols, ["full_stree", "full_street_name", "full_street", "st_name", "street_name", "stname", "street"], "street name")
    zp = _pick(cols, ["zipcode", "zip_code", "zip", "postcode", "postal_code"], "ZIP code")
    bo = next((c for c in ["borocode", "boro_code", "boro", "borough"] if c in cols), None)
    if "the_geom" in cols or "geometry" in cols or "point" in cols:
        g = ap[next(c for c in ["the_geom", "geometry", "point"] if c in cols)].str.extract(r"(-?\d+\.\d+)\s+(-?\d+\.\d+)")
        lon, lat = g[0].astype(float), g[1].astype(float)
    else:
        lon = pd.to_numeric(ap[_pick(cols, ["longitude", "lon", "x"], "longitude")], errors="coerce")
        lat = pd.to_numeric(ap[_pick(cols, ["latitude", "lat", "y"], "latitude")], errors="coerce")
    out = pd.DataFrame({"hn": ap[hn].str.strip(), "street": ap[st].str.strip(), "zip": ap[zp].str[:5],
                        "boro": ap[bo].astype(str).str.strip() if bo else "", "lon": lon, "lat": lat})
    out = out.dropna(subset=["hn", "street", "zip", "lon", "lat"])
    out = out[out["hn"].str.match(r"^\d+[A-Z]?(-\d+)?$") & (out["lat"].between(40.4, 41.0))]
    return out.drop_duplicates(["hn", "street", "zip"]).reset_index(drop=True)
