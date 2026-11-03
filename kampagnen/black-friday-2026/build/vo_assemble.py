"""Cut a single TTS voice-over take into phrases and lay them onto the picture.

Usage: python3 vo_assemble.py <orig_audio.wav> <tts_take.wav> <out_dir>
Writes <out_dir>/vo_track.wav (48 kHz stereo, woman's original intro + new VO)
and <out_dir>/vo_timing.json (subtitle + counter timings derived from the placement).
"""
import json
import os
import subprocess
import sys
import numpy as np
from scipy.io import wavfile
from faster_whisper import WhisperModel
from timeline import OUT_DURATION, CUT_FREEZE

SR = 48000
orig_path, take_path, out_dir = sys.argv[1:4]
MODEL_DIR = os.environ.get("WHISPER_DIR", "./models")


def load(path, sr=SR, ch=1):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", str(ch), "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    return x.reshape(-1, ch) if ch > 1 else x


take = load(take_path)
a16 = load(take_path, 16000)
m = WhisperModel("medium", device="cpu", compute_type="int8", download_root=MODEL_DIR)
segs, _ = m.transcribe(a16, language="de", beam_size=5, word_timestamps=True)
words = [(w.word.strip(), w.start, w.end) for s in segs for w in s.words]
print(len(words), "words:", " ".join(w for w, _, _ in words))
assert len(words) == 45, "unexpected word count - check the take"

# (first word, last word, slot start, latest end)
GROUPS = [
    (0, 3, 4.10, 5.66),     # Schluss mit Minirabatten!
    (4, 5, 5.68, 6.40),     # Nicht fünfzehn,
    (6, 7, 6.44, 7.26),     # nicht zwanzig,
    (8, 11, 7.30, 9.55),    # fünfundzwanzig Prozent auf alles!
    (12, 14, 9.62, 10.42),  # Klingt nach wenig?
    (15, 20, 10.36, 13.40), # Zaun Alira: über zweihundertachtzig Euro gespart.
    (21, 23, 13.74, 15.12), # Sauna Lagom Deluxe:
    (24, 26, 15.30, 17.25), # über zwölfhundert Euro.
    (27, 29, 17.55, 18.95), # Whirlpool Stream Big:
    (30, 33, 19.00, 20.80), # noch mal über zwölfhundert.
    (34, 37, 21.15, 23.95), # Zusammen über zweitausendsiebenhundert Euro!
    (38, 42, 24.22, 26.12), # Nur am Black-Friday-Wochenende.
    (43, 44, 26.72, 27.90), # Home Deluxe.
]
CHUNKS = [  # subtitle text, first word, last word
    ("Schluss mit Minirabatten.", 0, 3), ("Nicht 15,", 4, 5), ("nicht 20,", 6, 7),
    ("25 % auf alles.", 8, 11), ("Klingt nach wenig?", 12, 14), ("Zaun Alira:", 15, 16),
    ("über 280 € gespart.", 17, 20), ("Sauna Lagom Deluxe:", 21, 23), ("über 1.200 €.", 24, 26),
    ("Whirlpool Stream Big:", 27, 29), ("noch mal über 1.200.", 30, 33),
    ("Zusammen über 2.700 €,", 34, 37), ("nur am Black-Friday-Wochenende.", 38, 42),
]

env = np.sqrt(np.convolve(take ** 2, np.ones(480) / 480, mode="same"))
thr_low = 10 ** (-48 / 20)


def refine(w0, w1):
    """Cut in the energy minimum between neighbouring words, then trim silence."""
    st, en = words[w0][1], words[w1][2]
    lo = words[w0 - 1][2] if w0 > 0 else 0.0
    hi = words[w1 + 1][1] if w1 + 1 < len(words) else len(take) / SR
    a0, a1 = int(max(0.0, lo - 0.03) * SR), int((st + 0.04) * SR)
    cut0 = a0 + int(np.argmin(env[a0:a1])) if a1 > a0 else int(st * SR)
    b0, b1 = int((en - 0.04) * SR), int((hi + 0.03) * SR)
    cut1 = b0 + int(np.argmin(env[b0:b1])) if b1 > b0 else int(en * SR)
    # trim leading / trailing silence inside the cut
    base = cut0
    on = np.where(env[base:cut1] > thr_low)[0]
    if len(on):
        cut0 = max(base, base + on[0] - int(0.025 * SR))
        cut1 = min(cut1, base + on[-1] + int(0.06 * SR))
    return cut0, cut1


