#!/usr/bin/env bash
# Closed loop: MuJoCo plant on the Linux host + QNX 8.0 build of the controller inside QEMU.
# Needs the VM booted (scripts/qemu_boot.sh). Usage: scripts/run_qnx.sh [secs]
set -e; cd "$(dirname "$0")/.."; S=${1:-8}; mkdir -p out
K=vm-key/id_ed25519; SSH=(ssh -i $K -o IdentitiesOnly=yes -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@127.0.0.1)
scp -i $K -o IdentitiesOnly=yes -P 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR build/rtarm-qnx root@127.0.0.1:/data/home/root/rtarm
.venv/bin/python host/plant.py --listen 127.0.0.1:47400 --log out/plant_qnx.csv --duration $((S+1)) > out/plant_qnx.out 2>&1 &
P=$!; sleep 1.5
"${SSH[@]}" "uname -a; /data/home/root/rtarm -p 10.0.2.2 -P 47400 -s $S ${RTARGS:-} -l /data/home/root/ticks_qnx.csv"
"${SSH[@]}" "cat /data/home/root/ticks_qnx.csv" > out/ticks_qnx.csv
sleep 1; kill $P 2>/dev/null || true; tail -1 out/plant_qnx.out
.venv/bin/python scripts/track_check.py out/plant_qnx.csv
