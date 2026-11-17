#!/usr/bin/env bash
# The live terminal part of the demo video: QNX 8.0 guest under QEMU, 2 CPU hogs, controller at prio 10 then prio 50.
# Needs the VM up (taskset -c 12-15 scripts/qemu_boot.sh). Writes out/demo_<stamp>/.
cd "$(dirname "$0")/.."
K=vm-key/id_ed25519; SSH=(ssh -i $K -o IdentitiesOnly=yes -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@127.0.0.1)
D=out/demo_$(date +%m%d_%H%M); mkdir -p "$D"
note() { printf '\n\033[1;33m# %s\033[0m\n' "$*"; sleep 1.2; }
qnx()  { printf '\033[1;32mroot@qnx#\033[0m %s\n' "$1"; sleep 0.8; "${SSH[@]}" "$1"; sleep 1.5; }
host() { printf '\033[1;36mhost$\033[0m %s\n' "$1"; sleep 0.8; eval "$1"; sleep 1.5; }
clear
note "QNX 8.0 guest in QEMU (ssh), the controller binary built with qcc"
qnx "uname -a"
qnx "ls -l /data/home/root/rtarm"
note "Start 2 busy-loop CPU hogs at priority 10, one per vCPU"
"${SSH[@]}" 'rm -f /tmp/hogs'
qnx 'for i in 1 2; do on -p 10 ksh -c "while :; do :; done" >/dev/null 2>&1 & echo $! >>/tmp/hogs; done'
qnx 'pidin -p ksh -f abp   # 2 hogs + this ssh shell'

for MODE in prio10 prio50; do
  A=""; [ $MODE = prio50 ] && A="-r 50"
  note "Run: 1 kHz controller at $([ $MODE = prio50 ] && echo 'priority 50 (above the hogs)' || echo 'priority 10 (same as the hogs)'), MuJoCo arm on the host, 8000 ticks"
  .venv/bin/python host/plant.py --listen 127.0.0.1:47400 --log "$D/plant_$MODE.csv" --duration $([ $MODE = prio50 ] && echo 9 || echo 70) > "$D/plant_$MODE.out" 2>&1 & P=$!
  sleep 1.5
  qnx "/data/home/root/rtarm -p 10.0.2.2 -P 47400 -s 8 $A -l /data/home/root/d_$MODE.csv"
  "${SSH[@]}" "cat /data/home/root/d_$MODE.csv" > "$D/qnx_$MODE.csv"; kill $P 2>/dev/null; wait $P 2>/dev/null
done
"${SSH[@]}" 'kill $(cat /tmp/hogs)' 2>/dev/null || true
note "Loop period, measured from the tick logs just written"
host ".venv/bin/python scripts/measure.py 'QNX + 2 hogs, prio 10=$D/qnx_prio10.csv' 'QNX + 2 hogs, prio 50=$D/qnx_prio50.csv' | tee $D/table.txt"
sleep 6
