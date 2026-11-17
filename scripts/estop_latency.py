"""E-stop latency from rtarm tick logs (tick,t_ns,state_seq,estop).
Latency = controller time from the last tick that drained a fresh plant state to the tick that latched the
watchdog e-stop. The watchdog limit is -w (default 20 ms), so a perfect loop reads 20-21 ms every trial.
Usage: estop_latency.py label=file.csv [label=file.csv ...]"""
import csv, statistics, sys

def latency(path):
    rows = list(csv.DictReader(open(path)))
    last_fresh_t, prev_seq = None, 0
    for r in rows:
        seq, t, es = int(r["state_seq"]), int(r["t_ns"]), int(r["estop"])
        if es:
            return None if last_fresh_t is None else (t - last_fresh_t) / 1e6
        if seq != prev_seq:
            last_fresh_t, prev_seq = t, seq
    return None  # no e-stop in this log

groups = {}
for arg in sys.argv[1:]:
    label, path = arg.split("=", 1)
    groups.setdefault(label, []).append(latency(path))
print(f"{'run':34s} {'trials':>6s} {'estops':>6s} {'min ms':>7s} {'mean ms':>8s} {'max ms':>7s}")
for label, v in groups.items():
    ok = [x for x in v if x is not None]
    if ok:
        print(f"{label:34s} {len(v):6d} {len(ok):6d} {min(ok):7.2f} {statistics.mean(ok):8.2f} {max(ok):7.2f}")
    else:
        print(f"{label:34s} {len(v):6d} {0:6d}  (no e-stop latched)")
