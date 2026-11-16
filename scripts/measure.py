#!/usr/bin/env python3
"""Control-loop timing report from rtarm tick logs (tick,t_ns,state_seq,estop).

Usage: scripts/measure.py LABEL=out/ticks_a.csv [LABEL=out/ticks_b.csv ...] [--period-us 1000] [--png docs/jitter.png]
Prints period mean / sd / p99 / max and late ticks (> 1.1 x period) for each log, and draws
overlaid period histograms. Numbers come only from the logs given; say in the README what load
and settings each log was recorded under.
"""
import argparse
import csv
import sys

import numpy as np


def load(path):
    with open(path) as f:
        t = np.array([int(r["t_ns"]) for r in csv.DictReader(f)], dtype=np.int64)
    if len(t) < 3:
        sys.exit(f"{path}: fewer than 3 ticks")
    return np.diff(t) / 1e3  # periods in us


def stats(p, period):
    return {
        "ticks": len(p) + 1,
        "mean_us": p.mean(),
        "sd_us": p.std(),
        "p99_us": np.percentile(p, 99),
        "max_us": p.max(),
        "late": int((p > 1.1 * period).sum()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+", help="LABEL=path.csv")
    ap.add_argument("--period-us", type=float, default=1000.0)
    ap.add_argument("--png")
    a = ap.parse_args()
    runs = []
    for item in a.logs:
        label, _, path = item.partition("=")
        if not path:
            label, path = path or item, item
        runs.append((label, load(path)))
    hdr = f"{'run':<28}{'ticks':>7}{'mean':>9}{'sd':>8}{'p99':>9}{'max':>9}{'late':>6}"
    print(hdr + "\n" + "-" * len(hdr))
    for label, p in runs:
        s = stats(p, a.period_us)
        print(f"{label:<28}{s['ticks']:>7}{s['mean_us']:>9.1f}{s['sd_us']:>8.1f}{s['p99_us']:>9.1f}{s['max_us']:>9.1f}{s['late']:>6}")
    print("(us; late = period > 1.1 x nominal)")
    if a.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4.2), dpi=120)
        hi = max(np.percentile(p, 99.9) for _, p in runs)
        bins = np.linspace(0, max(hi, 1.5 * a.period_us), 120)
        for label, p in runs:
            ax.hist(np.clip(p, 0, bins[-1]), bins=bins, histtype="step", linewidth=1.6, label=label)
        ax.axvline(a.period_us, color="k", linestyle=":", linewidth=1)
        ax.set_yscale("log")
        ax.set_xlabel("loop period (us), last bin = everything above")
        ax.set_ylabel("ticks (log)")
        ax.set_title(f"1 kHz control loop period, nominal {a.period_us:.0f} us")
        ax.legend()
        fig.tight_layout()
        fig.savefig(a.png)
        print("wrote", a.png)


if __name__ == "__main__":
    main()
