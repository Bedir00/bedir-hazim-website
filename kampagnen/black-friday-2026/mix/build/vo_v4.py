"""v4 voice-over assembly.

Female UGC hook = audio track of the lip-synced Intone clip (keeps lips in sync).
Male VO = Vlad take, split at silences into 14 phrases, sped up slightly (rubberband,
formant preserved) and laid back-to-back with short gaps.

Usage: python3 vo_v4.py <s1_ugc.mp4> <vlad_take.mp3> <out_dir>
Writes vo_v4.wav (48 kHz stereo) and vo_v4.json (phrase/word timings).
"""
import json
import os
import subprocess
import sys
import numpy as np
from scipy.io import wavfile
from faster_whisper import WhisperModel

SR = 48000
ugc_path, vlad_path, out_dir = sys.argv[1:4]
TEMPO = 1.12
UGC_END = 5.40          # cut point of the UGC scene (her last word ends ~5.34 s)
MODEL_DIR = os.environ.get("WHISPER_DIR", "./models")

PHRASES = [  # subtitle text per silence-separated block of the take
    "Schluss mit Minirabatten.", "Nicht 15, nicht 20,", "25 %", "auf alles.", "Klingt nach wenig?",
    "Zaun Alira:", "über 280 € gespart.", "Sauna Lagom Deluxe:", "über 1.200 €.",
    "Whirlpool Stream Big:", "noch mal über 1.200.", "Zusammen über 2.700 €,",
    "nur am Black-Friday-Wochenende.", "Home Deluxe.",
]
# gap BEFORE each phrase (seconds on the final timeline)
GAPS = [0.08, 0.18, 0.14, 0.08, 0.22, 0.14, 0.10, 0.32, 0.10, 0.32, 0.10, 0.32, 0.12, 0.80]


def load(path, sr=SR):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def rubber(x, tempo):
    p = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                        "-af", f"rubberband=tempo={tempo:.4f}:formant=preserved:pitchq=quality", "-f", "f32le", "-"],
                       input=x.tobytes(), capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.float32).copy()


def segments(a, min_sil=0.15, thr_db=-48):
    env = np.sqrt(np.convolve(a ** 2, np.ones(480) / 480, "same"))
    sil = env < 10 ** (thr_db / 20)
    segs, cur, run, last = [], None, 0, 0
    for k in range(0, len(a), 48):
        if not sil[k]:
            if cur is None:
                cur = k
            last, run = k, 0
        elif cur is not None:
            run += 48
            if run >= int(min_sil * SR):
                segs.append((cur, last))
                cur, run = None, 0
    if cur is not None:
        segs.append((cur, last))
    return segs


ugc = load(ugc_path)[: int(UGC_END * SR)]
ugc[-int(0.04 * SR):] *= np.linspace(1, 0, int(0.04 * SR))
take = load(vlad_path)
segs = segments(take)
assert len(segs) == len(PHRASES), (len(segs), [(s / SR, e / SR) for s, e in segs])

track = [ugc]
t = UGC_END
placed = []
for (s, e), txt, gap in zip(segs, PHRASES, GAPS):
    # skip leading breath: first sample louder than -34 dB inside the block
    env_b = np.sqrt(np.convolve(take[s:e] ** 2, np.ones(480) / 480, "same"))
    on = np.where(env_b > 10 ** (-34 / 20))[0]
    s = s + max(0, (on[0] if len(on) else 0) - int(0.04 * SR))
    s0, e0 = max(0, s - int(0.02 * SR)), min(len(take), e + int(0.08 * SR))
    clip = rubber(take[s0:e0], TEMPO)
    fi, fo = int(0.01 * SR), int(0.05 * SR)
    clip[:fi] *= np.linspace(0, 1, fi)
    clip[-fo:] *= np.linspace(1, 0, fo)
    t += gap
    track.append(np.zeros(int(gap * SR), np.float32))
    track.append(clip)
    placed.append({"text": txt, "start": round(t, 3), "end": round(t + len(clip) / SR, 3), "src": [s0 / SR, e0 / SR]})
    t += len(clip) / SR
vo = np.concatenate(track)
vo = np.concatenate([vo, np.zeros(int(1.3 * SR), np.float32)])

# loudness match: male VO RMS to the UGC voice RMS
def vrms(x):
    e = np.sqrt(np.convolve(x ** 2, np.ones(960) / 960, "same"))
    v = x[e > 0.02]
    return float(np.sqrt(np.mean(v ** 2))) if len(v) else 1.0

n_ugc = int(UGC_END * SR)
g = vrms(vo[:n_ugc]) / vrms(vo[n_ugc:])
vo[n_ugc:] *= g * 1.05
wavfile.write(f"{out_dir}/vo_v4.wav", SR, (np.clip(np.stack([vo, vo], 1), -1, 1) * 32767).astype(np.int16))

# word timings on the final track
m = WhisperModel("medium", device="cpu", compute_type="int8", download_root=MODEL_DIR)
a16 = load(f"{out_dir}/vo_v4.wav", 16000)
ws, _ = m.transcribe(a16, language="de", beam_size=5, word_timestamps=True)
words = [(w.word.strip(), round(w.start, 3), round(w.end, 3)) for seg in ws for w in seg.words]
json.dump({"phrases": placed, "words": words, "ugc_end": UGC_END, "duration": round(len(vo) / SR, 3)},
          open(f"{out_dir}/vo_v4.json", "w"), ensure_ascii=False, indent=1)
for p in placed:
    print(f"{p['start']:6.2f}-{p['end']:6.2f}  {p['text']}")
print("total", len(vo) / SR)
print(" ".join(w for w, _, _ in words))
