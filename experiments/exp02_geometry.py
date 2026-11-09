"""EXP02 — Straight-boundary theory check + local geometry (needs EXP01 outputs).

1. Does the wrong-region rate collapse onto one curve of d/R, and does it match the closed-form
   prediction for a straight boundary?  (uniform: circular-segment fraction; Gaussian: Phi(-d/sigma))
2. Where real boundaries deviate from that prediction: classify each near-boundary true point by the
   geometry inside its radius-R disk — straight, bent/corner, multi-edge/sliver, junction (3+ regions),
   open edge (water / coverage gap).

    python experiments/exp02_geometry.py
Outputs -> results/v2_geometry/
"""
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely

from src import config as C
from src.geo import load_layers, load_points
from src.metrics import wilson
from src.report import Report
from src.uncertainty import p_straight

RES = C.out_dir(C.RESULTS, "v2_geometry")
FIG = C.out_dir(RES, "figures")
rep = Report("EXP02 straight-boundary theory + local geometry", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 400)

LAYERS = load_layers()
pts = load_points(LAYERS)
obs = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(f"{C.RAW}/v2/obs_*.parquet"))], ignore_index=True)
assert len(obs), "Run experiments/exp01_v2_main.py first"
obs["crisp_wrong"] = obs["crisp_idx"] != obs["true_idx"]
obs["d_over_R"] = obs["dist_true_m"] / obs["R"]
obs["p_line"] = 0.0
for model in C.MODELS:
    m = obs["model"] == model
    obs.loc[m, "p_line"] = p_straight(obs.loc[m, "dist_true_m"].to_numpy(), obs.loc[m, "R"].to_numpy(float), model)

# ----------------------------------------------------------------------------- 1. collapse onto d/R
edges = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0, 1.25, 1.5, 2.0, np.inf]
labels = [f"{a:g}-{b:g}" for a, b in zip(edges[:-1], edges[1:])]
obs["dR_bin"] = pd.cut(obs["d_over_R"], edges, labels=labels, right=False)
a1 = obs.groupby(["model", "dR_bin"], observed=True).agg(
    n=("crisp_wrong", "size"), observed_pct=("crisp_wrong", "mean"), straight_line_pct=("p_line", "mean"))
a1[["observed_pct", "straight_line_pct"]] *= 100
a1 = a1.round(3); a1.to_csv(f"{RES}/G1_dR_collapse.csv")
a1r = (obs.groupby(["model", "dR_bin", "R"], observed=True)["crisp_wrong"].mean() * 100).round(2).unstack("R")
a1r.to_csv(f"{RES}/G1b_dR_by_radius.csv")
rep.table("[G1] Wrong-region rate vs d/R: observed vs straight-line prediction (layers pooled)", a1)
rep.table("[G1b] Observed rate by d/R, one column per R (columns agree = collapse)", a1r)
for model in C.MODELS:
    d = obs[(obs["model"] == model) & (obs["d_over_R"] < (1 if model == "uniform" else 1.5))]
    rep.say(f"  {model}: observed {100*d['crisp_wrong'].mean():.2f}% vs predicted {100*d['p_line'].mean():.2f}% "
            f"(ratio {d['crisp_wrong'].mean()/max(d['p_line'].mean(), 1e-12):.3f}, n={len(d):,})")

# ----------------------------------------------------------------------------- 2. local geometry
def n_pieces(geoms):
    out = np.zeros(len(geoms), dtype=int)
    for i, gm in enumerate(geoms):
        try:
            if gm is None or gm.is_empty:
                continue
            if gm.geom_type == "GeometryCollection":
                lines = [p for p in gm.geoms if p.geom_type in ("LineString", "MultiLineString")]
                if not lines:
                    continue
                gm = shapely.union_all(lines)
            if gm.geom_type == "MultiLineString":
                gm = shapely.line_merge(gm)
            out[i] = shapely.get_num_geometries(gm)
        except Exception:
            out[i] = -1
    return out


