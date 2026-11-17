# rt-arm: a hard real-time arm controller on QNX 8.0, closed over UDP with a MuJoCo robot

A 1 kHz joint controller (PD + gravity compensation, watchdog e-stop) runs on **QNX 8.0** inside QEMU and
drives a simulated **Franka Panda** arm in MuJoCo over UDP. The same C file also builds on Linux, so you can
measure, side by side, what a real-time OS buys you when the CPU is busy.

**Measured result** (8 s runs, 8000 ticks each, busy host, tick logs + summaries in `results/`, produced by
`scripts/stress_bench.sh`):

| Run | mean period | std dev | p99 | max | late ticks (> 1.1 ms) |
|---|---|---|---|---|---|
| Linux, controller + 1 CPU hog on the same core, normal priority | 999.7 us | 247.1 us | 1646.7 us | 4660.5 us | 88 / 8000 |
| QNX 8.0, 2 CPU hogs at prio 10, controller at prio 10 | 7097.9 us | 2566.9 us | 15981.0 us | 19996.9 us | 7999 / 8000 |
| QNX 8.0, 2 CPU hogs at prio 10, controller at **prio 50** | **1000.0 us** | **5.9 us** | **1013.5 us** | **1114.7 us** | **1 / 8000** |

Read it honestly: the Linux run is plain `SCHED_OTHER` (this laptop has no root for `SCHED_FIFO`), so it is
"Linux as most people run it", not tuned PREEMPT_RT. The middle row is the point of QNX scheduling: at the same
priority as the hogs the controller only gets round-robin slices and misses almost every deadline; one priority
number later it is the most important thread in the system and holds 1 ms within a few microseconds. The host
was a busy laptop with QEMU pinned to 4 cores. Host load averages: 6.3 to 7.8 during the QNX runs
(`results/stress_1117_0039/load.txt`) and 8.9 to 11.0 during the Linux run (`results/stress_linux_1117_0340/`).
The Linux row was rerun on its own because the plant failed to start in the first combined run; the reason and
both sets of files are kept in `results/` (see `NOTE.txt`).

## Architecture

```
  QNX 8.0 guest (QEMU/KVM, 2 vCPU)                    Linux host
 +--------------------------------+   UDP 47400    +---------------------------------+
 | rtarm (controller/rtarm.c)     | <------------  | host/plant.py (MuJoCo, Panda)   |
 |  timer -> pulse -> channel     |  joint state   |  7 torque motors                |
 |  MsgReceivePulse every 1 ms    |  ------------> |  1 physics step (1 ms) per      |
 |  PD + gravity comp, watchdog   |  torque cmd    |  command, brake if cmds stop    |
 +--------------------------------+                +---------------------------------+
```

- `controller/proto.h`: the packet layout (state: q, qd, gravity torques, seq; command: tau, seq, tick, flags).
- `controller/rtarm.c`: QNX path = POSIX timer delivering a **pulse** to a private channel, thread at
  `SCHED_FIFO` priority `-r`. Linux path = `clock_nanosleep(TIMER_ABSTIME)`. Watchdog: no fresh state for
  `-w` ms (default 20) -> latch e-stop (damping + gravity only, flag sent to the plant).
- `host/plant.py`: MuJoCo Panda from MuJoCo Menagerie, steps once per received command, logs tracking error.
- `scripts/measure.py`: period statistics + histogram from the controller's tick logs.

## Codelab: build it and measure it yourself

### Step 1. Get QNX SDP 8.0 (free, non-commercial)

