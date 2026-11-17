"""One histogram panel per run (shared x axis) so no run hides another. usage: plot_panels.py out.png "label=ticks.csv" ..."""
import csv, sys
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
out, runs = sys.argv[1], [a.rsplit("=", 1) for a in sys.argv[2:]]
fig, axs = plt.subplots(len(runs), 1, figsize=(9, 2.2 * len(runs)), sharex=True)
bins = np.arange(0, 16050, 50)
for ax, (label, path) in zip(np.atleast_1d(axs), runs):
    t = np.array([int(r["t_ns"]) for r in csv.DictReader(open(path))], dtype=np.int64)
    p = np.diff(t) / 1000.0
    ax.hist(np.clip(p, 0, 16000), bins=bins, color="#2f5d8a")
    ax.set_yscale("log"); ax.axvline(1000, ls=":", c="k")
    late = int((p > 1100).sum())
    ax.set_title(f"{label}: sd {p.std():.1f} us, {late}/{len(p)} late (> 1.1 ms)", fontsize=10, loc="left")
    ax.set_ylabel("ticks")
axs[-1].set_xlabel("loop period (us), nominal 1000 us (dotted); last bin = 16000 us and above")
fig.tight_layout(); fig.savefig(out, dpi=110)
