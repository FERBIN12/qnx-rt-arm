"""MuJoCo plant for rt-arm: Franka Panda (MuJoCo Menagerie, Apache-2.0) with torque motors.

Each command packet from the controller applies tau, advances the plant by one 1 ms step, and answers with a state
packet. If commands stop for --brake-ms, the plant engages a joint brake (high damping) on its own.
    python host/plant.py --listen 0.0.0.0:47400 [--render out/frames] [--log out/plant.csv]
"""
import argparse, pathlib, socket, struct, time, os
import numpy as np
import mujoco

NJ = 7
STATE = struct.Struct("<II" + "d" * (1 + 3 * NJ))
CMD = struct.Struct("<IIIIQ" + "d" * NJ)
STATE_MAGIC, CMD_MAGIC = 0x52544153, 0x52544143
HOME = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785])


def menagerie_panda() -> pathlib.Path:
    env = os.environ.get("MENAGERIE")
    cands = [pathlib.Path(env)] if env else []
    cands += [pathlib.Path.home() / ".cache/robot_descriptions/mujoco_menagerie", pathlib.Path("third_party/mujoco_menagerie")]
    for c in cands:
        p = c / "franka_emika_panda" / "panda_nohand.xml"
        if p.exists():
            return p
    raise SystemExit("MuJoCo Menagerie not found: run scripts/get_menagerie.sh or set MENAGERIE=/path")


def build_model():
    spec = mujoco.MjSpec.from_file(str(menagerie_panda()))
    for a in list(spec.actuators):
        spec.delete(a)
    lim = [87, 87, 87, 87, 12, 12, 12]
    for i, j in enumerate(spec.joints):
        if i >= NJ:
            break
        a = spec.add_actuator(name=f"tau{i+1}", target=j.name, trntype=mujoco.mjtTrn.mjTRN_JOINT)
        a.ctrllimited = True
        a.ctrlrange = [-lim[i], lim[i]]
        a.gear[0] = 1.0
    spec.option.timestep = 0.001
    # floor + light for the renders
    w = spec.worldbody
    w.add_geom(type=mujoco.mjtGeom.mjGEOM_PLANE, size=[1.5, 1.5, 0.05], rgba=[0.82, 0.84, 0.86, 1])
    w.add_light(pos=[0.5, -0.5, 2.0], dir=[-0.2, 0.2, -1])
    return spec.compile()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", default="0.0.0.0:47400")
    ap.add_argument("--brake-ms", type=float, default=50.0)
    ap.add_argument("--log", default="")
    ap.add_argument("--render", default="", help="dir for PNG frames at 30 fps of plant time")
    ap.add_argument("--duration", type=float, default=0.0, help="exit after this many plant seconds (0 = forever)")
    a = ap.parse_args()
    m = build_model(); d = mujoco.MjData(m)
    d.qpos[:NJ] = HOME; mujoco.mj_forward(m, d)
    host, port = a.listen.split(":")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind((host, int(port))); s.settimeout(a.brake_ms / 1000.0)
    log = open(a.log, "w") if a.log else None
    if log:
        log.write("wall_ns,seq,tick,t_ctrl_ns,flags,braked," + ",".join(f"q{i}" for i in range(NJ)) + "," + ",".join(f"tau{i}" for i in range(NJ)) + "\n")
    rnd = None
    if a.render:
        pathlib.Path(a.render).mkdir(parents=True, exist_ok=True)
        rnd = mujoco.Renderer(m, 720, 1280); cam = mujoco.MjvCamera(); cam.lookat[:] = [0.3, 0, 0.45]; cam.distance = 1.9; cam.azimuth = 135; cam.elevation = -18
        next_frame = 0.0; frame = 0
    seq, peer, braked = 0, None, False
    print(f"plant: Panda, 7 torque motors, dt=1 ms, listening on {a.listen}", flush=True)
    while True:
        try:
            pkt, src = s.recvfrom(4096)
            if len(pkt) != CMD.size:
                continue
            f = CMD.unpack(pkt)
            if f[0] != CMD_MAGIC:
                continue
            peer = src; braked = False
            d.ctrl[:NJ] = f[5:5 + NJ]; flags, tick, tctrl = f[2], f[3], f[4]
        except socket.timeout:
            if peer is None:
                continue
            # link lost: plant-side brake, keep stepping in wall time so the arm visibly stops
            braked = True; flags, tick, tctrl = 0, 0, 0
            d.ctrl[:NJ] = d.qfrc_bias[:NJ] - 40.0 * d.qvel[:NJ]
        mujoco.mj_step(m, d); seq += 1
        out = STATE.pack(STATE_MAGIC, seq, d.time, *d.qpos[:NJ], *d.qvel[:NJ], *d.qfrc_bias[:NJ])
        if peer:
            s.sendto(out, peer)
        if log:
            log.write(f"{time.monotonic_ns()},{seq},{tick},{tctrl},{flags},{int(braked)}," + ",".join(f"{x:.5f}" for x in d.qpos[:NJ]) + "," + ",".join(f"{x:.3f}" for x in d.ctrl[:NJ]) + "\n")
        if rnd and d.time >= next_frame:
            rnd.update_scene(d, cam); import PIL.Image as I; I.fromarray(rnd.render()).save(f"{a.render}/f{frame:05d}.png"); frame += 1; next_frame += 1 / 30
        if a.duration and d.time >= a.duration:
            break
    if log:
        log.close()


if __name__ == "__main__":
    main()
