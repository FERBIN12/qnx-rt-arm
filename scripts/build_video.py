"""Compose the demo video from real footage only: live terminal recording (scripts/demo_session.sh captured with
ffmpeg x11grab), MuJoCo replay renders (scripts/replay_render.py), cards with measured numbers from results/.
Long idle waits in the terminal recording are cut and each cut is labelled on screen.
usage: build_video.py VIDEODIR DEMO_OUT_DIR   (VIDEODIR holds term_raw.mp4 + jitter_panels.png)"""
import re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

d, demo = Path(sys.argv[1]), Path(sys.argv[2]); W, H = 1440, 1000
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
run = lambda *a: subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)
enc = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-crf", "20"]


def card(name, title, lines, img=None, mono=False):
    im = Image.new("RGB", (W, H), (250, 248, 242)); g = ImageDraw.Draw(im)
    sz = 54
    while ImageFont.truetype(FB, sz).getlength(title) > W - 180: sz -= 2
    g.text((90, 80), title, font=ImageFont.truetype(FB, sz), fill=(31, 58, 95)); y = 190
    for ln in lines:
        f = ImageFont.truetype(FB if ln.startswith("*") else (FM if mono else F), 28 if mono else 31); ln = ln.lstrip("*")
        g.text((90, y), ln, font=f, fill=(40, 40, 40)); y += 50 if ln else 26
    if img:
        p = Image.open(img).convert("RGB"); s = min((W - 180) / p.width, (H - y - 40) / p.height)
        p = p.resize((int(p.width * s), int(p.height * s))); im.paste(p, ((W - p.width) // 2, y + 10))
    im.save(d / f"{name}.png")


card("c0", "rt-arm: a hard real-time arm controller on QNX 8.0", [
    "A 1 kHz joint controller (PD + gravity compensation, watchdog e-stop)",
    "runs on QNX 8.0 inside QEMU and drives a MuJoCo Franka Panda arm over UDP.", "",
    "Question: what does a real-time OS buy you when the CPU is busy?", "",
    "Everything here is real: live terminal recording, logged runs, measured numbers.",
    "Built by Ferbin Richard with Claude Code (an AI coding agent).", "Captions only, no voice."])
card("c1", "Measured: loop period under CPU load (8000 ticks each)", [
    "Tick logs in results/ (scripts/stress_bench.sh), one histogram per run, log scale:"], img=d / "jitter_panels.png")
card("c2", "Measured, not claimed", [
    "*Loop period, 8000 ticks, busy laptop (README table, results/):",
    "Linux, 1 hog same core, normal prio:  sd 247.1 us, max 4660.5 us, 88 late",
    "QNX, 2 hogs prio 10, controller prio 10:  mean 7097.9 us, 7999 late",
    "QNX, 2 hogs prio 10, controller prio 50:  sd 5.9 us, max 1114.7 us, 1 late",
    "The run recorded in this video: sd 10.1 us, max 1330.4 us, 4 late.", "",
    "*E-stop when the plant link drops (10 trials each):",
    "Linux 20.00 / 20.30 / 21.00 ms,  QNX 20.00 / 20.70 / 21.00 ms (min/mean/max)",
    "Both meet the 20 ms watchdog: the check is time-based. QNX wins on the loop,",
    "not on the e-stop. Linux baseline is SCHED_OTHER (no root), not PREEMPT_RT.",
    "QEMU on a laptop, not real hardware: relative behaviour, not absolute us."])
card("c3", "The bug worth learning from: pulse priority", [
    "The first version used SIGEV_PULSE_PRIO_INHERIT for the timer pulse.",
    "On QNX a thread that receives a pulse runs at the pulse's priority,",
    "so even with -r 50 the controller fell back to priority 10 after every",
    "MsgReceivePulse and shared round-robin with the hogs: ~7 ms periods.", "",
    "*Fix: SIGEV_PULSE_INIT(&ev, coid, pprio, ...) with pprio = the -r priority.",
    "One argument is the difference between the prio 10 and prio 50 rows."])
card("c4", "Try it", [
    "github.com/FERBIN12/qnx-rt-arm  (MIT license)", "",
    "The README is a step-by-step codelab: free QNX SDP 8.0 (QNX Everywhere),",
    "mkqnximage QEMU target, qcc build, closed loop, load test, e-stop test.", "",
    "Credits: MuJoCo (Apache-2.0), MuJoCo Menagerie Franka Panda (Apache-2.0),",
    "QNX SDP 8.0 under the QNX Everywhere non-commercial license.",
    "Built with Claude Code (AI coding agent) directed by Ferbin Richard."])

# --- terminal segment: trim idle freezes > 3 s, label each cut
raw = d / "term_raw.mp4"
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw)],
                           capture_output=True, text=True).stdout)
log = subprocess.run(["ffmpeg", "-i", str(raw), "-vf", "freezedetect=n=0.001:d=3", "-map", "0:v", "-f", "null", "-"],
                     capture_output=True, text=True).stderr
st = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
en = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", log)] + [dur]
keep, cuts, t = [], [], 0.0
for i, (a, b) in enumerate(zip(st, en)):
    last = i == len(st) - 1
    if last:
        keep.append((t, min(b, a + 7))); t = b; break
    keep.append((t, a + 1.2)); cuts.append((a + 1.2, b - 1.3)); t = b - 1.3
else:
    keep.append((t, dur))
src2out = []
o = 0.0
for a, b in keep:
    src2out.append((a, b, o)); o += b - a
def m(s):  # source time -> output time
    for a, b, oo in src2out:
        if s <= b: return oo + max(0.0, s - a)
    return o
notes = [(0, 11, "Real QNX 8.0 guest in QEMU on a laptop. Recorded live."),
         (11.4, 20.3, "Two busy loops now take both vCPUs at priority 10."),
         (20.3, 79.5, "Controller at the SAME priority as the hogs: QNX shares the CPU round-robin."),
         (79.5, 89.4, "1 ms loop became 6.8 ms on average: 7999 of 8000 ticks late."),
         (89.4, 102.1, "Change one number: -r 50. Now it is the most important thread."),
         (102.1, dur, "Same hogs, same guest: mean 1000.0 us, sd 10.1 us, 4 of 8000 late.")]
def ts(s): return f"{int(s//3600)}:{int(s%3600//60):02d}:{s%60:05.2f}"
hdr = ["[Script Info]", "PlayResX: 1440", "PlayResY: 1000", "", "[V4+ Styles]",
       "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Alignment, MarginV, BorderStyle, Outline, Shadow",
       "Style: C,DejaVu Sans,32,&H00FFFFFF,&H00000000,&H00000000,0,2,30,1,0,0",
       "Style: K,DejaVu Sans,22,&H0000D7FF,&H00000000,&H00000000,1,9,906,1,0,0", "", "[Events]",
       "Format: Layer, Start, End, Style, Text"]
ev = [f"Dialogue: 0,{ts(m(a))},{ts(m(b))},C,{x}" for a, b, x in notes]
ev += [f"Dialogue: 0,{ts(m(a))},{ts(m(a) + 3)},K,[cut: {b - a:.0f} s of real waiting]" for a, b in cuts]
(d / "term.ass").write_text("\n".join(hdr + ev) + "\n")
sel = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keep)
run("-i", str(raw), "-vf", f"select='{sel}',setpts=N/30/TB,pad={W}:{H}:0:0:color=0x1f3a5f,ass={d/'term.ass'}",
    *enc, str(d / "term.mp4"))

# --- arm replay segment: the two logged runs side by side
r = Path("out/renders")
arm_caps = [(0, 9, "MuJoCo replays of logged runs. They look alike: the difference is microseconds,"),
            (0, 9, "so the measured numbers, not the arm motion, carry the result.")]
(d / "arm.ass").write_text("\n".join(hdr[:9] + ["", "[Events]", "Format: Layer, Start, End, Style, Text",
    f"Dialogue: 0,{ts(0)},{ts(9)},C,{arm_caps[0][2]}\\N{arm_caps[1][2]}"]) + "\n")
run("-i", str(r / "qnx_prio50.mp4"), "-i", str(r / "linux_load.mp4"), "-filter_complex",
    f"[0:v]scale=710:400[a];[1:v]scale=710:400[b];color=c=0x1f3a5f:s={W}x{H}:d=9[bg];"
    f"[bg][a]overlay=7:200[t];[t][b]overlay=723:200,"
    f"drawtext=fontfile={FB}:text='QNX 8.0, controller prio 50, 2 hogs':x=20:y=150:fontsize=28:fontcolor=white,"
    f"drawtext=fontfile={FB}:text='Linux, normal prio, 1 hog':x=740:y=150:fontsize=28:fontcolor=white,"
    f"ass={d/'arm.ass'}", "-t", "9", *enc, str(d / "arm.mp4"))

for c, sec in (("c0", 9), ("c1", 11), ("c2", 16), ("c3", 11), ("c4", 10)):
    run("-loop", "1", "-t", str(sec), "-i", str(d / f"{c}.png"), "-vf", "fade=in:0:12", *enc, str(d / f"{c}.mp4"))
(d / "list.txt").write_text("".join(f"file '{n}.mp4'\n" for n in ("c0", "term", "arm", "c1", "c2", "c3", "c4")))
run("-f", "concat", "-safe", "0", "-i", str(d / "list.txt"), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
    "-shortest", *enc, "-c:a", "aac", str(d / "rtarm_demo.mp4"))
print("keep", [(round(a, 1), round(b, 1)) for a, b in keep], "cuts", [(round(a, 1), round(b, 1)) for a, b in cuts])
print("ok", d / "rtarm_demo.mp4")
