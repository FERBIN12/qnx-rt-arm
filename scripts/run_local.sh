#!/usr/bin/env bash
# Closed loop on one Linux machine: MuJoCo plant + Linux build of the controller. Usage: scripts/run_local.sh [secs]
set -e; cd "$(dirname "$0")/.."; S=${1:-8}; mkdir -p out
.venv/bin/python host/plant.py --listen 127.0.0.1:47400 --log out/plant.csv --duration $((S+1)) > out/plant.out 2>&1 &
P=$!; sleep 1.5
./build/rtarm-linux -p 127.0.0.1 -P 47400 -s "$S" -l out/ticks_linux.csv
sleep 1; kill $P 2>/dev/null || true; tail -1 out/plant.out
.venv/bin/python scripts/track_check.py out/plant.csv
