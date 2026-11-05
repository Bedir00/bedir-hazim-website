"""Assemble the v4 base picture from the generated Higgsfield clips.

Every scene = (clip, in-point, scene start, scene end, mode). Speed is derived from
the available clip material so each scene exactly fills its slot on the VO timeline.
Output: base_v4.mp4 (1080x1920, 24 fps, no audio) + base_v4.json (scene table).

Usage: python3 assemble_v4.py <clips_dir> <out_dir>
"""
import json
import subprocess
import sys

clips, out = sys.argv[1], sys.argv[2]
FPS = 24
W, H = 1080, 1920

# scene table (seconds on the final timeline)
SCENES = [
    # name, file, in, start, end, clip_out (None = in + (end-start)*speed computed from fixed speed)
    dict(name="S1_ugc", file="s1_ugc.mp4", cin=0.00, cout=5.40, start=0.00, end=5.40),
    dict(name="S2_transition", file="s2_transition.mp4", cin=0.40, cout=4.03, start=5.40, end=7.40),
    dict(name="S3a_fence_drop", file="s3a_fence.mp4", cin=0.26, cout=6.03, start=7.40, end=13.13),
    dict(name="S3b_fence_hero", file="s3b_fencehero.mp4", cin=0.00, cout=5.03, start=13.13, end=18.75),
    dict(name="S4_sauna", file="s4_minimax.mp4", cin=0.20, cout=3.87, start=18.75, end=22.42),
    dict(name="S5_whirlpool", file="s5_whirl.mp4", cin=0.00, cout=3.75, start=22.42, end=26.17),
    dict(name="S6_hero", file="s6_hero.mp4", cin=0.00, cout=5.13, start=26.17, end=31.30),
]


def run(cmd):
    subprocess.run(cmd, check=True)


parts = []
for i, s in enumerate(SCENES):
    dur_out = s["end"] - s["start"]
    dur_in = s["cout"] - s["cin"]
    speed = dur_in / dur_out
    s["speed"] = round(speed, 4)
    vf = [f"trim=start={s['cin']}:end={s['cout']}", "setpts=PTS-STARTPTS"]
    if speed < 0.97:
        # slow down with motion-compensated interpolation for a clean glide
        vf += [f"setpts=PTS/{speed:.5f}", f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1"]
    elif speed > 1.03:
        vf += [f"setpts=PTS/{speed:.5f}"]
    vf += [f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={W}:{H}", f"fps={FPS}",
           f"trim=end_frame={round(dur_out * FPS)}", "setsar=1"]
    seg = f"{out}/seg_{i}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", f"{clips}/{s['file']}", "-an", "-vf", ",".join(vf),
         "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", seg])
    n = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "csv=p=0", seg], capture_output=True, text=True).stdout.strip())
    s["frames"] = n
    parts.append(seg)
    print(f"{s['name']:16s} {s['start']:6.2f}-{s['end']:6.2f}  speed {speed:5.3f}  frames {n} (want {round(dur_out*FPS)})")

with open(f"{out}/concat.txt", "w") as f:
    for p in parts:
        f.write(f"file '{p}'\n")
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{out}/concat.txt", "-c", "copy", f"{out}/base_v4.mp4"])
json.dump(SCENES, open(f"{out}/base_v4.json", "w"), indent=1)
print("ok", out + "/base_v4.mp4")
