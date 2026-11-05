"""Procedural soundtrack + sound design for the Home Deluxe Black Friday spot.

Writes music.wav, sfx.wav (stems) and mix.wav (voice + ducked music + sfx), 48 kHz stereo.
Usage: python3 audio.py <voice_wav> <out_dir>
"""
import sys
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi, fftconvolve
from scipy.io import wavfile
from timeline import *

SR = 48000
N = int(OUT_DURATION * SR)
rng = np.random.default_rng(7)


# ----------------------------------------------------------------- helpers
def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def mtof(m):
    return 440.0 * 2 ** ((np.asarray(m, float) - 69) / 12)


def filt(x, kind, fc, order=2):
    nyq = SR / 2
    if kind == "bp":
        lo, hi = fc
        sos = butter(order, [max(lo, 20) / nyq, min(hi, nyq * 0.95) / nyq], "band", output="sos")
    else:
        sos = butter(order, min(fc, nyq * 0.95) / nyq, {"lp": "low", "hp": "high"}[kind], output="sos")
    return sosfilt(sos, x, axis=0)


def sweep_filter(x, kind, fc_curve, block=256, order=2):
    """Time-varying low/high/band pass (block-wise coefficient update)."""
    y = np.zeros_like(x)
    zi = None
    nyq = SR / 2
    for i in range(0, len(x), block):
        fc = fc_curve[min(i, len(fc_curve) - 1)]
        if kind == "bp":
            c, q = fc
            lo, hi = c / q, c * q
            sos = butter(order, [max(lo, 20) / nyq, min(hi, nyq * 0.95) / nyq], "band", output="sos")
        else:
            sos = butter(order, np.clip(fc, 20, nyq * 0.95) / nyq, {"lp": "low", "hp": "high"}[kind], output="sos")
        if zi is None or zi.shape != (sos.shape[0], 2):
            zi = sosfilt_zi(sos) * 0
        y[i:i + block], zi = sosfilt(sos, x[i:i + block], zi=zi)
    return y


def saw(freq, n):
    f = np.broadcast_to(np.asarray(freq, float), (n,)).copy()
    dt = f / SR
    ph = (rng.random() + np.cumsum(dt)) % 1.0
    y = 2 * ph - 1
    m = ph < dt
    x = ph[m] / dt[m]
    y[m] -= x + x - x * x - 1
    m = ph > 1 - dt
    x = (ph[m] - 1) / dt[m]
    y[m] -= x * x + x + x + 1
    return y


def sine(freq, n, phase=0.0):
    f = np.broadcast_to(np.asarray(freq, float), (n,))
    return np.sin(2 * np.pi * np.cumsum(f) / SR + phase)


def noise(n):
    return rng.standard_normal(n)


def adsr(n, a=0.005, d=0.1, s=0.0, r=0.05):
    t = np.arange(n) / SR
    e = np.ones(n) * s
    na, nd = int(a * SR), int(d * SR)
    e[:na] = np.linspace(0, 1, na, endpoint=False) if na else e[:na]
    if nd:
        seg = slice(na, min(n, na + nd))
        k = np.arange(seg.stop - seg.start) / max(nd, 1)
        e[seg] = 1 - (1 - s) * k
    nr = int(r * SR)
    if nr and n > nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def stereo(x, pan=0.0):
    l = np.cos((pan + 1) * np.pi / 4)
    r = np.sin((pan + 1) * np.pi / 4)
    return np.stack([x * l, x * r], axis=1) * 1.4142


def place(buf, x, t, gain=1.0, pan=0.0):
    if x.ndim == 1:
        x = stereo(x, pan)
    i = int(round(t * SR))
    if i < 0:
        x = x[-i:]
        i = 0
    j = min(len(buf), i + len(x))
    if j > i:
        buf[i:j] += x[: j - i] * gain


def make_ir(dur=2.2, decay=3.2, damp=6000, pre=0.012):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = np.zeros((n, 2))
    for c in range(2):
        v = noise(n) * np.exp(-t * decay)
        v = filt(v, "lp", damp)
        ir[:, c] = v
    ir[: int(pre * SR)] = 0
    return ir / np.sqrt((ir ** 2).sum(0)).max()


IR_ROOM = make_ir(1.2, 5.5, 7000)
IR_HALL = make_ir(3.0, 2.2, 5500, 0.02)


