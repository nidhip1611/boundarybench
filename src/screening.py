"""Screening rules for real geocodes, using only information available at assignment time (pure numpy/pandas).

A rule ranks addresses by a risk score (lower = riskier) and sends the riskiest ones for review.
  A  distance only            score = d_obs
  B  boundary type only       flag every geocode whose nearest tract line does not follow a street (fixed workload)
  C  distance + boundary type score = d_obs / w if the nearest tract line is not a street, else d_obs   (w >= 1)
     (w = 1 is rule A; large w sends all non-street cases first, ordered by distance, then street cases)
Errors are scored against the reference location only.
"""
import numpy as np
import pandas as pd

W_GRID = (1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 1e6)


def score_C(d, nonstreet, w):
    return np.where(nonstreet, d / w, d)


def flag_lowest(score, workload):
    """Flag the round(workload*n) lowest scores (stable order)."""
    n = len(score); k = int(round(workload * n))
    f = np.zeros(n, bool)
    if k > 0:
        f[np.argsort(score, kind="stable")[:k]] = True
    return f


def summarize(flag, wrong):
    n = len(wrong); ans = ~flag; E = int(wrong.sum())
    caught = int(wrong[flag].sum())
    return {"n": n, "reviewed_%": 100 * flag.mean(), "coverage_%": 100 * ans.mean(),
            "errors_caught": caught, "errors_total": E, "recall_%": 100 * caught / E if E else np.nan,
            "correct_withheld": int((flag & ~wrong).sum()), "errors_answered": int(wrong[ans].sum()),
            "risk_answered_%": 100 * wrong[ans].mean() if ans.any() else np.nan}


def best_w(d, nonstreet, wrong, workload, grid=W_GRID):
    """w that catches the most errors at this workload (ties -> smallest w, i.e. closest to distance only)."""
    best, bw = -1, grid[0]
    for w in grid:
        c = int(wrong[flag_lowest(score_C(d, nonstreet, w), workload)].sum())
        if c > best:
            best, bw = c, w
    return bw


def coverage_at_risk(score, wrong, target_pct):
    """Answer the safest addresses first (highest score); largest coverage whose answered risk <= target."""
    o = np.argsort(-score, kind="stable"); cw = np.cumsum(wrong[o]); k = np.arange(1, len(o) + 1)
    ok = np.where(100 * cw / k <= target_pct)[0]
    if len(ok) == 0:
        return {"coverage_%": 0.0, "answered": 0, "errors_answered": 0, "risk_answered_%": np.nan}
    m = ok[-1] + 1
    return {"coverage_%": 100 * m / len(o), "answered": int(m), "errors_answered": int(cw[m - 1]),
            "risk_answered_%": 100 * cw[m - 1] / m}


def bootstrap_diff(d, nonstreet, wrong, workload, w, B=2000, seed=19):
    """Address-level bootstrap of (errors caught by C) - (errors caught by A) at the same workload.
    Thresholds are re-applied (lowest-k) inside every replicate; w is held fixed."""
    rng = np.random.default_rng(seed); n = len(d); out = np.empty(B)
    sC = score_C(d, nonstreet, w)
    for b in range(B):
        i = rng.integers(0, n, n)
        out[b] = wrong[i][flag_lowest(sC[i], workload)].sum() - wrong[i][flag_lowest(d[i], workload)].sum()
    return np.percentile(out, [2.5, 50, 97.5])


def heldout(D, groups, workload, grid=W_GRID):
    """Leave-one-group-out. On the training groups: tau_A = workload-quantile of d_obs; w and tau_C chosen to catch the
    most training errors at the workload. Both thresholds are then applied unchanged to the held-out group, so the
    held-out review share can differ from the target workload. Also reports A re-thresholded to C's held-out review
    share ('A, same held-out workload') for a like-for-like comparison."""
    rows = []
    for g in groups:
        tr, te = D[D["group"] != g], D[D["group"] == g]
        if len(te) == 0:
            continue
        dtr, ntr, wtr = tr["d_obs"].to_numpy(), tr["nonstreet"].to_numpy(), tr["wrong"].to_numpy()
        dte, nte, wte = te["d_obs"].to_numpy(), te["nonstreet"].to_numpy(), te["wrong"].to_numpy()
        tauA = np.quantile(dtr, workload)
        w = best_w(dtr, ntr, wtr, workload, grid)
        tauC = np.quantile(score_C(dtr, ntr, w), workload)
        fA = dte < tauA
        fC = score_C(dte, nte, w) < tauC
        fA2 = flag_lowest(dte, fC.mean())
        fB = nte.copy()
        for rule, f, extra in [("A distance only", fA, f"tau={tauA:.1f} m"), ("C distance + boundary type", fC, f"w={w:g}"),
                               ("A, same held-out workload as C", fA2, ""), ("B non-street boundary only", fB, ""),
                               ("none (assign all)", np.zeros(len(te), bool), "")]:
            rows.append({"held_out": g, "workload_target_%": 100 * workload, "rule": rule, "param": extra,
                         **summarize(f, wte)})
    return pd.DataFrame(rows)
