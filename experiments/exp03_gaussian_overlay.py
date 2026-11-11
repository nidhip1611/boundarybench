"""EXP03 — Gaussian-weighted overlay as a 5th strategy (needs EXP01 outputs).
Method: radial Gauss-Legendre quadrature (src/uncertainty.py: radial_quadrature).

Regenerates the exact EXP01 reported points (same seeds), verifies them against the saved files,
then adds the Gaussian overlay and compares all probabilistic strategies.

    python experiments/exp03_gaussian_overlay.py
Raw -> $BB_WORK/outputs/v2/gaussian_overlay.parquet   Tables + summary -> results/v2_gaussian/
"""
import glob
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import numpy as np
import pandas as pd

from src import config as C
from src.geo import load_layers, load_points, locate, dist_to_own_boundary
from src.metrics import rc_summary, op_point, ece
from src.report import Report
from src.uncertainty import simulate_obs, gaussian_overlay, gaussian_rmax, monte_carlo_gaussian

RES = C.out_dir(C.RESULTS, "v2_gaussian")
rep = Report("EXP03 Gaussian-weighted overlay", RES)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 400)

LAYERS = load_layers()
pts = load_points(LAYERS)
obs = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(f"{C.RAW}/v2/obs_*.parquet"))], ignore_index=True)
assert len(obs), "Run experiments/exp01_v2_main.py first"

# validation against high-sample Gaussian Monte Carlo
rng = np.random.default_rng(11)
L = LAYERS["tract"]; sub = pts[pts["layer"] == "tract"]; R = 20.0; sig = R / C.GAUSS_K95
ox, oy = simulate_obs(sub["x"].to_numpy(), sub["y"].to_numpy(), "gaussian", R, rng)
ci = locate(L, ox, oy); dd = dist_to_own_boundary(L, ox, oy, ci)
near = np.where((dd < R) | (ci < 0))[0][:300]
ti = sub["true_idx"].to_numpy()[near]
_, _, g_true = gaussian_overlay(L, ox[near], oy[near], sig, ti)
_, _, m_true = monte_carlo_gaussian(L, ox[near], oy[near], sig, 5000, rng, ti)
mae = float(np.abs(g_true - m_true).mean())
rep.say(f"[GA0] Gaussian overlay vs 5,000-sample Gaussian MC ({len(near)} obs): MAE = {mae:.4f} -> {'PASS' if mae < 0.015 else 'CHECK'}")

raw_path = f"{C.RAW}/v2/gaussian_overlay.parquet"
if not os.path.exists(raw_path):
    parts, timing = [], []
    for model in C.MODELS:
        for R in C.RADII:
            sig = R / C.GAUSS_K95; r_max = gaussian_rmax(sig)
            for li, (lname, sub) in enumerate(pts.groupby("layer")):
                L = LAYERS[lname]
                rng = np.random.default_rng(1000 * R + 100 * C.MODELS.index(model) + li)
                rp = sub.loc[sub.index.repeat(C.K_OBS)].reset_index(drop=True)
                x, y, tidx = rp["x"].to_numpy(), rp["y"].to_numpy(), rp["true_idx"].to_numpy()
                ox, oy = simulate_obs(x, y, model, R, rng)
                v2 = obs[(obs["model"] == model) & (obs["R"] == R) & (obs["layer"] == lname)]
                ok = (len(v2) == len(rp) and np.allclose(v2["err_m"].to_numpy(), np.hypot(ox - x, oy - y), atol=1e-6)
                      and (v2["point_id"].to_numpy() == rp["point_id"].to_numpy()).all())
                assert ok, f"Observation regeneration mismatch ({model} R={R} {lname})"
                crisp = v2["crisp_idx"].to_numpy(); dist = v2["dist_obs_m"].to_numpy()
                near = np.where((dist < r_max) | (crisp < 0))[0]
                g_idx, g_p, g_pt = crisp.copy(), np.ones(len(rp)), (crisp == tidx).astype(float)
                t = time.time()
                a, b, c = gaussian_overlay(L, ox[near], oy[near], sig, tidx[near])
                timing.append({"model": model, "R": R, "layer": lname, "n_obs": len(rp), "t_gauss_s": time.time() - t})
                g_idx[near], g_p[near], g_pt[near] = a, b, c
                parts.append(pd.DataFrame({"model": model, "R": R, "layer": lname, "point_id": rp["point_id"],
                                           "k": v2["k"].to_numpy(), "g_idx": g_idx, "g_p": g_p, "g_p_true": g_pt}))
                print(f"{model:8s} R={R:>2} {lname:6s} near={len(near):,} {time.time()-t:.1f}s")
    pd.concat(parts, ignore_index=True).to_parquet(raw_path, index=False)
    pd.DataFrame(timing).to_csv(f"{C.RAW}/v2/gaussian_timing.csv", index=False)
    rep.say("[GA1] regenerated observations match EXP01 exactly")

obs = obs.merge(pd.read_parquet(raw_path), on=["model", "R", "layer", "point_id", "k"], how="left", validate="one_to_one")
assert obs["g_p"].notna().all()

METHODS = {"Distance rule": ("dist_obs_m", "crisp_idx"), "Monte Carlo (disk)": ("mc_p", "mc_idx"),
           "Disk overlay": ("ex_p", "ex_idx"), "Gaussian overlay": ("g_p", "g_idx")}
rows = []
for (model, R), d in obs.groupby(["model", "R"]):
    nr = d[d["near"]]
    for name, (sc, pr) in METHODS.items():
        wrong = d[pr].to_numpy() != d["true_idx"].to_numpy()
        row = {"model": model, "R": R, "method": name, **rc_summary(d[sc].to_numpy(), wrong),
               **op_point(d[sc].to_numpy(), d[pr].to_numpy(), d["true_idx"], R if name == "Distance rule" else C.THETA)}
        if name != "Distance rule":
            row["ECE_near_%"] = ece(nr[sc], nr[pr] == nr["true_idx"])
            row["Brier_true_near"] = float(((1 - nr[sc + "_true"]) ** 2).mean())
        rows.append(row)
b1 = pd.DataFrame(rows).round(3); b1.to_csv(f"{RES}/GA1_method_comparison.csv", index=False)
rep.table("[GA1] Strategies incl. Gaussian overlay (pooled). Distance rule tau = R; others theta = 0.90.\n"
          "      Correctly specified model: Disk overlay for 'uniform' data, Gaussian overlay for 'gaussian' data.", b1, index=False)
tim = pd.read_csv(f"{C.RAW}/v2/gaussian_timing.csv").groupby("R")[["n_obs", "t_gauss_s"]].sum()
tim["gauss_ms_per_1k"] = 1e6 * tim["t_gauss_s"] / tim["n_obs"]
tim.round(2).to_csv(f"{RES}/GA2_runtime.csv")
rep.table("[GA2] Gaussian overlay runtime (ms per 1,000 queries; compare results/v2/T4_runtime.csv)", tim.round(2))
rep.save()
