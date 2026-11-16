#!/usr/bin/env bash
# Quiet-host benchmark: only runs when the 1-min load average is below 2 (busy-host numbers are noise).
# Needs the QEMU VM up (scripts/qemu_boot.sh). Writes out/night_<stamp>/ and prints the measure.py table.
set -e; cd "$(dirname "$0")/.."
L=$(cut -d' ' -f1 /proc/loadavg)
if awk "BEGIN{exit !($L >= 2)}"; then echo "load $L >= 2, not measuring"; exit 3; fi
D=out/night_$(date +%m%d_%H%M); mkdir -p "$D"; echo "load at start $L" > "$D/load.txt"
scripts/run_local.sh 8 && cp out/ticks_linux.csv "$D/linux.csv"
scripts/run_qnx.sh 8 && cp out/ticks_qnx.csv "$D/qnx_noprio.csv"
RTARGS="-r 50" scripts/run_qnx.sh 8 && cp out/ticks_qnx.csv "$D/qnx_prio50.csv"
echo "load at end $(cut -d' ' -f1 /proc/loadavg)" >> "$D/load.txt"
.venv/bin/python scripts/measure.py "Linux=$D/linux.csv" "QNX no prio=$D/qnx_noprio.csv" "QNX prio 50=$D/qnx_prio50.csv" --png "$D/jitter.png" | tee "$D/table.txt"
