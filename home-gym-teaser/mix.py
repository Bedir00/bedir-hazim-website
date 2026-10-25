"""Mix voice-over segments and a quiet synthesized pad, then mux with the silent render.
Usage: python3 mix.py <key>  ->  out/<key>.mp4"""
import json, subprocess, sys, wave, pathlib
import numpy as np

T = pathlib.Path(__file__).parent
key = sys.argv[1]
SR = 48000
tl = json.load(open(T / f'out/{key}.timeline.json'))
n = int(tl['end'] * SR)

def load(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()

voice = np.zeros(n, np.float32)
for i, start in enumerate([tl['s0'], tl['s1'], tl['s2']]):
    seg = load(T / f'vo/{key}-{i}.wav')
    a = int(start * SR)
    voice[a:a + len(seg)] += seg[: n - a]

# Calm pad: soft A-minor add9 voicing, slow breathing, swells a little for the CTA.
t = np.arange(n) / SR
pad = np.zeros(n)
for f, amp in [(110, .5), (164.81, .35), (220, .3), (261.63, .22), (329.63, .18), (493.88, .07)]:
    for det in (-0.35, 0.35):
        pad += amp * np.sin(2 * np.pi * (f + det) * t + f)
pad *= 0.75 + 0.25 * np.sin(2 * np.pi * t / 7.0)
env = np.clip(t / 2.0, 0, 1) * np.clip((tl['end'] - t) / 1.2, 0, 1)
swell = 1 + 0.4 * np.clip((t - tl['s2']) / 1.5, 0, 1)
pad = pad / np.max(np.abs(pad)) * env * swell
# Duck the pad under the voice.
vo_env = np.convolve(np.abs(voice), np.ones(SR // 10) / (SR // 10), mode='same')
duck = 1 - 0.45 * np.clip(vo_env / (vo_env.max() * 0.25), 0, 1)
mix = voice * 1.0 + pad * 0.055 * duck
stereo = np.stack([mix, mix], 1).astype(np.float32)
tmp = T / f'out/{key}.mix.f32'
stereo.tofile(tmp)
wav = T / f'out/{key}.wav'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', str(tmp),
                '-af', 'highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=180,loudnorm=I=-16:TP=-1.5:LRA=9',
                '-ar', str(SR), str(wav)], check=True)
tmp.unlink()
out = T / f'out/{key}.mp4'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(T / f'out/{key}.silent.mp4'), '-i', str(wav),
                '-vf', 'hqdn3d=3:3:6:6', '-c:v', 'libx264', '-preset', 'slow', '-crf', '26', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
                '-c:a', 'aac', '-b:a', '112k', '-shortest', '-movflags', '+faststart', str(out)], check=True)
print(key, out.stat().st_size)