track = np.zeros(int(OUT_DURATION * SR), np.float32)
new_time = {}  # word index -> (start, end) on the final timeline
for w0, w1, slot, latest in GROUPS:
    s, e = refine(w0, w1)
    clip = take[s:e].copy()
    dur = len(clip) / SR
    room = latest - slot
    tempo = 1.0
    if dur > room:
        tempo = min(1.22, dur / room)
        p = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                            "-af", f"rubberband=tempo={tempo:.4f}:formant=preserved:pitchq=quality",
                            "-f", "f32le", "-"], input=clip.tobytes(), capture_output=True, check=True)
        clip = np.frombuffer(p.stdout, np.float32).copy()
    fi, fo = int(0.012 * SR), int(0.06 * SR)
    clip[:fi] *= np.linspace(0, 1, fi)
    clip[-fo:] *= np.linspace(1, 0, fo)
    i = int(slot * SR)
    track[i:i + len(clip)] += clip[: len(track) - i]
    for k in range(w0, w1 + 1):
        ws = slot + (words[k][1] - s / SR) / tempo
        we = slot + (words[k][2] - s / SR) / tempo
        new_time[k] = (max(slot, ws), min(slot + len(clip) / SR, we))
    print(f"group {w0:2d}-{w1:2d} slot {slot:5.2f} dur {dur:4.2f}s room {room:4.2f}s tempo {tempo:.3f}")

# woman's on-camera intro stays original (cut right before the freeze)
orig = load(orig_path)
n_int = int((CUT_FREEZE - 0.01) * SR)
intro = orig[:n_int].copy()
intro[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR))

# level-match: TTS peak-normalised to the intro's speech level (RMS of voiced parts)
def voiced_rms(x):
    e = np.sqrt(np.convolve(x ** 2, np.ones(960) / 960, mode="same"))
    v = x[e > 0.02]
    return np.sqrt(np.mean(v ** 2)) if len(v) else 1.0

track *= voiced_rms(intro) / voiced_rms(track) * 1.05
track[:n_int] = intro
st = np.stack([track, track], 1)
wavfile.write(f"{out_dir}/vo_track.wav", SR, (np.clip(st, -1, 1) * 32767).astype(np.int16))

group_slot = {w0: slot for w0, _, slot, _ in GROUPS}
starts = [group_slot[a] - 0.03 if a in group_slot else new_time[a][0] - 0.06 for _, a, _ in CHUNKS]
subs = []
for k, (txt, a, b) in enumerate(CHUNKS):
    nxt = starts[k + 1] - 0.02 if k + 1 < len(CHUNKS) else 1e9
    end = min(nxt, new_time[b][1] + 0.55, 26.30)
    subs.append([round(starts[k], 3), round(end, 3), txt])
timing = {
    "subs": subs,
    "counters": {
        "fence": [round(new_time[17][0], 3), round(new_time[18][1], 3)],
        "sauna": [round(new_time[24][0], 3), round(new_time[25][1], 3)],
        "whirl": [round(new_time[32][0], 3), round(new_time[33][1], 3)],
        "total": [round(new_time[35][0], 3), round(new_time[36][1], 3)],
    },
    "klingt": round(new_time[12][0], 3),
    "nur_am": round(new_time[38][0], 3),
    "home": round(new_time[43][0], 3),
    "words": {k: [round(v[0], 3), round(v[1], 3), words[k][0]] for k, v in new_time.items()},
}
json.dump(timing, open(f"{out_dir}/vo_timing.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(timing["counters"]))
for s_ in subs:
    print(s_)
