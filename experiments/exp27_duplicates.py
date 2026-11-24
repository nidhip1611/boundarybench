"""EXP27 — Duplicate addresses across samples (reviewer request). Uses the archived Census outputs and EXP22 M_points.
Inputs are compared within each sample; matched output addresses are compared within and across samples.
    python experiments/exp27_duplicates.py   -> results/v2_duplicates/summary.txt
"""
import os
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
F = {"NYC, PLUTO": "nyc_pluto", "NYC, Address Points": "nyc_addresspoints", "Utah": "utah", "National": "nad"}
M = pd.read_csv(f"{ROOT}/results/v2_matched_edge/M_points.csv", dtype={"uid": str})
out, parts = [], []
for s, v in F.items():
    d = pd.read_csv(f"{ROOT}/data/geocoder_outputs/{v}_census_geocoded.csv", dtype=str)
    d["key"] = d["out_address"].str.upper().str.strip()
    out.append(f"{s}: rows {len(d)}, duplicate inputs {int(d['input'].str.upper().duplicated().sum())}")
    parts.append(M[M.source == s].merge(d[["uid", "key"]], on="uid", how="left"))
A = pd.concat(parts)
for st in ["near_50m", "random"]:
    x = A[A.stratum == st]; dup = x[x.key.notna() & x.key.duplicated(keep=False)]
    pairs = dup.groupby("key").source.apply(lambda q: " | ".join(sorted(q))).value_counts().to_dict()
    out.append(f"[{st}] edge-found rows {len(x)}; matched addresses in >1 row {dup.key.nunique()} ({len(dup)} rows, "
               f"{int(dup.wrong.sum())} disagreements); by sample: {pairs}")
for s in F:
    x = A[A.source == s]
    out.append(f"{s}: matched addresses in both strata {len(set(x[x.stratum=='near_50m'].key) & set(x[x.stratum=='random'].key))}")
near = A[A.stratum == "near_50m"]; dup = near[near.key.duplicated(keep=False)]
n_all, w_all = 5971, int(near.wrong.sum())          # 5,971 scored near-line; the 84 without a found edge had 0 disagreements
out.append(f"pooled near-line {w_all}/{n_all} = {100*w_all/n_all:.2f}%; dropping duplicate rows "
           f"{w_all-int(dup.wrong.sum())}/{n_all-len(dup)} = {100*(w_all-dup.wrong.sum())/(n_all-len(dup)):.2f}%")
os.makedirs(f"{ROOT}/results/v2_duplicates", exist_ok=True)
open(f"{ROOT}/results/v2_duplicates/summary.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out))