def reverb(x, ir, wet=0.3):
    if x.ndim == 1:
        x = stereo(x)
    y = np.stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return x * (1 - wet) + y * wet


def delay(x, t, fb=0.35, mix=0.3, n_taps=5, pingpong=True):
    if x.ndim == 1:
        x = stereo(x)
    y = x.copy()
    d = int(t * SR)
    g = mix
    for k in range(1, n_taps + 1):
        tap = np.zeros_like(x)
        if d * k < len(x):
            src = x[: len(x) - d * k]
            if pingpong and k % 2 == 1:
                src = src[:, ::-1]
            tap[d * k:] = src
            y += filt(tap, "lp", 5000 - 500 * k) * g
        g *= fb
    return y


def soft_clip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


# ------------------------------------------------------------ instruments
def kick(gain=1.0, dur=0.42):
    t = t_axis(dur)
    f = 46 + 120 * np.exp(-t * 32)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.0)
    click = filt(noise(len(t)), "hp", 2500) * np.exp(-t * 350) * 0.35
    return soft_clip((body + click) * 1.3, 1.6) * gain


def soft_kick(gain=1.0):
    t = t_axis(0.25)
    f = 60 + 70 * np.exp(-t * 40)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14) * gain


def clap(gain=1.0):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    env = np.zeros(n)
    for k, off in enumerate([0, 0.009, 0.018]):
        i = int(off * SR)
        env[i:] += np.exp(-(t[: n - i]) * 180) * (0.7 if k < 2 else 1)
    env += np.exp(-t * 18) * 0.35 * (t > 0.02)
    x = filt(noise(n), "bp", (900, 3200)) * env
    return x * gain * 1.6


def snap(gain=1.0):
    t = t_axis(0.12)
    x = filt(noise(len(t)), "bp", (1800, 5000)) * np.exp(-t * 90)
    x += np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 120) * 0.3
    return x * gain


def hat(open_=False, gain=1.0):
    t = t_axis(0.32 if open_ else 0.06)
    x = filt(noise(len(t)), "hp", 7500 if not open_ else 6500)
    x *= np.exp(-t * (11 if open_ else 75))
    return x * gain


def snare(gain=1.0):
    t = t_axis(0.22)
    tone = np.sin(2 * np.pi * (190 + 60 * np.exp(-t * 40)) * t) * np.exp(-t * 25)
    nz = filt(noise(len(t)), "bp", (1500, 8000)) * np.exp(-t * 22)
    return (tone * 0.5 + nz) * gain


def crash(gain=1.0, dur=2.6):
    t = t_axis(dur)
    x = filt(noise(len(t)), "hp", 4500) * np.exp(-t * 1.6)
    x += filt(noise(len(t)), "bp", (3000, 9000)) * np.exp(-t * 4) * 0.5
    x *= 1 - np.exp(-t * 400)
    return reverb(x, IR_ROOM, 0.25) * gain


def supersaw(midi, dur, cutoff=3500, voices=5, detune=0.12, env=None):
    n = int(dur * SR)
    out = np.zeros(n)
    for m in np.atleast_1d(midi):
        for v in range(voices):
            dc = (v - (voices - 1) / 2) / ((voices - 1) / 2) * detune
            out += saw(mtof(m + dc), n)
    out /= voices * len(np.atleast_1d(midi))
    if env is None:
        env = adsr(n, 0.004, dur * 0.8, 0.0, 0.02)
    out *= env
    return filt(out, "lp", cutoff)


