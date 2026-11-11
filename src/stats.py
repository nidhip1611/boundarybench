"""Cluster (per benchmark point) bootstrap: the K noisy observations of one point are not independent,
so confidence intervals resample whole points, never single observations."""
import numpy as np
import pandas as pd


def point_bootstrap(df, stat_fn, B=300, seed=0, cluster="point_id"):
    """df: rows for one setting; stat_fn(df) -> dict of floats. Returns DataFrame [metric, value, ci_low, ci_high]."""
    df = df.sort_values([cluster]).reset_index(drop=True)
    codes, uniq = pd.factorize(df[cluster])
    counts = np.bincount(codes)
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    point_est = stat_fn(df)
    rng = np.random.default_rng(seed)
    equal = (counts == counts[0]).all()
    if equal:
        M = np.arange(len(df)).reshape(len(uniq), counts[0])
    draws = {k: [] for k in point_est}
    for _ in range(B):
        pick = rng.integers(0, len(uniq), len(uniq))
        rows = M[pick].ravel() if equal else np.concatenate([np.arange(starts[p], starts[p] + counts[p]) for p in pick])
        r = stat_fn(df.iloc[rows])
        for k in draws:
            draws[k].append(r[k])
    out = []
    for k, v in point_est.items():
        a = np.asarray(draws[k], float)
        out.append({"metric": k, "value": v, "ci_low": np.nanpercentile(a, 2.5), "ci_high": np.nanpercentile(a, 97.5)})
    return pd.DataFrame(out)
