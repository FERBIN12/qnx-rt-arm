"""Tracking error of a run from out/plant.csv (plant-side log). Prints max/mean joint error after 1 s."""
import csv, sys, numpy as np
r = list(csv.DictReader(open(sys.argv[1] if len(sys.argv) > 1 else "out/plant.csv")))
r = [x for x in r if int(x["braked"]) == 0 and int(x["tick"]) > 0]
q = np.array([[float(x[f"q{i}"]) for i in range(7)] for x in r]); t = np.array([int(x["tick"]) for x in r]) * 1e-3
HOME = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]); ref = np.tile(HOME, (len(t), 1)); w = 2 * np.pi * 0.25
for j, A in [(0, .5), (1, .35), (2, .5), (3, .35)]:
    ref[:, j] += A * np.sin(w * t)
e = np.abs(q - ref)[t > 1.0]
print(f"rows={len(r)} track_err_rad max={e.max():.4f} mean={e.mean():.5f}")
