"""Shepard-Risset-Glissando: der akustische Zwilling der optischen Täuschung.

Der Ton scheint endlos zu steigen, kommt aber nie oben an. Er steigt genau eine
Oktave pro Raum (Raum halb so groß  ->  Frequenz doppelt so hoch) und ist exakt
periodisch mit der Bildschleife, d. h. auch der Ton loopt nahtlos.

Usage: python3 audio.py PERIOD_SECONDS LOOPS out.wav
"""
import sys
import wave

import numpy as np

SR = 48000


def shepard_stack(n, period, fmin, n_oct, center_oct, sigma, phase0):
    """Ein Stapel oktavversetzter Sinusstimmen, exakt periodisch über `period`."""
    t = np.arange(n) / SR
    x_t = t / period                      # 0..1 Oktave über eine Periode
    out = np.zeros(n)
    phi = phase0
    for k in range(n_oct):
        x = k + x_t                       # Lage der Stimme in Oktaven
        amp = np.exp(-0.5 * ((x - center_oct) / sigma) ** 2)
        # analytisch integrierte Phase für f(t) = fmin * 2^(k + t/T)
        ph = phi + 2 * np.pi * fmin * 2 ** k * period * (2 ** x_t - 1) / np.log(2)
        out += amp * np.sin(ph)
        # Phase so wählen, dass Stimme k am Periodenende nahtlos in Stimme k+1 übergeht
        phi = phi + 2 * np.pi * fmin * 2 ** k * period / np.log(2)
    return out


def circular_filter(sig, lo, hi):
    spec = np.fft.rfft(sig)
    f = np.fft.rfftfreq(len(sig), 1 / SR)
    mask = np.exp(-0.5 * (np.log2(np.maximum(f, 1) / np.sqrt(lo * hi)) / (np.log2(hi / lo) / 2)) ** 2)
    return np.fft.irfft(spec * mask, len(sig))


def circular_reverb(sig, rng, decay=2.8, wet=0.35):
    n = len(sig)
    ir_len = int(decay * SR)
    t = np.arange(ir_len) / SR
    ir = rng.standard_normal(ir_len) * np.exp(-t * 6.9 / decay)   # -60 dB nach `decay` s
    ir = circular_filter(np.pad(ir, (0, n - ir_len)), 120, 5000)[:n]
    ir /= np.sqrt(np.sum(ir ** 2))
    wet_sig = np.fft.irfft(np.fft.rfft(sig) * np.fft.rfft(ir), n)  # zirkulär => periodisch
    return (1 - wet) * sig + wet * wet_sig


def main():
    period = float(sys.argv[1])
    loops = int(sys.argv[2])
    out_path = sys.argv[3]
    n = int(round(period * SR))
    rng = np.random.default_rng(7)
    t = np.arange(n) / SR
    ph = t / period

    chans = []
    for ch in range(2):
        root = shepard_stack(n, period, 27.5, 9, 4.0, 1.05, rng.uniform(0, 2 * np.pi))       # A
        fifth = shepard_stack(n, period, 41.2, 9, 3.6, 1.05, rng.uniform(0, 2 * np.pi))      # E
        tone = root + 0.55 * fifth
        # sanftes Pulsieren, synchron zur Bewegung
        tone *= 0.85 + 0.15 * np.cos(2 * np.pi * ph)
        # "Whoosh" beim Durchschreiten des Torbogens (t ~ 0.92 .. 1.0 der Schleife)
        noise = circular_filter(rng.standard_normal(n), 250, 2500)
        noise /= np.max(np.abs(noise))
        dphi = (ph - 0.965 + 0.5) % 1.0 - 0.5
        env = np.exp(-0.5 * (dphi / 0.045) ** 2)
        tone = tone / np.max(np.abs(tone)) + 0.22 * noise * env
        chans.append(circular_reverb(tone, rng))

    st = np.stack(chans, axis=1)
    st /= np.max(np.abs(st))
    st *= 10 ** (-7 / 20)                 # Peak -7 dBFS (~ -18 LUFS, dezente Atmosphäre)
    st = np.tile(st, (loops, 1))
    pcm = (st * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote {out_path}: {len(pcm) / SR:.2f} s")


if __name__ == "__main__":
    main()
