"""Run the V2 experiments in order. Each step skips work whose raw outputs already exist.

    python experiments/run_all.py                 # EXP01 -> EXP10
    python experiments/run_all.py 2 3             # only EXP02 and EXP03
    python experiments/run_all.py --skip-nyc      # everything except the internet-dependent EXP04
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = {"1": "exp01_v2_main.py", "2": "exp02_geometry.py", "3": "exp03_gaussian_overlay.py", "4": "exp04_nyc_real.py",
         "4b": "exp04b_nyc_mechanism.py", "5": "exp05_mc_convergence.py", "6": "exp06_geometry_stress.py",
         "7": "exp07_heavy_tails.py", "8": "exp08_stats.py", "9": "exp09_nyc_streets.py",
         "10": "exp10_output_categories.py"}

args = [a for a in sys.argv[1:] if not a.startswith("--")]
todo = args or list(STEPS)
if "--skip-nyc" in sys.argv:
    todo = [k for k in todo if k not in ("4", "4b", "9")]
for k in todo:
    t = time.time()
    print(f"\n{'=' * 80}\nRUNNING {STEPS[k]}\n{'=' * 80}", flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, STEPS[k])])
    if r.returncode != 0:
        sys.exit(f"{STEPS[k]} failed (exit {r.returncode}) — stopping.")
    print(f"{STEPS[k]} finished in {time.time() - t:.0f}s")
print("\nAll done. Summaries: results/*/summary.txt")