def pluck(midi, dur=0.22, bright=6000, gain=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = mtof(midi)
    x = saw(f, n) * 0.6 + np.sign(sine(f, n)) * 0.25 + sine(f * 2, n) * 0.15
    fc = 500 + bright * np.exp(-t * 28)
    x = sweep_filter(x, "lp", np.repeat(fc[::256], 256)[:n] if n > 256 else fc)
    return x * np.exp(-t * 14) * adsr(n, 0.002, 0, 1, 0.01) * gain


def pizz(midi, dur=0.18, gain=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = mtof(midi)
    x = sine(f, n) + 0.35 * sine(2 * f, n) + 0.12 * sine(3 * f, n)
    return x * np.exp(-t * 22) * (1 - np.exp(-t * 900)) * gain


def bass_note(midi, dur, gain=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = mtof(midi)
    sub = sine(f, n)
    mid = saw(f, n) + 0.5 * saw(f * 1.005, n)
    fc = 350 + 1300 * np.exp(-t * 16)
    mid = sweep_filter(mid, "lp", np.repeat(fc[::256], 256)[:n])
    x = sub * 0.85 + mid * 0.45
    return soft_clip(x * adsr(n, 0.003, 0, 1, 0.03), 1.3) * gain


def pad(chord, dur, cutoff=1400, gain=1.0):
    n = int(dur * SR)
    x = supersaw(chord, dur, cutoff=cutoff, voices=7, detune=0.18, env=adsr(n, 0.25, 0, 1, 0.4))
    return x * gain


# ------------------------------------------------------------ sound design
def whoosh(dur=0.6, f0=300, f1=4500, gain=1.0, peak=0.6, pan_sweep=True):
    n = int(dur * SR)
    u = np.arange(n) / n
    centre = f0 * (f1 / f0) ** u
    x = sweep_filter(noise(n), "bp", list(zip(np.repeat(centre[::256], 256)[:n], [1.8] * n)), order=1)
    env = np.where(u < peak, (u / peak) ** 2.2, ((1 - u) / (1 - peak)) ** 1.6)
    x = x * env
    if pan_sweep:
        pan = np.linspace(-0.7, 0.7, n)
        st = np.stack([x * np.cos((pan + 1) * np.pi / 4), x * np.sin((pan + 1) * np.pi / 4)], 1) * 1.414
    else:
        st = stereo(x)
    return reverb(st, IR_ROOM, 0.2) * gain * 2.2


def swish(gain=1.0):
    return whoosh(0.22, 1500, 7000, gain, peak=0.45, pan_sweep=False)


def impact(gain=1.0, size=1.0):
    t = t_axis(2.2)
    f = 32 + 70 * np.exp(-t * 9)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (2.4 / size))
    crack = filt(noise(len(t)), "lp", 2500) * np.exp(-t * 28)
    top = filt(noise(len(t)), "hp", 3000) * np.exp(-t * 18) * 0.25
    x = soft_clip(boom * 1.1 + crack * 0.8 + top, 1.4)
    return reverb(x, IR_HALL, 0.28) * gain


def thud(gain=1.0):
    t = t_axis(0.5)
    f = 48 + 55 * np.exp(-t * 25)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)
    dirt = filt(noise(len(t)), "bp", (200, 1800)) * np.exp(-t * 16) * 0.6
    crumble = filt(noise(len(t)), "bp", (1500, 5000)) * (rng.random(len(t)) > 0.985) * np.exp(-t * 6) * 0.8
    return reverb(body + dirt + crumble, IR_ROOM, 0.18) * gain


def riser(dur=1.2, gain=1.0):
    n = int(dur * SR)
    u = np.arange(n) / n
    nz = sweep_filter(noise(n), "hp", np.repeat((300 * (30 ** u))[::256], 256)[:n])
    tone = saw(220 * 2 ** (2.5 * u), n) * 0.25 + saw(221.5 * 2 ** (2.5 * u), n) * 0.25
    tone = filt(tone, "lp", 4000)
    x = (nz * 0.7 + tone) * u ** 2.0
    return reverb(x, IR_HALL, 0.3) * gain


def reverse_cymbal(dur=1.0, gain=1.0):
    c = crash(1.0, dur)[::-1]
    return c * gain


def kaching(gain=1.0):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    # 'ka' : drawer/mechanical click
    ka = filt(noise(n), "bp", (2500, 7000)) * np.exp(-t * 160)
    ka += filt(noise(n), "bp", (400, 1500)) * np.exp(-t * 60) * 0.5
    out += ka * 0.9
    # 'ching' : two inharmonic bells, slightly delayed
    for f0, off, g in [(2093.0, 0.06, 0.6), (2637.0, 0.075, 0.5), (3136.0, 0.09, 0.3)]:
        i = int(off * SR)
        tt = t[: n - i]
        bell = np.zeros(n - i)
        for ratio, dec, a in [(1, 3.2, 1), (2.76, 5, 0.45), (5.4, 8, 0.25), (8.93, 12, 0.12)]:
            bell += a * np.sin(2 * np.pi * f0 * ratio * tt) * np.exp(-tt * dec)
        out[i:] += bell * g * (1 - np.exp(-tt * 2000))
    # coin sparkle
    for k in range(10):
        s = 0.08 + rng.random() * 0.35
        i = int(s * SR)
        f = 4000 + rng.random() * 4000
        tt = t[: n - i]
        out[i:] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 30) * 0.08
    return reverb(out * 0.6, IR_ROOM, 0.22) * gain


