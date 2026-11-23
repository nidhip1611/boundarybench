"""Figures for the ICICT 2027 paper. Numbers are copied from results/*/summary.txt (source noted per value).
    python paper/make_figures.py   -> paper/figures/*.pdf
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import norm

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.size": 8, "font.family": "serif", "axes.spines.top": False, "axes.spines.right": False})
INK, BLUE, ORANGE, GREY = "#222222", "#2b6cb0", "#dd6b20", "#a0aec0"

# ---------------------------------------------------------------- Fig. 1: straight-boundary theory
u = np.linspace(0, 1.6, 400)
uni = np.where(u < 1, (np.arccos(np.clip(u, 0, 1)) - u * np.sqrt(np.clip(1 - u ** 2, 0, 1))) / np.pi, 0)
gau = norm.sf(u * 2.4477)                      # sigma = R / 2.4477
fig, ax = plt.subplots(figsize=(3.6, 1.85))
ax.plot(u, uni, color=BLUE, lw=1.6, label="uniform disk, radius $R$")
ax.plot(u, gau, color=ORANGE, lw=1.6, ls="--", label="Gaussian, 95% radius $R$")
# observed benchmark rates by d/R bin (results/v2_geometry/summary.txt, [G1], layers pooled)
mid = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 1.125, 1.375]
obs_uni = [46.236, 40.451, 33.796, 28.061, 21.359, 16.829, 10.916, 7.586, 2.888, 0.743, 0.0, 0.0]
obs_gau = [45.424, 34.585, 26.499, 19.606, 13.708, 9.471, 5.458, 3.190, 1.926, 0.885, 0.422, 0.081]
ax.plot(mid, np.array(obs_uni) / 100, "o", color=BLUE, ms=3, label="observed (uniform)")
ax.plot(mid, np.array(obs_gau) / 100, "s", color=ORANGE, ms=3, mfc="white", label="observed (Gaussian)")
ax.axvline(1.0, color=GREY, lw=0.8, ls=":")
ax.text(1.04, 0.19, "uniform error:\nno crossing for\n$d_{\\mathrm{true}}\\geq R$", fontsize=6.5, color="#4a5568", va="top")
ax.set_xlabel(r"true distance to boundary / error radius  ($d_{\mathrm{true}}/R$)")
ax.set_ylabel("P(wrong region)")
ax.set_ylim(0, 0.52); ax.set_xlim(0, 1.6)
ax.legend(frameon=False, fontsize=6.5, loc="upper right")
fig.tight_layout(); fig.savefig(f"{OUT}/fig1_theory.pdf"); plt.close(fig)

# ---------------------------------------------------------------- Fig. 2: real vs random-direction error
# addresses within 50 m of a tract line; real Census geocodes vs the same displacement lengths in random directions
rows = [  # label, real %, random-direction %, source
    ("NYC\n(PLUTO)", 0.04, 11.5),           # EXP09 Wilson n=2,478 / EXP11 near-line
    ("NYC\n(Addr. Pts.)", 0.97, 15.0),      # EXP09 n=1,443 / EXP11 near-line
    ("Utah\nSalt Lake", 0.72, 11.7),        # EXP15 U1/U5
    ("Utah\n6 rural", 2.03, 10.8),          # EXP15 U5 (geocoded truth removed)
    ("18 sampled\ncounties", 1.57, 20.2),  # EXP16 G4
]
x = np.arange(len(rows)); w = 0.38
fig, ax = plt.subplots(figsize=(3.8, 1.75))
ax.bar(x - w / 2, [r[1] for r in rows], w, color=BLUE, label="real Census geocode")
ax.bar(x + w / 2, [r[2] for r in rows], w, color=GREY, label="same error, random direction")
for i, r in enumerate(rows):
    ax.text(i - w / 2, r[1] + 0.4, f"{r[1]:g}", ha="center", fontsize=6)
    ax.text(i + w / 2, r[2] + 0.4, f"{r[2]:.1f}", ha="center", fontsize=6)
ax.set_xticks(x); ax.set_xticklabels([r[0] for r in rows], fontsize=6.5)
ax.set_ylabel("wrong tract (%)")
ax.set_ylim(0, 25)
ax.legend(frameon=False, fontsize=6.5, loc="upper left")
fig.tight_layout(); fig.savefig(f"{OUT}/fig2_direction.pdf"); plt.close(fig)
print("wrote", os.listdir(OUT))

# ---------------------------------------------------------------- Fig. 3 (used as Fig. 1 from round 4): direction test
# results/v2_realdata_reconcile/P7_along_vs_across.csv (clear segment matches); read directly so values cannot drift
import re
import pandas as pd
P7 = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "results", "v2_realdata_reconcile", "P7_along_vs_across.csv"))
P7 = P7[P7["group"] != "ALL"]
lab = {"NYC, PLUTO": "NYC\nPLUTO", "NYC, Address Points": "NYC addr.\npoints", "Utah, Salt Lake County": "Salt Lake\nCounty",
       "Utah, six rural counties": "rural\nUtah", "National, largest-coverage counties": "largest\ncounties",
       "National, smaller counties": "smaller\ncounties"}


def parse(s):
    v, lo, hi = map(float, re.findall(r"[-\d.]+", s)); return v, v - lo, hi - v


series = [("actual_wrong_%", "observed", INK), ("along_street_%", "along street", BLUE),
          ("random_direction_%", "random direction", GREY), ("across_street_%", "across street", ORANGE)]
fig, ax = plt.subplots(figsize=(4.8, 1.95))
x = np.arange(len(P7)); w = 0.2
for j, (col, name, colr) in enumerate(series):
    v = np.array([parse(s) for s in P7[col]])
    ax.bar(x + (j - 1.5) * w, v[:, 0], w, color=colr, label=name, yerr=v[:, 1:].T, error_kw={"lw": 0.6, "capsize": 1.2})

obs = [parse(v)[0] for v in P7["actual_wrong_%"]]
ax.set_xticks(x); ax.set_xticklabels([f"{lab[g]}\nobs. {o:.2f}%" for g, o in zip(P7["group"], obs)], fontsize=7.2)
ax.set_ylabel("tract disagreement (%)", fontsize=8); ax.tick_params(axis="y", labelsize=7.5)
ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper left", handlelength=1.2, columnspacing=1.0)
ax.set_ylim(0, 38)
fig.tight_layout(); fig.savefig(f"{OUT}/fig3_direction_test.pdf"); fig.savefig("/tmp/fig3.png", dpi=200); plt.close(fig)

# ---------------------------------------------------------------- Fig. 2 (round 6): block-face mechanism schematic
fig, ax = plt.subplots(figsize=(4.8, 2.05))
ax.set_xlim(-1, 21); ax.set_ylim(-5.2, 5.6); ax.axis("off")
ax.axhspan(0, 5.6, xmin=0, xmax=1, color="#ebf4ff", zorder=0); ax.axhspan(-5.2, 0, color="#fff5eb", zorder=0)
ax.axvspan(11, 21, ymin=5.2 / 10.8, ymax=1, color="#e6fffa", zorder=0)
ax.plot([-1, 21], [0, 0], color=GREY, lw=5, solid_capstyle="butt", zorder=1)                 # main street
for xv in (0, 11):
    ax.plot([xv, xv], [-5.2, 5.6], color=GREY, lw=5, zorder=1)                                 # cross streets
ax.plot([-1, 21], [0, 0], color="#c53030", lw=1.2, ls="--", zorder=4)                            # tract line on street
ax.plot([11, 11], [0, 5.6], color="#c53030", lw=1.2, ls="--", zorder=2)
ax.plot([0.3, 10.7], [0.0, 0.0], color=BLUE, lw=3.4, zorder=3)                                  # matched edge (centerline)
ax.plot([0.3, 10.7], [1.3, 1.3], color=BLUE, lw=0.8, ls=":", zorder=3)                         # offset on reported side
ax.text(0.5, 2.2, "block face: matched edge, reported side", ha="left", fontsize=6.3, color=BLUE)
ax.text(-0.6, 4.7, "Tract A", fontsize=7, color="#2c5282"); ax.text(1.0, -4.8, "Tract B", fontsize=7, color="#9c4221")
ax.text(19.2, 4.7, "Tract C", fontsize=7, color="#285e61", ha="right")
def mark(x, y, kind, lab, dx=0.3, dy=0.45):
    if kind == "ref":
        ax.plot(x, y, "s", ms=5, mfc="white", mec=INK, zorder=4)
    else:
        ax.plot(x, y, "o", ms=5, color=ORANGE, zorder=4)
    ax.text(x + dx, y + dy, lab, fontsize=6.3, color=INK, bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.85), zorder=6)
mark(3.0, 3.2, "ref", "R1"); mark(3.8, 1.3, "geo", "G1", dy=0.35)
mark(7.0, -3.2, "ref", "R2"); mark(7.2, 1.3, "geo", "G2", dy=0.35)
ax.annotate("", xy=(7.15, 1.05), xytext=(7.0, -2.9), arrowprops=dict(arrowstyle="->", lw=0.6, color=INK))
mark(15.0, 3.0, "ref", "R3"); mark(9.4, 1.3, "geo", "G3", dx=-1.1, dy=0.35)
ax.annotate("", xy=(9.6, 1.5), xytext=(14.7, 2.9), arrowprops=dict(arrowstyle="->", lw=0.6, color=INK))
ax.text(12.0, -0.45, "R1, G1: reference on the matched face, same tract\nR2, G2: other side of the street, tract differs\nR3, G3: neighboring block face, tract differs",
        fontsize=6.2, color=INK, va="top")
ax.plot([], [], "s", ms=5, mfc="white", mec=INK, label="reference point"); ax.plot([], [], "o", ms=5, color=ORANGE, label="Census geocode")
ax.plot([], [], color="#c53030", ls="--", lw=1.2, label="tract line")
ax.plot([], [], color=BLUE, lw=2.6, label="matched edge")
ax.legend(frameon=False, fontsize=6.3, loc="lower right", bbox_to_anchor=(1.0, -0.06), ncol=2, handlelength=1.4, columnspacing=0.8)
fig.tight_layout(pad=0.2); fig.savefig(f"{OUT}/fig2_mechanism.pdf"); fig.savefig("/tmp/fig2.png", dpi=200); plt.close(fig)
