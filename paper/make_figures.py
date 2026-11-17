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
fig, ax = plt.subplots(figsize=(3.3, 2.0))
ax.plot(u, uni, color=BLUE, lw=1.6, label="uniform disk, radius $R$")
ax.plot(u, gau, color=ORANGE, lw=1.6, ls="--", label="Gaussian, 95% radius $R$")
ax.axvline(1.0, color=GREY, lw=0.8, ls=":")
ax.text(1.02, 0.42, "distance rule\nanswers only\nbeyond $d=R$", fontsize=6.5, color="#4a5568", va="top")
ax.set_xlabel("distance to boundary / error radius  ($d/R$)")
ax.set_ylabel("P(wrong region)")
ax.set_ylim(0, 0.52); ax.set_xlim(0, 1.6)
ax.legend(frameon=False, fontsize=6.5, loc="upper right")
fig.tight_layout(); fig.savefig(f"{OUT}/fig1_theory.pdf"); plt.close(fig)

# ---------------------------------------------------------------- Fig. 2: real vs random-direction error
# addresses within 50 m of a tract line; real Census geocodes vs the same displacement lengths in random directions
rows = [  # label, real %, random-direction %, source
    ("NYC\n(PLUTO)", 0.33, 8.7),            # EXP11
    ("NYC\n(Addr. Pts.)", 0.97, 15.0),      # EXP11
    ("Utah\nSalt Lake", 0.72, 11.7),        # EXP15 U1/U5
    ("Utah\n6 rural", 2.03, 10.8),          # EXP15 U5 (geocoded truth removed)
    ("National\n18 counties", 1.57, 20.2),  # EXP16 G4
]
x = np.arange(len(rows)); w = 0.38
fig, ax = plt.subplots(figsize=(3.4, 2.0))
ax.bar(x - w / 2, [r[1] for r in rows], w, color=BLUE, label="real Census geocode")
ax.bar(x + w / 2, [r[2] for r in rows], w, color=GREY, label="same error, random direction")
for i, r in enumerate(rows):
    ax.text(i - w / 2, r[1] + 0.4, f"{r[1]:.2g}", ha="center", fontsize=6)
    ax.text(i + w / 2, r[2] + 0.4, f"{r[2]:.3g}", ha="center", fontsize=6)
ax.set_xticks(x); ax.set_xticklabels([r[0] for r in rows], fontsize=6.5)
ax.set_ylabel("wrong tract (%)")
ax.legend(frameon=False, fontsize=6.5, loc="upper left")
fig.tight_layout(); fig.savefig(f"{OUT}/fig2_direction.pdf"); plt.close(fig)
print("wrote", os.listdir(OUT))
