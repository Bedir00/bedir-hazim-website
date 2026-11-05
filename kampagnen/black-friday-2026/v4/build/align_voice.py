"""Re-time a clean voice recording onto the speech timing of a lip-synced video.

The lip-sync model re-synthesised the voice (small slip + metallic tint). We keep its
TIMING (which matches the lips) but put the original clean recording back:
  1) DTW on log-mel features maps every 10 ms of the target (video) audio to the source
  2) WSOLA renders the source with that time-varying mapping
  3) target silences stay silent

Usage: python3 align_voice.py <clean.wav> <lipsync_video_or_audio> <out.wav>
"""
import subprocess
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft
from scipy.ndimage import median_filter

SR = 48000
HOP = 480  # 10 ms


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def mel_fb(n_fft, n_mels=40, fmin=80, fmax=8000):
    def hz2mel(f):
        return 2595 * np.log10(1 + f / 700)

    def mel2hz(m):
        return 700 * (10 ** (m / 2595) - 1)
    mels = np.linspace(hz2mel(fmin), hz2mel(fmax), n_mels + 2)
    hz = mel2hz(mels)
    bins = np.floor((n_fft + 1) * hz / SR).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for i in range(n_mels):
        a, b, c = bins[i], bins[i + 1], bins[i + 2]
        fb[i, a:b] = (np.arange(a, b) - a) / max(1, b - a)
        fb[i, b:c] = (c - np.arange(b, c)) / max(1, c - b)
    return fb


def feats(x):
    n_fft = 1024
    _, _, Z = stft(x, SR, nperseg=n_fft, noverlap=n_fft - HOP, boundary=None)
    P = np.abs(Z) ** 2
    M = np.log(mel_fb(n_fft) @ P + 1e-8)
    M = (M - M.mean(1, keepdims=True)) / (M.std(1, keepdims=True) + 1e-6)
    return M.T  # frames x mels


def dtw(A, B):
    """Return path mapping rows of A (target) to rows of B (source)."""
    n, m = len(A), len(B)
    C = np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1))
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0
    for i in range(1, n + 1):
        Di, Dp = D[i], D[i - 1]
        ci = C[i - 1]
        for j in range(1, m + 1):
            Di[j] = ci[j - 1] + min(Dp[j - 1], Dp[j] * 1.0 + 0.0, Di[j - 1])
    i, j, path = n, m, []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        k = np.argmin([D[i - 1, j - 1], D[i - 1, j], D[i, j - 1]])
        if k == 0:
            i, j = i - 1, j - 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    return path[::-1]


def wsola(src, mapping_s, out_len, win=1024, tol=240):
    """mapping_s(t_out_sample) -> t_in_sample. Overlap-add with similarity search."""
    hop = win // 2
    w = np.hanning(win).astype(np.float32)
    out = np.zeros(out_len + win, np.float32)
    norm = np.zeros(out_len + win, np.float32)
    prev_tail = None
    pos_prev = None
    for o in range(0, out_len, hop):
        target = int(mapping_s(o))
        best = target
        if prev_tail is not None and pos_prev is not None:
            nat = pos_prev + hop  # natural continuation
            lo, hi = max(0, target - tol), min(len(src) - win, target + tol)
            if hi > lo:
                cand = np.arange(lo, hi, 8)
                seg = np.stack([src[c:c + hop] for c in cand])
                score = seg @ prev_tail
                best = int(cand[np.argmax(score)])
        best = int(np.clip(best, 0, len(src) - win))
        frame = src[best:best + win] * w
        out[o:o + win] += frame
        norm[o:o + win] += w
        prev_tail = src[best + hop:best + win] if best + win <= len(src) else None
        pos_prev = best
    norm[norm < 1e-3] = 1
    return (out / norm)[:out_len]


def main():
    clean_p, target_p, out_p = sys.argv[1:4]
    clean, target = load(clean_p), load(target_p)
    A, B = feats(target), feats(clean)
    path = dtw(A, B)
    tmap = np.zeros(len(A))
    for i, j in path:
        tmap[i] = j
    tmap = np.maximum.accumulate(median_filter(tmap, size=7))
    # optional linear overrides: target_t0:target_t1=source_t0:source_t1 (seconds)
    for spec in sys.argv[4:]:
        tgt, srcr = spec.split("=")
        a0, a1 = map(float, tgt.split(":"))
        b0, b1 = map(float, srcr.split(":"))
        i0, i1 = int(a0 * SR / HOP), int(a1 * SR / HOP)
        tmap[i0:i1] = np.linspace(b0 * SR / HOP, b1 * SR / HOP, i1 - i0)
        tmap[i1:] = np.maximum(tmap[i1:], b1 * SR / HOP)
    # silence mask of the target
    env_t = np.sqrt(np.convolve(target ** 2, np.ones(480) / 480, "same"))
    speech = env_t > 10 ** (-44 / 20)

    def mapping(o):
        f = min(len(tmap) - 1, o / HOP)
        i0 = int(f)
        i1 = min(len(tmap) - 1, i0 + 1)
        return (tmap[i0] + (tmap[i1] - tmap[i0]) * (f - i0)) * HOP

    y = wsola(clean, mapping, len(target))
    # gate: follow target speech/silence with smooth edges
    g = np.convolve(speech.astype(np.float32), np.ones(960) / 960, "same")
    y *= np.clip(g * 1.5, 0, 1)
    peak = max(1e-6, np.abs(y).max())
    y = y / peak * min(0.95, np.abs(clean).max())
    wavfile.write(out_p, SR, (np.clip(y, -1, 1) * 32767).astype(np.int16))
    print("ok", len(y) / SR, "s; path length", len(path))


if __name__ == "__main__":
    main()
