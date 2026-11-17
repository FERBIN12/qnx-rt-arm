#!/usr/bin/env bash
# E-stop latency: the plant process exits mid-run (link lost), the controller's 20 ms watchdog must latch e-stop.
# N trials each: Linux + 1 hog on its core (normal prio, no root), QNX + 2 prio-10 hogs with the controller at -r 50.
# Needs the VM up (taskset -c 12-15 scripts/qemu_boot.sh). Usage: scripts/estop_bench.sh [N]
set -e; cd "$(dirname "$0")/.."; N=${1:-10}
K=vm-key/id_ed25519; SSH=(ssh -i $K -o IdentitiesOnly=yes -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@127.0.0.1)
D=out/estop_$(date +%m%d_%H%M); mkdir -p "$D"; echo "host load at start $(cut -d' ' -f1-3 /proc/loadavg)" > "$D/load.txt"
start_plant() {  # plant runs 2.5 s of plant time, then exits = link lost while the controller keeps ticking
  taskset -c 11 .venv/bin/python host/plant.py --listen 127.0.0.1:47400 --log "$D/plant_$1.csv" --duration 2.5 > "$D/plant_$1.out" 2>&1 & P=$!
  sleep 1.5; kill -0 $P 2>/dev/null || { echo "plant did not start (port 47400 in use?)"; cat "$D/plant_$1.out"; exit 1; }
}
taskset -c 10 sh -c 'while :; do :; done' & H=$!
for i in $(seq 1 $N); do
  start_plant linux_$i
  taskset -c 10 ./build/rtarm-linux -p 127.0.0.1 -P 47400 -s 4 -l "$D/linux_$i.csv" > "$D/rtarm_linux_$i.out" 2>&1 || true
  wait $P 2>/dev/null || true
done
kill $H
"${SSH[@]}" 'for i in 1 2; do on -p 10 ksh -c "while :; do :; done" > /dev/null 2>&1 & echo $!; done' > "$D/qnx_hog_pids.txt"
sleep 1
for i in $(seq 1 $N); do
  start_plant qnx_$i
  "${SSH[@]}" "/data/home/root/rtarm -p 10.0.2.2 -P 47400 -s 4 -r 50 -l /data/home/root/e.csv" > "$D/rtarm_qnx_$i.out" 2>&1 || true
  "${SSH[@]}" "cat /data/home/root/e.csv" > "$D/qnx_$i.csv"
  wait $P 2>/dev/null || true
done
"${SSH[@]}" "kill $(tr '\n' ' ' < "$D/qnx_hog_pids.txt")" || true
echo "host load at end $(cut -d' ' -f1-3 /proc/loadavg)" >> "$D/load.txt"
A=(); for i in $(seq 1 $N); do A+=("Linux + hog (normal prio)=$D/linux_$i.csv" "QNX + 2 hogs, ctl prio 50=$D/qnx_$i.csv"); done
.venv/bin/python scripts/estop_latency.py "${A[@]}" | tee "$D/table.txt"
