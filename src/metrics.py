"""Selective-prediction and calibration metrics."""
import math

import numpy as np
import pandas as pd


def rc_curve(score, wrong):
    """Risk–coverage curve: answer when score >= threshold, for every distinct threshold (high to low)."""
    g = (pd.DataFrame({"s": np.asarray(score, float), "w": np.asarray(wrong, float)})
         .groupby("s")["w"].agg(["sum", "count"]).iloc[::-1])
    n = g["count"].cumsum().to_numpy()
    w = g["sum"].cumsum().to_numpy()
    return g.index.to_numpy(), n / len(score), w / n


def rc_summary(score, wrong):
    thr, cov, risk = rc_curve(score, wrong)
    c = np.concatenate([[0], cov])
    r = np.concatenate([[risk[0]], risk])
    aurc = float(np.sum(np.diff(c) * (r[1:] + r[:-1]) / 2))

    def cov_at(t):
        ok = risk <= t
        return float(cov[ok].max()) if ok.any() else 0.0

    return {"err_full_cov_%": 100 * float(np.mean(wrong)), "AURC_%": 100 * aurc,
            "cov@risk<=1%": 100 * cov_at(0.01), "cov@risk<=0.5%": 100 * cov_at(0.005),
            "cov@risk<=0.1%": 100 * cov_at(0.001)}


def op_point(score, pred, true, t):
    """Coverage and risk at one fixed threshold t."""
    ans = np.asarray(score) >= t
    wrong = np.asarray(pred) != np.asarray(true)
    return {"op_coverage_%": 100 * ans.mean(), "op_risk_%": 100 * (wrong[ans].mean() if ans.any() else 0)}


def ece(p, correct, bins=10):
    """Expected calibration error (%) of the top-region probability."""
    p = np.asarray(p, float)
    c = np.asarray(correct, float)
    e = 0.0
    edges = np.linspace(0, 1, bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p > lo) & (p <= hi) if lo > 0 else (p >= lo) & (p <= hi)
        if m.any():
            e += m.mean() * abs(p[m].mean() - c[m].mean())
    return 100 * e


def wilson(k, n, z=1.96):
    """95% Wilson interval for a proportion."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / den, (c + h) / den)