geo_rows = []
for R in C.RADII:
    for lname, sub in pts.groupby("layer"):
        s = sub[sub["dist_to_boundary_m"] < R]
        if len(s) == 0:
            continue
        L = LAYERS[lname]
        x, y, own = s["x"].to_numpy(), s["y"].to_numpy(), s["true_idx"].to_numpy()
        disks = shapely.buffer(shapely.points(x, y), R, quad_segs=32)
        inp, _ = L.tree.query(disks, predicate="intersects")
        n_reg = np.bincount(inp, minlength=len(s))
        b = shapely.bounds(disks)
        seg = shapely.intersection(shapely.clip_by_rect(L.bounds[own], b[:, 0], b[:, 1], b[:, 2], b[:, 3]), disks)
        d = s["dist_to_boundary_m"].to_numpy()
        bend = shapely.length(seg) / (2 * np.sqrt(np.maximum(R * R - d * d, 1e-9)))
        pieces = n_pieces(seg)
        cls = np.where(n_reg <= 1, "open edge (water/gap)",
              np.where(n_reg >= 3, "junction (3+ regions)",
              np.where(pieces >= 2, "multi-edge / sliver",
              np.where(bend > 1.10, "bent / corner", "straight"))))
        geo_rows.append(pd.DataFrame({"point_id": s["point_id"].to_numpy(), "layer": lname, "R": R, "geom_class": cls,
                                      "n_regions": n_reg, "n_pieces": pieces, "bend_ratio": bend}))
geo = pd.concat(geo_rows, ignore_index=True)
geo.to_csv(f"{RES}/G2_point_geometry.csv", index=False)
obs = obs.merge(geo[["point_id", "R", "geom_class"]], on=["point_id", "R"], how="left")
obs["geom_class"] = obs["geom_class"].fillna("far (d >= R)")

rows = []
for (model, R, cls), d in obs.groupby(["model", "R", "geom_class"]):
    k, n = int(d["crisp_wrong"].sum()), len(d)
    lo, hi = wilson(k, n)
    rows.append({"model": model, "R": R, "geom_class": cls, "n_obs": n, "n_points": d["point_id"].nunique(),
                 "observed_%": 100 * k / n, "ci_low_%": 100 * lo, "ci_high_%": 100 * hi,
                 "straight_line_%": 100 * d["p_line"].mean(),
                 "obs/pred": (k / n) / max(d["p_line"].mean(), 1e-12)})
a2 = pd.DataFrame(rows).round(3); a2.to_csv(f"{RES}/G2_geometry_vs_straight_line.csv", index=False)
rep.table("[G2] Observed vs straight-line prediction by local geometry (points with d < R), R = 20 and 50",
          a2[a2["R"].isin([20, 50])], index=False)
gl = geo[geo["R"] == 20]
rep.table("[G2b] Share of near-boundary points per geometry class, by layer (R = 20, %)",
          (pd.crosstab(gl["layer"], gl["geom_class"], normalize="index") * 100).round(1))

# ----------------------------------------------------------------------------- figure
plt.rcParams.update({"font.size": 9})
fig, axes = plt.subplots(1, 2, figsize=(8, 3.2), sharey=True)
for ax, model in zip(axes, C.MODELS):
    d = obs[obs["model"] == model]
    for R in C.RADII:
        dd = d[d["R"] == R]
        gb = dd.groupby(pd.cut(dd["d_over_R"], np.linspace(0, 2, 41)), observed=True)
        ax.plot(gb["d_over_R"].mean(), 100 * gb["crisp_wrong"].mean(), "o", ms=3, label=f"R = {R} m")
    u = np.linspace(0, 2, 200)
    ax.plot(u, 100 * p_straight(u * 20, 20.0, model), "k-", lw=1.2, label="straight-line theory")
    ax.set_title(f"{model} error"); ax.set_xlabel("distance to boundary / R")
axes[0].set_ylabel("wrong region (%)"); axes[0].legend(fontsize=7)
plt.tight_layout(); plt.savefig(f"{FIG}/figG1_dR_collapse.png", dpi=300); plt.close()
rep.save()