def tick(gain=1.0):
    t = t_axis(0.03)
    x = filt(noise(len(t)), "bp", (2500, 6000)) * np.exp(-t * 500)
    x += np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 400) * 0.4
    return x * gain


def pop(gain=1.0, f0=500):
    t = t_axis(0.12)
    f = f0 + f0 * 1.6 * (1 - np.exp(-t * 60))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 38) * (1 - np.exp(-t * 3000))
    return reverb(x, IR_ROOM, 0.15) * gain


def click(gain=1.0):
    t = t_axis(0.06)
    x = filt(noise(len(t)), "bp", (1500, 6000)) * np.exp(-t * 600)
    i = int(0.035 * SR)
    x[i:] += filt(noise(len(t) - i), "bp", (1000, 4000)) * np.exp(-t[: len(t) - i] * 700) * 0.6
    x += np.sin(2 * np.pi * 1200 * t) * np.exp(-t * 200) * 0.25
    return x * gain


def sparkle(dur=0.7, gain=1.0, n_ping=16):
    n = int(dur * SR)
    out = np.zeros(n)
    t = np.arange(n) / SR
    for k in range(n_ping):
        s = (k / n_ping) * dur * 0.7 + rng.random() * 0.03
        i = int(s * SR)
        f = 3000 + (k / n_ping) * 4000 + rng.random() * 600
        tt = t[: n - i]
        out[i:] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 18) * 0.12
    return reverb(delay(out, 0.09, 0.3, 0.25), IR_HALL, 0.3) * gain


