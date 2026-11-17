#!/usr/bin/env bash
# Stress benchmark on a busy laptop: CPU hogs compete with the 1 kHz controller, same 8 s run each.
#   Linux:   controller + 1 busy-loop hog pinned to the same core, both normal priority (no root here).
#   QNX:     2 busy-loop hogs at priority 10 inside the guest (one per vCPU), controller at default prio 10,
#            then the controller at SCHED priority 50 (-r 50).
# Needs the VM up (taskset -c 12-15 scripts/qemu_boot.sh). Writes out/stress_<stamp>/ + the measure.py table.
set -e; cd "$(dirname "$0")/.."
K=vm-key/id_ed25519; SSH=(ssh -i $K -o IdentitiesOnly=yes -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@127.0.0.1)
D=out/stress_$(date +%m%d_%H%M); mkdir -p "$D"; echo "host load at start $(cut -d' ' -f1-3 /proc/loadavg)" > "$D/load.txt"
# Linux: hog + controller share core 10, plant on core 11 (QEMU threads are on cores 12-15)
taskset -c 10 sh -c 'while :; do :; done' & H=$!
taskset -c 11 .venv/bin/python host/plant.py --listen 127.0.0.1:47400 --log "$D/plant_linux.csv" --duration 9 > "$D/plant_linux.out" 2>&1 & P=$!
sleep 1.5; taskset -c 10 ./build/rtarm-linux -p 127.0.0.1 -P 47400 -s 8 -l "$D/linux_hog.csv" > "$D/rtarm_linux.out" 2>&1 || true
kill $H; wait $P 2>/dev/null || true
# QNX: start 2 hogs at prio 10 in the guest, remember their pids
"${SSH[@]}" 'for i in 1 2; do on -p 10 ksh -c "while :; do :; done" > /dev/null 2>&1 & echo $!; done' > "$D/qnx_hog_pids.txt"
sleep 1
for MODE in noprio prio50; do
  A=""; [ $MODE = prio50 ] && A="-r 50"
  taskset -c 11 .venv/bin/python host/plant.py --listen 127.0.0.1:47400 --log "$D/plant_qnx_$MODE.csv" --duration 9 > "$D/plant_qnx_$MODE.out" 2>&1 & P=$!
  sleep 1.5
  "${SSH[@]}" "/data/home/root/rtarm -p 10.0.2.2 -P 47400 -s 8 $A -l /data/home/root/t_$MODE.csv" > "$D/rtarm_qnx_$MODE.out" 2>&1 || true
  "${SSH[@]}" "cat /data/home/root/t_$MODE.csv" > "$D/qnx_hog_$MODE.csv"
  wait $P 2>/dev/null || true
done
"${SSH[@]}" "pidin -p ksh -f aep | head -20" > "$D/qnx_pidin.txt" 2>&1 || true
"${SSH[@]}" "kill $(tr '\n' ' ' < "$D/qnx_hog_pids.txt")" || true
echo "host load at end $(cut -d' ' -f1-3 /proc/loadavg)" >> "$D/load.txt"
.venv/bin/python scripts/measure.py "Linux + hog=$D/linux_hog.csv" "QNX + hogs, prio 10=$D/qnx_hog_noprio.csv" "QNX + hogs, prio 50=$D/qnx_hog_prio50.csv" --png "$D/jitter.png" | tee "$D/table.txt"
for f in "$D"/plant_*.csv; do echo "$f: $(.venv/bin/python scripts/track_check.py "$f" | tail -1)"; done | tee -a "$D/table.txt"
