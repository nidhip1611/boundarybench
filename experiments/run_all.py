"""Run the V2 experiments in order. Each step skips work whose raw outputs already exist.

    python experiments/run_all.py                 # EXP01 -> EXP16
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
         "10": "exp10_output_categories.py", "11": "exp11_direction_counterfactual.py",
         "12": "exp12_heldout_geography.py", "13": "exp13_nyc_sensitivity.py", "14": "exp14_cartographic_boundaries.py",
         "15": "exp15_utah_transfer.py", "16": "exp16_national_transfer.py",
         "17": "exp17_matched_operating_points.py", "18": "exp18_realdata_mechanism.py",
         "19": "exp19_realdata_reconcile.py", "20": "exp20_heldout_folds.py",
         "21": "exp21_realdata_sensitivity.py",
         "22": "exp22_matched_edge.py",
         "23": "exp23_blocks_policy_flags.py",
         "24": "exp24_sim_clustered.py", "25": "exp25_reference_sensitivity.py",
         "26": "exp26_paired_gap.py"}

args = [a for a in sys.argv[1:] if not a.startswith("--")]
todo = args or list(STEPS)
if "--skip-nyc" in sys.argv:
    todo = [k for k in todo if k not in ("4", "4b", "9", "11", "13", "15", "16", "18", "19", "21", "22", "23", "25")]
for k in todo:
    t = time.time()
    print(f"\n{'=' * 80}\nRUNNING {STEPS[k]}\n{'=' * 80}", flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, STEPS[k])])
    if r.returncode != 0:
        sys.exit(f"{STEPS[k]} failed (exit {r.returncode}) — stopping.")
    print(f"{STEPS[k]} finished in {time.time() - t:.0f}s")
print("\nAll done. Summaries: results/*/summary.txt")