1. Create a myQNX account and request the free **QNX Everywhere** non-commercial license
   (https://www.qnx.com/products/everywhere/). Accept and deploy it in the License Manager.
2. Install the **QNX Software Center**, then install *QNX SDP 8.0* (about 3.6 GB).
3. In every shell where you build: `source ~/qnx800/qnxsdp-env.sh` (adjust the path to your install).

### Step 2. Build a QEMU target image

```bash
mkdir -p vm-key && ssh-keygen -t ed25519 -N '' -f vm-key/id_ed25519
mkdir -p vm && cd vm && mkqnximage --type=qemu --hostname=rtarm --sys-size=256 --data-size=64 \
    --ssh-ident=$PWD/../vm-key/id_ed25519.pub && cd ..
```

`mkqnximage` (part of SDP 8.0) writes `vm/output/ifs.bin` and a disk image. `scripts/qemu_boot.sh` boots it with
KVM and user-mode networking, so no root or bridge is needed: the guest reaches the host at `10.0.2.2`, and the
host reaches the guest's ssh at `localhost:2222`. The scripts use the key in `vm-key/`.

### Step 3. Build the controller for QNX and for Linux

```bash
make qnx     # qcc -Vgcc_ntox86_64 ... -lm -lsocket  -> build/rtarm-qnx
make linux   # gcc baseline                         -> build/rtarm-linux
```

The only QNX-specific code is the tick source, about 15 lines:

```c
chid = ChannelCreate(_NTO_CHF_PRIVATE);
int coid = ConnectAttach(0, 0, chid, _NTO_SIDE_CHANNEL, 0);
struct sigevent ev; SIGEV_PULSE_INIT(&ev, coid, pprio, _PULSE_CODE_MINAVAIL, 0);
timer_create(CLOCK_MONOTONIC, &ev, &tid);              /* fires every 1 ms */
...
MsgReceivePulse(chid, &p, sizeof p, NULL);             /* the loop blocks here each tick */
```

### Step 4. Run the closed loop

```bash
python3 -m venv .venv && .venv/bin/pip install mujoco numpy && scripts/get_menagerie.sh
scripts/qemu_boot.sh &          # boot QNX, wait until ssh on localhost:2222 answers
scripts/run_qnx.sh 8            # copies rtarm into the guest, runs 8 s against the MuJoCo plant
```

`run_qnx.sh` prints the controller summary (`ticks=8000 period_us mean=... sd=... late>1.1ms=...`) and the
plant's tracking error. Without QNX you can still try the Linux build: `make linux && scripts/run_local.sh 8`.

### Step 5. Load the CPU and compare

`scripts/stress_bench.sh` starts busy-loop hogs (inside the guest with `on -p 10`, and on the Linux core),
runs Linux, QNX at prio 10 and QNX at prio 50, then writes `out/stress_<stamp>/table.txt` and a histogram.
Run it yourself and compare with the table above; your numbers will differ with your hardware and load.

### The bug worth learning from: pulse priority

The first version used `SIGEV_PULSE_PRIO_INHERIT` for the timer pulse. On QNX the thread that receives a pulse
runs at **the pulse's priority**, so after every `MsgReceivePulse` the controller dropped back to priority 10 and
shared round-robin with the prio-10 hogs, even when started with `-r 50`: periods of about 7 ms. The fix is to set
the pulse priority explicitly to the thread's priority (`SIGEV_PULSE_INIT(&ev, coid, pprio, ...)` with
`pprio = -r`). That single argument is the difference between rows 2 and 3 being a fair test or not.

A side observation from the logs: with low-priority hogs running, QNX jitter was *lower* (sd 19 to 35 us) than on
an idle guest (sd 67 us). Our reading is that an idle vCPU halts and its wake-up exit through KVM adds latency;
a busy vCPU does not. This is a QEMU/KVM effect, not a QNX one, and real hardware would differ.

## Limits

- QEMU/KVM on a busy laptop, not real hardware: the host scheduler still sits under the guest. The point is the
  relative behaviour under load, not absolute microseconds.
- The plant runs on Linux and steps once per command, so it does not model sensor latency or a real arm's
  dynamics limits. It is a test harness for the controller's timing and safety logic.
- The Linux baseline is not `SCHED_FIFO` / PREEMPT_RT (no root on the test machine).

## Credits

- [MuJoCo](https://github.com/google-deepmind/mujoco) (Apache-2.0), Google DeepMind.
- Franka Emika Panda model from [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie)
  (Apache-2.0), fetched by `scripts/get_menagerie.sh`, not committed.
- QNX SDP 8.0 under the QNX Everywhere non-commercial license (not redistributed here).
- Built with Claude Code (an AI coding agent) directed by Ferbin. Every number in this README comes from logged
  runs produced by the scripts in this repo.

License: MIT (see `LICENSE`).
