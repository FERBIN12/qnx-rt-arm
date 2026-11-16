# rt-arm: a hard real-time arm controller on QNX 8.0, closed over UDP with a MuJoCo robot

Work in progress for the QNX Global Hackathon 2026 (Robotics & Medical).

- `controller/rtarm.c`: 1 kHz joint PD + gravity compensation, watchdog e-stop. QNX build uses a timer pulse on a
  channel + SCHED_FIFO; Linux build uses `clock_nanosleep` as the baseline.
- `host/plant.py`: Franka Panda simulated in MuJoCo with 7 torque motors, one 1 ms step per command packet,
  plant-side brake if commands stop.

Quick local check (Linux, no QNX): `python3 -m venv .venv && .venv/bin/pip install mujoco numpy && make linux && scripts/run_local.sh 8`

## Credits
- MuJoCo (Apache-2.0), DeepMind.
- Franka Emika Panda model from MuJoCo Menagerie (Apache-2.0).
- Built with AI-assisted development (Claude Code); all numbers come from logged runs in this repo's scripts.