def splash(dur=1.1, gain=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = filt(noise(n), "bp", (400, 6000))
    bub = np.zeros(n)
    for k in range(40):
        i = int(rng.random() * 0.8 * SR)
        f = 300 + rng.random() * 900
        m = min(int(0.06 * SR), n - i)
        tt = np.arange(m) / SR
        bub[i:i + m] += np.sin(2 * np.pi * (f + 3000 * tt) * tt) * np.exp(-tt * 60) * 0.3
    env = (1 - np.exp(-t * 25)) * np.exp(-t * 3.2)
    return reverb((x * 0.5 + bub) * env, IR_ROOM, 0.3) * gain


# --------------------------------------------------------------- music
def build_music():
    drums = np.zeros((N, 2))
    bass = np.zeros((N, 2))
    harm = np.zeros((N, 2))
    lead = np.zeros((N, 2))
    fx = np.zeros((N, 2))
    sc_times = []  # kick times for sidechain

    chords = {"Fm": [53, 56, 60, 65], "Db": [53, 56, 61, 65], "Ab": [51, 56, 60, 63], "Eb": [51, 55, 58, 63]}
    roots = {"Fm": 41, "Db": 37, "Ab": 44, "Eb": 39}
    prog = ["Fm", "Db", "Ab", "Eb"]
    s16 = BEAT / 4

    # ---- intro: cheeky pizzicato groove (bars -3..-1 relative to drop), cut at freeze
    intro_motif = [0, 3, 6, 8, 11, 14]
    for bar in range(-4, 0):
        t0 = DROP_A + bar * BAR
        ch = prog[(bar + 4) % 4]
        tones = chords[ch]
        for k, step in enumerate(intro_motif):
            t = t0 + step * s16
            if 0 <= t < CUT_FREEZE:
                note = tones[(k * 2) % 4] + 12
                place(harm, filt(pizz(note, 0.2, 0.32), 'lp', 2800), t, pan=-0.25 if k % 2 else 0.25)
        for b in range(4):
            t = t0 + b * BEAT
            if 0 <= t < CUT_FREEZE:
                if b in (1, 3):
                    place(drums, filt(snap(0.42), 'lp', 4200), t, pan=0.15)
                if b in (0, 2):
                    place(drums, soft_kick(0.5), t)
                place(drums, hat(False, 0.12), t + BEAT / 2, pan=0.3)
        rt = t0
        for e in range(8):
            t = rt + e * BEAT / 2
            if 0 <= t < CUT_FREEZE and e % 2 == 1:
                place(bass, bass_note(roots[ch] + 12, 0.16, 0.22), t)

    # ---- drop A (8 bars) + drop B (2 bars)
    def groove_bar(bar_idx, t0, with_lead):
        ch = prog[bar_idx % 4]
        for b in range(4):
            t = t0 + b * BEAT
            place(drums, kick(1.05), t)
            sc_times.append(t)
            if b in (1, 3):
                place(drums, clap(0.42), t, pan=0.05)
            place(drums, hat(True, 0.16), t + BEAT / 2, pan=0.25)
        for s in range(16):
            vel = 0.10 if s % 2 == 0 else 0.06
            place(drums, hat(False, vel), t0 + s * s16, pan=-0.3)
        # offbeat rolling bass
        for e in range(8):
            t = t0 + e * BEAT / 2
            if e % 2 == 1:
                place(bass, bass_note(roots[ch], BEAT / 2 * 0.9, 0.5), t)
            else:
                place(bass, bass_note(roots[ch] - 12, BEAT / 2 * 0.6, 0.18), t)
        # house chord stabs
        for step in [0, 3, 6, 10, 13]:
            place(harm, filt(supersaw(chords[ch], 0.16, cutoff=3400), 'hp', 260), t0 + step * s16, gain=0.24)
        if with_lead:
            arp = chords[ch][1:] + [chords[ch][1] + 12]
            pattern = [0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 3, 1, 2, 0, 2]
            for s, idx in enumerate(pattern):
                place(lead, pluck(arp[idx] + 12, 0.2, 5500, 0.16), t0 + s * s16, pan=0.35 if s % 2 else -0.35)

    for bar in range(GROOVE_BARS):
        groove_bar(bar, DROP_A + bar * BAR, with_lead=bar >= 4)
    for bar in range(2):
        groove_bar(bar, DROP_B + bar * BAR, with_lead=True)

    # crashes on section starts
    for t, g in [(DROP_A, 0.32), (DROP_A + 4 * BAR, 0.2), (DROP_B, 0.32)]:
        place(fx, crash(g), t)

    # fill at end of bar 7 (snare 16ths)
    for s in range(8):
        t = DROP_A + (GROOVE_BARS - 1) * BAR + 2 * BEAT + s * s16
        place(drums, snare(0.12 + 0.03 * s), t, pan=0.1)

    # ---- break (bar 8): filtered pad + building snare roll
    place(harm, pad(chords["Fm"], BAR / 2 + 0.3, 1100, 0.35), BREAK)
    place(harm, pad(chords["Db"], BAR / 2 + 0.3, 1400, 0.35), BREAK + BAR / 2)
    place(bass, bass_note(roots["Fm"] - 12, BAR / 2, 0.35), BREAK)
    place(bass, bass_note(roots["Db"] - 12, BAR / 2, 0.35), BREAK + BAR / 2)
    roll = []
    t = BREAK + BAR / 2
    while t < DROP_B - 1e-3:
        u = (t - (BREAK + BAR / 2)) / (BAR / 2)
        roll.append((t, 0.05 + 0.2 * u))
        t += s16 if u < 0.5 else s16 / 2
    for t, g in roll:
        place(drums, snare(g), t)
    place(fx, riser(BAR, 0.22), BREAK)

    # last half bar before the end card: fill + riser
    for s in range(8):
        place(drums, snare(0.1 + 0.035 * s), DROP_B + BAR + 2 * BEAT + s * s16)

    # ---- end hit + outro tail
    place(drums, kick(1.0, 0.6), END_HIT)
    place(fx, crash(0.38, 3.5), END_HIT)
    place(harm, reverb(pad(chords["Fm"], 3.6, 2600, 0.55), IR_HALL, 0.45), END_HIT)
    place(bass, bass_note(roots["Fm"] - 12, 1.6, 0.5) * np.exp(-t_axis(1.6) * 1.6), END_HIT)
    for k, m in enumerate([72, 77, 80, 84]):
        place(lead, pluck(m, 0.6, 4500, 0.2), END_HIT + 1.05 + k * s16 * 2, pan=(-0.3, 0.3)[k % 2])

    # ---- scratch + tape stop at the freeze frame (built from the intro material itself)
    pre = harm + bass + drums
    seg_len = int(0.6 * SR)
    i0 = int(CUT_FREEZE * SR)
    src = pre[i0 - seg_len:i0].copy()
    rate = np.concatenate([np.linspace(1.0, -2.2, int(0.09 * SR)),
                           np.linspace(-2.2, 1.8, int(0.10 * SR)),
                           np.linspace(1.8, 0.0, int(0.38 * SR))])
    pos = np.clip(seg_len - 1 - 0.30 * SR + np.cumsum(rate), 0, seg_len - 2)
    i_ = pos.astype(int)
    frac = (pos - i_)[:, None]
    scr = src[i_] * (1 - frac) + src[i_ + 1] * frac
    scr *= np.linspace(1, 0.0, len(scr))[:, None] ** 0.6
    # silence everything between the stop and the drop (kills intro tails)
    j0 = int((DROP_A - 0.005) * SR)
    for st in (harm, bass, drums, lead):
        st[i0:j0] = 0
    return drums, bass, harm, lead, fx, sc_times, scr, i0


def main():
    voice_path, out_dir = sys.argv[1], sys.argv[2]

    d2, b2, h2, l2, fx2, sc_times, scr, i0 = build_music()

    # sidechain pump on bass / harmony / lead (only after the drop)
    pump = np.ones(N)
    rel = int(0.2 * SR)
    curve = 1 - 0.8 * np.exp(-np.arange(rel) / (0.06 * SR))
    for t in sc_times:
        i = int(t * SR)
        j = min(N, i + rel)
        pump[i:j] = np.minimum(pump[i:j], curve[: j - i])
    pump = pump[:, None]
    lead_fx = delay(l2 * pump, 3 * BEAT / 4, 0.32, 0.28)
    music = d2 + b2 * pump + h2 * pump * 0.9 + lead_fx + fx2
    place(music, scr * 0.9, CUT_FREEZE)

    # glue: gentle bus saturation
    music = soft_clip(music * 0.9, 1.02)

    # ---------------------------------------------------------- SFX bus (v4 scenes)
    sfx = np.zeros((N, 2))

    def ticks(t0, t1, gain=0.3, step=0.05):
        k = 0
        while t0 + k * step < t1 - 0.02:
            place(sfx, tick(gain), t0 + k * step)
            k += 1

    # S1 UGC hook
    place(sfx, whoosh(0.30, 5000, 400, 0.4, peak=0.05), 0.0)
    place(sfx, impact(0.30, 0.6), 0.0)
    place(sfx, impact(0.50, 0.7), T["bf"])
    place(sfx, pop(0.5, 520), T["ten"])
    place(sfx, swish(0.6), T["strike10"])
    # zoom-through the patio door + FPV flight into the garden, drop on landing
    place(sfx, whoosh(0.34, 300, 7000, 0.55, peak=0.95), CUT_UGC - 0.32)
    place(sfx, impact(0.45, 0.8), CUT_UGC)
    place(sfx, whoosh(1.9, 250, 5200, 0.45, peak=0.85), CUT_UGC + 0.05)
    place(sfx, reverse_cymbal(1.3, 0.45), CUT_GARDEN - 1.3)
    place(sfx, riser(1.6, 0.30), CUT_GARDEN - 1.6)
    place(sfx, impact(1.0, 1.3), CUT_GARDEN)
    # kinetic numbers + fence panels slamming in
    place(sfx, pop(0.45, 480), T["n15_in"])
    place(sfx, swish(0.45), T["n15_strike"])
    place(sfx, pop(0.45, 560), T["n20_in"])
    place(sfx, swish(0.45), T["n20_strike"])
    place(sfx, impact(0.85, 1.0), T["slam25"])
    place(sfx, pop(0.35, 640), T["auf"])
    for k, t in enumerate(FENCE_THUDS):
        place(sfx, thud(0.75 if k in (6, 7) else 0.55), t, pan=float(rng.uniform(-0.4, 0.4)))
    place(sfx, whoosh(0.45, 800, 5000, 0.30), T["out25"])
    # fence hero + ALIRA card
    c0, c1 = COUNTERS["fence"]
    place(sfx, swish(0.5), T["fence_card"])
    ticks(c0, c1)
    place(sfx, kaching(0.75), c1 + 0.02)
    # whip pan -> sauna drop
    place(sfx, whoosh(0.46, 900, 7500, 0.45, peak=0.5), CUT_SAUNA - 0.16)
    place(sfx, whoosh(1.1, 400, 2500, 0.35, peak=0.9), SAUNA_LAND - 1.05)
    place(sfx, impact(1.0, 1.4), SAUNA_LAND)
    place(sfx, thud(0.7), SAUNA_LAND + 0.04)
    c0, c1 = COUNTERS["sauna"]
    place(sfx, swish(0.5), T["sauna_card"])
    ticks(c0, c1)
    place(sfx, kaching(0.75), c1 + 0.02)
    # crash zoom -> whirlpool drop with splash
    place(sfx, whoosh(0.30, 500, 6000, 0.45, peak=0.8), CUT_WHIRL - 0.22)
    place(sfx, impact(0.5, 0.8), CUT_WHIRL)
    place(sfx, impact(0.95, 1.3), WHIRL_LAND)
    place(sfx, splash(1.4, 0.55), WHIRL_LAND - 0.02)
    place(sfx, splash(1.0, 0.30), WHIRL_LAND + 0.35)
    c0, c1 = COUNTERS["whirl"]
    place(sfx, swish(0.5), T["whirl_card"])
    ticks(c0, c1)
    place(sfx, kaching(0.75), c1 + 0.02)
    # spin-zoom into the blue-hour hero shot, summary
    place(sfx, reverse_cymbal(0.5, 0.4), CUT_WIDE - 0.5)
    place(sfx, whoosh(0.5, 250, 6000, 0.5, peak=0.5), CUT_WIDE - 0.25)
    place(sfx, impact(0.6, 1.0), CUT_WIDE)
    for k, t in enumerate(T["sum_chips"]):
        place(sfx, pop(0.35, 520 + 80 * k), t)
    place(sfx, whoosh(0.35, 600, 3000, 0.3), T["merge"][0] - 0.05)
    c0, c1 = COUNTERS["total"]
    ticks(c0, c1, 0.32)
    place(sfx, kaching(0.95), c1 + 0.02)
    place(sfx, impact(0.45, 0.8), c1 + 0.02)
    place(sfx, swish(0.5), T["banner"])
    # zoom into the savings box -> end card
    place(sfx, reverse_cymbal(0.7, 0.45), CUT_END - 0.7)
    place(sfx, whoosh(0.42, 200, 6500, 0.5, peak=0.92), CUT_END - 0.40)
    place(sfx, impact(0.9, 1.4), CUT_END)
    place(sfx, impact(0.22, 0.6), CUT_END + 0.35)
    place(sfx, pop(0.35, 600), CUT_END + 0.98)
    place(sfx, sparkle(0.8, 0.5), CUT_END + 1.65)
    place(sfx, click(0.6), CUT_END + 2.30)

    # ---------------------------------------------------------- voice + ducking
    sr_v, v = wavfile.read(voice_path)
    assert sr_v == SR, sr_v
    v = v.astype(np.float64) / 32768.0
    if v.ndim == 1:
        v = np.stack([v, v], 1)
    voice = np.zeros((N, 2))
    voice[: min(N, len(v))] = v[:N]
    env = np.abs(voice).max(1)
    win = int(0.02 * SR)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    active = (env > 10 ** (-38 / 20)).astype(float)
    # attack 25 ms, release 350 ms smoothing
    g = np.zeros(N)
    a_att, a_rel = np.exp(-1 / (0.025 * SR)), np.exp(-1 / (0.35 * SR))
    acc = 0.0
    for i in range(0, N, 64):
        tgt = active[i]
        coef = a_att ** 64 if tgt > acc else a_rel ** 64
        acc = tgt + (acc - tgt) * coef
        g[i:i + 64] = acc
    duck = (1 - 0.66 * g)[:, None]        # ~ -9.4 dB under speech
    bed_gain = np.full(N, 0.30)
    bed_gain[: int(CUT_GARDEN * SR)] = 0.40   # cheeky intro sits a bit higher
    music_d = music * duck * bed_gain[:, None]
    sfx_d = sfx * (1 - 0.3 * g)[:, None]

    mix = voice * 1.0 + music_d + sfx_d * 0.5
    nf = int(0.45 * SR)
    mix[-nf:] *= np.linspace(1, 0, nf)[:, None] ** 1.5
    peak = np.abs(mix).max()
    sc_ = 0.98 / max(peak, 1e-6)
    mix = soft_clip(mix * sc_, 1.05) * 0.95

    def w(name, x):
        x = x / max(np.abs(x).max(), 1e-6) * 0.95
        wavfile.write(f"{out_dir}/{name}", SR, (x * 32767).astype(np.int16))

    w("music.wav", music)
    w("sfx.wav", sfx)
    w("mix.wav", mix)
    print("ok", mix.shape, "peak", peak)


if __name__ == "__main__":
    main()
