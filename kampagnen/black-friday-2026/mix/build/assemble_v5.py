"""Assemble the base picture of the MIX version: new UGC hook + original product footage.

  S1  new UGC hook (Higgsfield: Soul 2 + Intone + Sync Lipsync 3)          0.00 -  5.40
  S2  door fly-through (Higgsfield Kling 4.0) with a speed ramp INTO the door 5.40 -  7.40
  S3  original spot: fence drop (real time) + fence hero (slow motion)      7.40 - 18.75
  S4  original spot: sauna + whirlpool fall in                             18.75 - 26.17
  S5  original spot: wide shot with all products                           26.17 - 31.30

The voice-over timeline is the one of v4 (same VO), so the product shots are re-timed to it.
Usage: python3 assemble_v5.py <clips_dir> <original_spot.mp4> <out_dir>
"""
import json
import os
import subprocess
import sys
import tempfile

clips, orig, out = sys.argv[1], sys.argv[2], sys.argv[3]
FPS = 24
W, H = 1080, 1920
SRC_FPS = 30  # original spot

# frame-based scenes from the original spot (start frame incl., end frame excl.)
SCENES = [
    dict(name="S1_ugc", file=f"{clips}/s1_ugc.mp4", cin=0.00, cout=5.40, start=0.00, end=5.40),
    dict(name="S2_door_ramp", file=f"{clips}/s2_transition.mp4", cin=0.40, cout=1.56, start=5.40, end=7.40, ramp=0.45),
    dict(name="S3a_fence_drop", file=orig, f0=157, f1=318, start=7.40, end=13.13),
    dict(name="S3b_fence_hero", file=orig, f0=318, f1=406, start=13.13, end=18.75),
    dict(name="S4_sauna_whirl", file=orig, f0=406, f1=640, start=18.75, end=26.17),
    dict(name="S5_wide", file=orig, f0=640, f1=791, start=26.17, end=31.30),
]


def run(cmd):
    subprocess.run(cmd, check=True)


def nframes(p):
    return int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                               "stream=nb_read_frames", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip())


ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p"]
FIT = [f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={W}:{H}", "setsar=1"]
parts = []
for i, s in enumerate(SCENES):
    dur_out = s["end"] - s["start"]
    n_out = round(dur_out * FPS)
    seg = f"{out}/seg5_{i}.mp4"
    if "ramp" in s:
        # speed ramp: slow drift after the hook, accelerating into the door frame (time map a*u + (1-a)*u^3)
        hi = 96
        tmp = tempfile.mkdtemp(dir=out)
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['cin'] - 0.1:.3f}", "-t", f"{s['cout'] - s['cin'] + 0.25:.3f}",
             "-i", s["file"], "-an", "-vf", f"minterpolate=fps={hi}:mi_mode=mci:mc_mode=aobmc:vsbmc=1," + ",".join(FIT),
             "-q:v", "2", f"{tmp}/h_%05d.jpg"])
        a = s["ramp"]
        L = s["cout"] - s["cin"]
        for k in range(n_out):
            u = k / (n_out - 1)
            src_t = 0.1 + L * (a * u + (1 - a) * u ** 3)
            j = max(1, round(src_t * hi) + 1)
            os.link(f"{tmp}/h_{j:05d}.jpg", f"{tmp}/o_{k:05d}.jpg")
        run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{tmp}/o_%05d.jpg", "-vf", "setsar=1", *ENC, seg])
        subprocess.run(["rm", "-rf", tmp])
        s["speed"] = round(L / dur_out, 4)
    else:
        if "f0" in s:
            trim = f"trim=start_frame={s['f0']}:end_frame={s['f1']}"
            dur_in = (s["f1"] - s["f0"]) / SRC_FPS
            src_fps = SRC_FPS
        else:
            trim = f"trim=start={s['cin']}:end={s['cout']}"
            dur_in = s["cout"] - s["cin"]
            src_fps = 24
        speed = dur_in / dur_out
        s["speed"] = round(speed, 4)
        vf = [trim, "setpts=PTS-STARTPTS"]
        if abs(speed - 1) > 0.002:
            vf += [f"setpts=PTS/{speed:.5f}"]
        if src_fps * speed < FPS * 0.999:
            # not enough real frames for 24 fps: motion-compensated interpolation for a clean slow motion
            vf += [f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1"]
        vf += FIT + [f"fps={FPS}", f"trim=end_frame={n_out}"]
        run(["ffmpeg", "-v", "error", "-y", "-i", s["file"], "-an", "-vf", ",".join(vf), *ENC, seg])
    s["frames"] = nframes(seg)
    parts.append(seg)
    print(f"{s['name']:16s} {s['start']:6.2f}-{s['end']:6.2f}  speed {s['speed']:5.3f}  frames {s['frames']} (want {n_out})")

with open(f"{out}/concat5.txt", "w") as f:
    for p in parts:
        f.write(f"file '{p}'\n")
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{out}/concat5.txt", "-c", "copy", f"{out}/base_mix.mp4"])
json.dump(SCENES, open(f"{out}/base_mix.json", "w"), indent=1)
print("ok", out + "/base_mix.mp4")
