"""Render a video from a logged run: replays the joint angles in out/plant*.csv (no live rendering in the 1 ms loop).

    python scripts/replay_render.py out/plant_qnx.csv out/replay.mp4 [--fps 30] [--size 1280x720]
Frames are taken from the logged states every 1/fps seconds of plant time (one plant step = 1 ms).
"""
import argparse, csv, pathlib, subprocess, sys, tempfile
import numpy as np
import mujoco
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "host"))
from plant import build_model, NJ  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("log"); ap.add_argument("out")
ap.add_argument("--fps", type=int, default=30); ap.add_argument("--size", default="1280x720")
a = ap.parse_args()
W, H = map(int, a.size.split("x"))
rows = list(csv.DictReader(open(a.log)))
q = np.array([[float(r[f"q{i}"]) for i in range(NJ)] for r in rows if r.get("q0")])
step = max(1, round(1000 / a.fps))  # 1 ms per logged step
m = build_model(); d = mujoco.MjData(m)
rnd = mujoco.Renderer(m, H, W)
cam = mujoco.MjvCamera(); cam.lookat[:] = [0.25, 0, 0.4]; cam.distance = 1.6; cam.azimuth = 140; cam.elevation = -20
tmp = pathlib.Path(tempfile.mkdtemp(prefix="rtarm_frames_"))
import PIL.Image as I
for k, i in enumerate(range(0, len(q), step)):
    d.qpos[:NJ] = q[i]; mujoco.mj_forward(m, d)
    rnd.update_scene(d, cam); I.fromarray(rnd.render()).save(tmp / f"f{k:05d}.png")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", str(tmp / "f%05d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", a.out], check=True)
print(f"{len(q)} logged steps -> {k + 1} frames -> {a.out} ({(k + 1) / a.fps:.1f} s)")
for f in tmp.glob("*.png"): f.unlink()
tmp.rmdir()
