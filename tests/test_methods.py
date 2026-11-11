"""Correctness tests against closed-form answers.   Run:  python -m pytest tests -q"""
import os
import sys

import numpy as np
import pytest
import shapely

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.geo import Layer, locate, dist_to_own_boundary
from src.metrics import rc_summary, op_point
from src.uncertainty import (disk_overlay, gaussian_overlay, monte_carlo, p_straight, p_straight_empirical,
                             simulate_obs, top_from_pairs)

R = 20.0
SIG = R / 2.4477


def halfplane():
    return Layer(np.array(["W", "E"]), np.array([shapely.box(-2000, -2000, 0, 2000), shapely.box(0, -2000, 2000, 2000)]))


def quadrants():
    return Layer(np.array(["SW", "SE", "NW", "NE"]),
                 np.array([shapely.box(-2000, -2000, 0, 0), shapely.box(0, -2000, 2000, 0),
                           shapely.box(-2000, 0, 0, 2000), shapely.box(0, 0, 2000, 2000)]))


def test_locate_and_distance():
    L = halfplane()
    idx = locate(L, np.array([-5.0, 7.0]), np.array([0.0, 0.0]))
    assert list(idx) == [0, 1]
    assert np.allclose(dist_to_own_boundary(L, np.array([-5.0, 7.0]), np.array([0.0, 0.0]), idx), [5, 7])


@pytest.mark.parametrize("d", [0.5, 5, 10, 15, 19])
def test_disk_overlay_matches_straight_line_formula(d):
    _, _, pt = disk_overlay(halfplane(), np.array([-d]), np.array([0.0]), R, np.array([0]))
    assert abs((1 - pt[0]) - p_straight(d, R, "uniform")) < 2e-3


@pytest.mark.parametrize("d", [0.5, 5, 10, 15, 20, 25, 30])
def test_gaussian_overlay_matches_phi(d):
    _, _, pt = gaussian_overlay(halfplane(), np.array([-d]), np.array([0.0]), SIG, np.array([0]))
    assert abs((1 - pt[0]) - p_straight(d, R, "gaussian")) < 1e-3


@pytest.mark.parametrize("a,b", [(3, 4), (10, 10), (20, 5)])
def test_gaussian_overlay_matches_gaussian_mc_at_a_junction(a, b):
    from src.uncertainty import monte_carlo_gaussian
    L = quadrants(); x, y, t = np.array([-a]), np.array([-b]), np.array([0])
    _, _, mc = monte_carlo_gaussian(L, x, y, SIG, 400000, np.random.default_rng(3), t)
    _, _, g = gaussian_overlay(L, x, y, SIG, t)
    assert abs(mc[0] - g[0]) < 4e-3


@pytest.mark.parametrize("a,b", [(3, 4), (8, 2), (12, 12)])
def test_overlays_match_monte_carlo_at_a_junction(a, b):
    L = quadrants(); x, y, t = np.array([-a]), np.array([-b]), np.array([0])
    rng = np.random.default_rng(0)
    _, _, mc = monte_carlo(L, x, y, R, 200000, rng, t)
    _, _, ex = disk_overlay(L, x, y, R, t)
    assert abs(mc[0] - ex[0]) < 5e-3


def test_straight_line_formula_matches_simulation():
    rng = np.random.default_rng(1)
    ox, _ = simulate_obs(np.zeros(400000), np.zeros(400000), "uniform", R, rng)
    assert abs((ox > 10).mean() - p_straight(10, R, "uniform")) < 3e-3
    ox, _ = simulate_obs(np.zeros(400000), np.zeros(400000), "gaussian", R, rng)
    assert abs((ox > 10).mean() - p_straight(10, R, "gaussian")) < 3e-3
    assert abs(p_straight_empirical([0.0], np.array([5.0, 10.0]))[0] - 0.5) < 1e-9


def test_top_from_pairs_and_metrics():
    top, p, pt = top_from_pairs(3, np.array([0, 0, 2, 0]), np.array([5, 6, 9, 5]), np.array([.5, .3, .4, .2]), np.array([6, 1, 9]))
    assert list(top) == [5, -1, 9] and np.allclose(p, [.7, 0, .4]) and np.allclose(pt, [.3, 0, .4])
    s = np.array([1, 1, .9, .8, .5]); w = np.array([0, 0, 0, 1, 1])
    assert abs(rc_summary(s, w)["AURC_%"] - 9.0) < 1e-9
    assert op_point(s, np.array([1, 2, 3, 4, 5]), np.array([1, 2, 3, 0, 0]), 0.9) == {"op_coverage_%": 60.0, "op_risk_%": 0.0}
