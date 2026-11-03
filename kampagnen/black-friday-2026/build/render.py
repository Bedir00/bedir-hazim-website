"""Frame renderer: camera FX, motion graphics, TikTok-classic subtitles, animated end card.

Usage:
  python3 render.py <src.mp4> <fonts_dir> <audio.wav> <out.mp4>            full render
  python3 render.py <src.mp4> <fonts_dir> --stills t1,t2,... <out_dir>     preview stills
"""
import math
import subprocess
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

import gfx
import fx
from gfx import (W, H, NAVY, NAVY_END, WHITE, MUTED, GREY, font, clamp, prog, lerp,
                 ease_out_cubic, ease_in_cubic, ease_in_out_cubic, ease_out_back,
                 to_sprite, supersampled, shadowed, blit, clip_sprite, fill_rect,
                 ring_sprite, disc_sprite, line_sprite, draw_text)
from timeline import *

SRC, gfx.FONT_DIR = sys.argv[1], sys.argv[2]
rng = np.random.default_rng(3)


# =============================================================== sprite builders
def tight_text(txt, weight, size, color, tracking=0):
    f = font(weight, size)
    w = int(sum(f.getlength(c) for c in txt) + tracking * max(0, len(txt) - 1) + size)
    h = int(size * 1.6)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_text(ImageDraw.Draw(img), (size // 4, int(size * 1.15)), txt, f, color + (255,), tracking)
    bbox = img.getbbox()
    return img.crop(bbox)


def box(content_imgs, bg, padx, pady, gap=0, align="center", min_w=0, shadow=True):
    """Stack content images vertically inside a square-cornered box."""
    cw = max(max(i.size[0] for i in content_imgs), min_w - 2 * padx)
    ch = sum(i.size[1] for i in content_imgs) + gap * (len(content_imgs) - 1)
    bw, bh = cw + 2 * padx, ch + 2 * pady
    img = Image.new("RGBA", (bw, bh), bg + (255,))
    y = pady
    for i in content_imgs:
        x = padx if align == "left" else (bw - i.size[0]) // 2
        img.alpha_composite(i, (x, y))
        y += i.size[1] + gap
    if shadow:
        img, pad = shadowed(img)
        return img, pad
    return img, 0


def sprite_with_meta(img, pad):
    spr = to_sprite(img)
    return {"spr": spr, "pad": pad, "w": img.size[0] - 2 * pad, "h": img.size[1] - 2 * pad}


# --- subtitles (TikTok classic: per-line rounded boxes, #fefefe bg, #0f2334 text)
SUB_FONT = ("700", 56)
SUB_PADX, SUB_LINE_H, SUB_RADIUS, SUB_MAXW = 22, 82, 14, 880
SUB_CY = 1300


def wrap(txt, f, maxw):
    words = txt.split(" ")
    lines, cur = [], ""
    for w_ in words:
        cand = (cur + " " + w_).strip()
        if f.getlength(cand) + 2 * SUB_PADX > maxw and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = cand
    lines.append(cur)
    return lines


def subtitle_sprite(txt):
    f = font(*SUB_FONT)
    lines = wrap(txt, f, SUB_MAXW)
    widths = [int(f.getlength(l)) + 2 * SUB_PADX for l in lines]
    bw = max(widths) + 4
    bh = SUB_LINE_H * len(lines) + 4
    cap = f.getbbox("H")[3] - f.getbbox("H")[1]

    def fn(d, s, img):
        for k, (l, lw) in enumerate(zip(lines, widths)):
            x0 = (bw - lw) / 2
            y0 = 2 + k * SUB_LINE_H
            d.rounded_rectangle([x0 * s, y0 * s, (x0 + lw) * s, (y0 + SUB_LINE_H) * s], radius=SUB_RADIUS * s, fill=WHITE + (255,))
    img = supersampled(fn, bw, bh)
    d = ImageDraw.Draw(img)
    for k, (l, lw) in enumerate(zip(lines, widths)):
        x0 = (bw - lw) / 2 + SUB_PADX
        base = 2 + k * SUB_LINE_H + SUB_LINE_H / 2 + cap / 2
        d.text((x0, base), l, font=f, fill=NAVY + (255,), anchor="ls")
    return to_sprite(img)


# --- reusable boxes
def badge(txt, weight, size, bg, fg, padx, pady, tracking=0, shadow=True):
    img, pad = box([tight_text(txt, weight, size, fg, tracking)], bg, padx, pady, shadow=shadow)
    return sprite_with_meta(img, pad)


def sticker(lines, bg, fg, padx, pady, gap, shadow=True):
    imgs = [tight_text(t, w, s, fg, tr) for t, w, s, tr in lines]
    img, pad = box(imgs, bg, padx, pady, gap=gap, shadow=shadow)
    return sprite_with_meta(img, pad)


def card(label, name):
    imgs = [tight_text(label, "600", 32, MUTED, 4), tight_text(name, "800", 84, WHITE, 0)]
    img, pad = box(imgs, NAVY, 40, 34, gap=22, align="left")
    # extra space at the bottom for the overlapping chip
    w_, h_ = img.size
    ext = Image.new("RGBA", (w_, h_ + 40), (0, 0, 0, 0))
    ext.alpha_composite(img, (0, 0))
    # re-shadow with extended navy area
    base = Image.new("RGBA", (w_ - 2 * pad, h_ - 2 * pad + 40), NAVY + (255,))
    inner = img.crop((pad, pad, w_ - pad, h_ - pad))
    base.alpha_composite(inner, (0, 0))
    out, pad2 = shadowed(base)
    return sprite_with_meta(out, pad2)


def chip(txt, size=40, min_w=0, bg=WHITE, fg=NAVY):
    t = tight_text(txt, "800", size, fg, 0)
    img, pad = box([t], bg, 26, 18, min_w=min_w, shadow=True)
    return sprite_with_meta(img, pad)


def fmt(v):
    return f"{int(v):,}".replace(",", ".")


def strike_onto(st, p, angle=-14, color=NAVY, thick=16):
    """Return sticker sprite copy with a strike-through line drawn to progress p."""
    if p <= 0:
        return st["spr"]
    spr = st["spr"].copy()
    w, h = st["w"], st["h"]
    L = math.hypot(w, h * 0.55) * 1.02
    ln = line_sprite(L, thick, color)
    ln = clip_sprite(ln, 0, p, 0, 1)
    cx, cy = st["pad"] + w / 2, st["pad"] + h / 2
    blit(spr, ln, cx, cy, rot=angle, anchor=(0.5, 0.5))
    return spr


# =============================================================== build assets
print("building sprites ...", flush=True)
SUB_SPR = [(a, b, subtitle_sprite(t)) for a, b, t in SUBS]

BF_BADGE = badge("BLACK FRIDAY", "800", 62, NAVY, WHITE, 36, 24, tracking=3)
TEN = sticker([("10 %", "800", 118, 0), ("RABATT", "700", 30, 9)], WHITE, NAVY, 34, 26, 16)
N15 = badge("15 %", "800", 150, WHITE, NAVY, 40, 26)
N20 = badge("20 %", "800", 150, WHITE, NAVY, 40, 26)
N25 = badge("25 %", "800", 236, NAVY, WHITE, 52, 36)
AUF = badge("AUF ALLES", "800", 74, WHITE, NAVY, 34, 20, tracking=2)
RING = ring_sprite(300, 10)
DOT = disc_sprite(13)
DOT_RING = ring_sprite(26, 4)

CARDS = [
    dict(label="WPC-SICHTSCHUTZZAUN", name="ALIRA", value=280, t_in=10.50, c0=COUNTERS["fence"][0], c1=COUNTERS["fence"][1],
         t_out=99.0, seg_end=CUT_SAUNA, anchor=[(10.0, (420, 790)), (14.0, (420, 790))]),
    dict(label="FASSSAUNA", name="LAGOM DELUXE", value=1200, t_in=15.25, c0=COUNTERS["sauna"][0], c1=COUNTERS["sauna"][1],
         t_out=17.10, seg_end=CUT_WIDE, anchor=[(15.0, (560, 690)), (17.5, (560, 690))]),
    dict(label="OUTDOOR-WHIRLPOOL", name="STREAM BIG", value=1200, t_in=18.30, c0=COUNTERS["whirl"][0], c1=COUNTERS["whirl"][1],
         t_out=99.0, seg_end=CUT_WIDE, anchor=[(18.30, (560, 740)), (18.55, (560, 760)), (18.9, (560, 780)), (20.9, (520, 860)), (21.4, (515, 870))]),
]
for c in CARDS:
    c["card"] = card(c["label"], c["name"])
    final = f"ÜBER {fmt(c['value'])} € GESPART"
    c["chip_final"] = chip(final)
    c["chip_w"] = c["chip_final"]["w"]
    c["chip_cache"] = {}

SUM_CHIPS = [
    sticker([("ZAUN", "600", 24, 3), ("–280 €", "800", 50, 0)], WHITE, NAVY, 26, 18, 10),
    sticker([("SAUNA", "600", 24, 3), ("–1.200 €", "800", 50, 0)], WHITE, NAVY, 26, 18, 10),
    sticker([("WHIRLPOOL", "600", 24, 3), ("–1.200 €", "800", 50, 0)], WHITE, NAVY, 26, 18, 10),
]
SUM_T = [21.62, 21.74, 21.86]
TOTAL_W, TOTAL_H = 740, 300
BANNER = badge("NUR AM BLACK-FRIDAY-WOCHENENDE", "800", 38, WHITE, NAVY, 30, 20, tracking=1)
_total_cache = {}


def total_sprite(v):
    key = int(v)
    if key in _total_cache:
        return _total_cache[key]
    img = Image.new("RGBA", (TOTAL_W, TOTAL_H), NAVY + (255,))
    l1 = tight_text("ZUSAMMEN ÜBER", "600", 32, MUTED, 4)
    l2 = tight_text(f"{fmt(v)} €", "800", 136, WHITE, 0)
    l3 = tight_text("GESPART", "700", 38, WHITE, 12)
    img.alpha_composite(l1, ((TOTAL_W - l1.size[0]) // 2, 34))
    img.alpha_composite(l2, ((TOTAL_W - l2.size[0]) // 2, 34 + l1.size[1] + 24))
    img.alpha_composite(l3, ((TOTAL_W - l3.size[0]) // 2, TOTAL_H - 34 - l3.size[1]))
    out, pad = shadowed(img)
    s = sprite_with_meta(out, pad)
    _total_cache[key] = s
    return s


# ----- end card: crop the delivered end card into its elements
def grab_frame(idx):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-vf", f"select=eq(n\\,{idx})", "-vframes", "1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(H, W, 3)


END_FRAME = grab_frame(850).astype(np.float32) / 255.0
BG_END = np.array(NAVY_END, np.float32) / 255.0


def crop_elem(x0, y0, x1, y1):
    """Crop element as sprite; alpha from distance to the end-card navy."""
    rgb = END_FRAME[y0:y1, x0:x1]
    d = np.abs(rgb - BG_END).sum(-1)
    a = np.clip(d / 0.18, 0, 1)[..., None]
    # un-mix background: rgb = a*fg + (1-a)*bg  -> premultiplied fg = rgb - (1-a)*bg
    prem = np.clip(rgb - (1 - a) * BG_END, 0, 1)
    return np.concatenate([prem, a], -1).astype(np.float32), ((x0 + x1) / 2, (y0 + y1) / 2)


END_ELEMS = {
    "logo": crop_elem(150, 240, 930, 338),
    "bar": crop_elem(106, 696, 128, 1184),
    "bf": crop_elem(158, 704, 606, 764),
    "pct": crop_elem(156, 838, 728, 1042),
    "auf": crop_elem(154, 1090, 718, 1184),
    "sub": crop_elem(156, 1266, 940, 1326),
    "cta": crop_elem(104, 1494, 976, 1636),
    "tag": crop_elem(104, 1724, 582, 1764),
}
TAP = disc_sprite(36, (120, 134, 150), 105)
TAP_EDGE = ring_sprite(36, 4, WHITE)
TAP_RING = ring_sprite(40, 5, (120, 134, 150))

# ----- generic FX buffers
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
r = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.68)) ** 2)
VIGNETTE = (1 - 0.55 * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None].astype(np.float32)
GRAIN = [cv2.GaussianBlur(rng.normal(0, 0.045, (H // 2, W // 2)).astype(np.float32), (0, 0), 0.6) for _ in range(6)]
GRAIN = [cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)[..., None] for g in GRAIN]
del yy, xx, r

SHAKES = [(1.26, 9, 11), (CUT_FREEZE, 16, 10), (CUT_GARDEN, 20, 8), (T["slam25"], 14, 9), (SAUNA_LAND, 24, 7.5),
          (WHIRL_LAND, 20, 8), (CUT_WIDE, 10, 10), (COUNTERS["total"][1], 8, 11)] + [(t, 4, 14) for t in FENCE_THUDS]
SHAKE_PH = [(rng.random() * 6.28, rng.random() * 6.28, rng.random() * 6.28) for _ in SHAKES]
PUNCHES = [(0.0, 1.14, 0.40), (CUT_FREEZE, 1.14, 0.30), (T["slam25"], 1.05, 0.30),
           (SAUNA_LAND, 1.035, 0.25), (WHIRL_LAND, 1.035, 0.25), (COUNTERS["total"][1], 1.02, 0.25)]
FLASHES = [(0.0, 0.7, 0.16), (CUT_FREEZE, 0.6, 0.18), (CUT_GARDEN, 0.75, 0.24), (T["slam25"], 0.22, 0.15),
           (CUT_SAUNA, 0.28, 0.18), (SAUNA_LAND, 0.18, 0.14), (WHIRL_LAND, 0.16, 0.14), (CUT_WIDE, 0.45, 0.22)]
# impact distortions on the background plate: (t0, cx, cy, max radius, duration, amplitude)
SHOCKS = [(T["slam25"] + 0.02, 540, 350, 900, 0.45, 16), (SAUNA_LAND, 540, 1000, 1100, 0.55, 30),
          (WHIRL_LAND, 585, 1150, 1100, 0.55, 26)]
# chromatic-aberration pulses: (t0, px, duration)
CHROMA = [(0.0, 12, 0.30), (1.26, 6, 0.15), (CUT_FREEZE, 14, 0.25), (T["slam25"], 10, 0.20), (SAUNA_LAND, 10, 0.22),
          (WHIRL_LAND, 9, 0.22), (COUNTERS["total"][1], 7, 0.18)]


def segment_end(t):
    for c in (CUT_FREEZE, CUT_GARDEN, CUT_SAUNA, CUT_WIDE, CUT_END):
        if t < c:
            return c
    return 1e9


def camera(t):
    s = 1.0
    for t0, amp, dur in PUNCHES:
        if t0 <= t < t0 + dur:
            s *= lerp(amp, 1.0, ease_out_cubic(prog(t, t0, t0 + dur)))
    if CUT_FREEZE <= t < CUT_GARDEN:
        s *= lerp(1.0, 1.07, ease_in_out_cubic(prog(t, CUT_FREEZE, CUT_GARDEN)))
    dx = dy = rot = 0.0
    seg_end = segment_end(t)
    for (t0, amp, dec), (p1, p2, p3) in zip(SHAKES, SHAKE_PH):
        if t0 <= t and segment_end(t0) == seg_end:
            e = amp * math.exp(-(t - t0) * dec)
            if e > 0.15:
                k = t - t0
                dx += e * math.sin(2 * math.pi * 19 * k + p1)
                dy += e * math.sin(2 * math.pi * 23 * k + p2)
                rot += e * 0.035 * math.sin(2 * math.pi * 13 * k + p3)
    if abs(dx) + abs(dy) > 0.01:
        s *= 1 + 2.2 * (abs(dx) + abs(dy)) / W
    return s, dx, dy, rot


def apply_camera(frame, t):
    s, dx, dy, rot = camera(t)
    if abs(s - 1) < 1e-4 and abs(dx) < 0.01 and abs(dy) < 0.01 and abs(rot) < 1e-3:
        return frame
    M = cv2.getRotationMatrix2D((W / 2, H / 2), rot, s)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


# =============================================================== per-element drawing
def draw_subtitles(f, t):
    for a, b, spr in SUB_SPR:
        if a <= t < b:
            u = prog(t, a, a + 0.14)
            sc = lerp(0.82, 1.0, ease_out_back(u, 2.2))
            al = prog(t, a, a + 0.05)
            if b - t < 0.06:
                al *= (b - t) / 0.06
            blit(f, spr, W / 2, SUB_CY, scale=sc, alpha=al)


def draw_hook(f, t):
    if t >= CUT_GARDEN:
        return
    # BLACK FRIDAY badge
    if t >= 1.26:
        u = ease_out_cubic(prog(t, 1.26, 1.44))
        sc = lerp(2.3, 1.0, u)
        rot = lerp(-12, -3, u)
        bob = 3 * math.sin(2 * math.pi * (t - 1.44) / (BEAT * 2)) if t > 1.44 else 0
        blit(f, BF_BADGE["spr"], W / 2, 236 + bob, scale=sc, rot=rot, alpha=prog(t, 1.26, 1.31))
    # 10 % sticker (+ strike + fall)
    if t >= 2.24:
        u = prog(t, 2.24, 2.54)
        sc = max(0.0, ease_out_back(u, 2.0))
        rot = lerp(24, 6, ease_out_cubic(u)) + 2.5 * math.sin(2 * math.pi * 1.4 * (t - 2.24))
        x, y = 872, 452
        al = 1.0
        if t >= 4.40:
            k = t - 4.40
            y += 2100 * k * k
            x += 120 * k
            rot += 140 * k
            al = 1 - prog(t, 4.85, 5.10)
        spr = strike_onto(TEN, ease_out_cubic(prog(t, 4.06, 4.20)), angle=-20, thick=18)
        blit(f, spr, x, y, scale=sc, rot=rot, alpha=al)


def freeze_fx(f, t, idx):
    if CUT_FREEZE <= t < CUT_GARDEN:
        f *= VIGNETTE
        f += GRAIN[idx % len(GRAIN)]


def draw_numbers(f, t):
    if not (5.5 <= t < T["out25"] + 0.3):
        return
    cx, cy = W / 2, 350
    a15, s15, o15 = T["n15_in"], T["n15_strike"], T["n15_out"]
    a20, s20, o20 = T["n20_in"], T["n20_strike"], T["n20_out"]
    sl, au, wb, ou = T["slam25"], T["auf"], T["wobble"], T["out25"]
    # 15 %
    if a15 <= t < o15 + 0.24:
        u = prog(t, a15, a15 + 0.22)
        sc = max(0, ease_out_back(u, 2.0))
        x, rot, al = cx, -4, prog(t, a15, a15 + 0.06)
        if t >= o15:
            k = ease_in_cubic(prog(t, o15, o15 + 0.22))
            x -= 1000 * k
            rot -= 30 * k
            al *= 1 - k
        blit(f, strike_onto(N15, ease_out_cubic(prog(t, s15, s15 + 0.10))), x, cy, scale=sc, rot=rot, alpha=al)
    # 20 %
    if a20 <= t < o20 + 0.22:
        u = prog(t, a20, a20 + 0.22)
        sc = max(0, ease_out_back(u, 2.0))
        x, rot, al = cx, 4, prog(t, a20, a20 + 0.06)
        if t >= o20:
            k = ease_in_cubic(prog(t, o20, o20 + 0.20))
            x += 1000 * k
            rot += 30 * k
            al *= 1 - k
        blit(f, strike_onto(N20, ease_out_cubic(prog(t, s20, s20 + 0.10)), angle=14), x, cy, scale=sc, rot=rot, alpha=al)
    # 25 % slam + AUF ALLES
    if t >= sl:
        u = prog(t, sl, sl + 0.16)
        sc = 1 + 1.6 * (1 - u) ** 2
        if t > sl + 0.16:
            sc = 1 - 0.05 * math.sin(math.pi * prog(t, sl + 0.16, sl + 0.32))
        sc *= 1 + 0.07 * math.sin(math.pi * prog(t, wb, wb + 0.26))
        rot = -2 + 3.5 * math.sin(2 * math.pi * 3 * (t - wb)) * (1 - prog(t, wb, wb + 0.54)) * (t >= wb)
        al = prog(t, sl, sl + 0.05)
        ex = ease_in_cubic(prog(t, ou, ou + 0.22))
        sc_ex, dy_ex, al_ex = lerp(1, 0.5, ex), -90 * ex, 1 - ex
        if sl + 0.04 <= t < sl + 0.56:
            v = prog(t, sl + 0.04, sl + 0.56)
            blit(f, RING, cx, cy, scale=lerp(0.35, 1.7, ease_out_cubic(v)), alpha=0.85 * (1 - v))
        blit(f, N25["spr"], cx, cy + dy_ex, scale=sc * sc_ex, rot=rot, alpha=al * al_ex)
        if t >= au:
            v = prog(t, au, au + 0.24)
            ay = cy + 150 + 60 * (1 - ease_out_cubic(v))
            blit(f, AUF["spr"], cx, ay + dy_ex * 1.2, scale=max(0, ease_out_back(v, 1.8)) * sc_ex, rot=rot - 1,
                 alpha=prog(t, au, au + 0.08) * al_ex)


def anchor_at(kf, t):
    if t <= kf[0][0]:
        return kf[0][1]
    for (t0, p0), (t1, p1) in zip(kf, kf[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0)
            return (lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u))
    return kf[-1][1]


def chip_sprite(c, v):
    key = int(v)
    if key not in c["chip_cache"]:
        c["chip_cache"][key] = chip(f"ÜBER {fmt(v)} € GESPART", min_w=c["chip_w"])
    return c["chip_cache"][key]


def draw_cards(f, t):
    X0, Y0 = 70, 190
    for c in CARDS:
        if not (c["t_in"] <= t < min(c["t_out"] + 0.3, c["seg_end"])):
            continue
        cd = c["card"]
        ex = ease_in_cubic(prog(t, c["t_out"], c["t_out"] + 0.24))
        dx_ex, al_ex = -700 * ex, 1 - ex
        # pointer line + dot (drawn first, under the card)
        ax, ay = anchor_at(c["anchor"], t)
        sx_, sy_ = X0 + 70, Y0 + cd["h"] + 30
        lp = ease_in_out_cubic(prog(t, c["t_in"] + 0.30, c["t_in"] + 0.62)) * (1 - prog(t, c["t_out"] - 0.12, c["t_out"]))
        if lp > 0:
            L = math.hypot(ax - sx_, ay - sy_)
            ang = math.degrees(math.atan2(ay - sy_, ax - sx_))
            ln = line_sprite(L, 4)
            ln = clip_sprite(ln, 0, lp, 0, 1)
            blit(f, ln, sx_, sy_, rot=ang, anchor=(0, 0.5), alpha=0.95)
            if lp >= 0.999:
                v = prog(t, c["t_in"] + 0.62, c["t_in"] + 0.82)
                blit(f, DOT, ax, ay, scale=ease_out_back(v, 2.5))
                pulse = ((t - c["t_in"] - 0.62) % 0.9) / 0.9
                blit(f, DOT_RING, ax, ay, scale=lerp(0.5, 1.9, pulse), alpha=(1 - pulse) * 0.9)
        # card box: wipe reveal from the left
        u = ease_out_cubic(prog(t, c["t_in"], c["t_in"] + 0.28))
        if u > 0:
            pad = cd["pad"]
            spr = cd["spr"]
            fullw = spr.shape[1]
            reveal = (pad + cd["w"] * u + pad * u) / fullw
            spr = clip_sprite(spr, 0, reveal, 0, 1)
            blit(f, spr, X0 - pad + dx_ex + (1 - u) * -30, Y0 - pad, anchor=(0, 0), alpha=al_ex * prog(t, c["t_in"], c["t_in"] + 0.06))
        # savings chip with counter
        chip_t = max(c["t_in"] + 0.30, c["c0"] - 0.22)
        if t >= chip_t:
            v = prog(t, chip_t, chip_t + 0.25)
            val = c["value"] * ease_out_cubic(prog(t, chip_t + 0.04, c["c1"]))
            cs = chip_sprite(c, round(val / 10) * 10 if t < c["c1"] else c["value"])
            punch = 1 + 0.12 * math.sin(math.pi * prog(t, c["c1"] + 0.03, c["c1"] + 0.25))
            cx = X0 + 30 + cs["w"] / 2 + dx_ex
            cy = Y0 + cd["h"] - 10
            blit(f, cs["spr"], cx, cy, scale=max(0, ease_out_back(v, 2.0)) * punch, rot=-1.5, alpha=al_ex)


def draw_summary(f, t):
    if not (CUT_WIDE <= t < CUT_END):
        return
    fade = 1.0
    # three chips pop in, then merge into the total
    xs = [205, 540, 875]
    cy = 300
    merge = ease_in_cubic(prog(t, 21.92, 22.10))
    for k, (st, t0) in enumerate(zip(SUM_CHIPS, SUM_T)):
        if t >= t0 and merge < 1:
            v = prog(t, t0, t0 + 0.24)
            x = lerp(xs[k], W / 2, merge)
            blit(f, st["spr"], x, cy, scale=max(0, ease_out_back(v, 2.2)) * lerp(1, 0.4, merge),
                 rot=(-3, 2, -2)[k] * (1 - merge), alpha=(1 - merge) * fade)
    tc0, tc1 = COUNTERS["total"]
    if t >= 22.00:
        v = prog(t, 22.00, 22.26)
        val = 2700 * ease_out_cubic(prog(t, tc0, tc1))
        ts = total_sprite(round(val / 10) * 10 if t < tc1 else 2700)
        punch = 1 + 0.10 * math.sin(math.pi * prog(t, tc1 + 0.02, tc1 + 0.25))
        blit(f, ts["spr"], W / 2, 318, scale=max(0, ease_out_back(v, 1.6)) * punch, alpha=fade * prog(t, 22.00, 22.06))
        if tc1 <= t < tc1 + 0.48:
            w_ = prog(t, tc1, tc1 + 0.48)
            blit(f, RING, W / 2, 318, scale=lerp(0.6, 2.0, ease_out_cubic(w_)), alpha=0.7 * (1 - w_) * fade)
    if t >= T["banner"]:
        v = ease_out_cubic(prog(t, T["banner"], T["banner"] + 0.30))
        x = lerp(W + 500, W / 2, v)
        blit(f, BANNER["spr"], x, 518, rot=-1.5, alpha=fade)


def draw_endcard(f, t):
    f[:] = BG_END
    E = END_ELEMS
    t0 = CUT_END

    def el(name, tin, dur, mode, **kw):
        spr, (cx, cy) = E[name]
        u = prog(t, t0 + tin, t0 + tin + dur)
        if u <= 0:
            return
        if mode == "fade_down":
            blit(f, spr, cx, cy - 34 * (1 - ease_out_cubic(u)), alpha=ease_out_cubic(u))
        elif mode == "grow_down":
            blit(f, clip_sprite(spr, 0, 1, 0, ease_out_cubic(u)), cx, cy)
        elif mode == "slide_right":
            v = ease_out_cubic(u)
            s2 = clip_sprite(spr, 0, 1, 0, 1)
            blit(f, s2, cx - 60 * (1 - v), cy, alpha=v)
        elif mode == "slam":
            v = ease_out_back(u, 1.6)
            blit(f, spr, cx, cy, scale=lerp(1.35, 1.0, ease_out_cubic(u)) * (0.96 + 0.04 * v), alpha=prog(t, t0 + tin, t0 + tin + 0.08))
        elif mode == "rise":
            v = ease_out_cubic(u)
            blit(f, spr, cx, cy + 28 * (1 - v), alpha=v)
        elif mode == "pop":
            blit(f, spr, cx, cy, scale=max(0, ease_out_back(u, 1.8)) * kw.get("press", 1.0), alpha=prog(t, t0 + tin, t0 + tin + 0.06))

    el("logo", 0.03, 0.40, "fade_down")
    el("bar", 0.13, 0.32, "grow_down")
    el("bf", 0.23, 0.30, "slide_right")
    el("pct", 0.35, 0.30, "slam")
    el("auf", 0.58, 0.30, "rise")
    el("sub", 0.78, 0.30, "rise")
    # CTA with breathing + tap
    press = 1.0
    tap_t = 28.70
    press *= 1 + 0.035 * math.sin(math.pi * prog(t, 28.0, 28.45))
    press *= 1 - 0.05 * math.sin(math.pi * prog(t, tap_t, tap_t + 0.18))
    el("cta", 0.98, 0.32, "pop", press=press)
    el("tag", 1.13, 0.30, "rise")
    # expanding square outline around the CTA (attention pulse)
    cta_spr, (ccx, ccy) = E["cta"]
    for k, ts in enumerate([28.0]):
        if ts <= t < ts + 0.6:
            v = prog(t, ts, ts + 0.6)
            grow = lerp(0, 34, ease_out_cubic(v))
            hw, hh = cta_spr.shape[1] / 2 + grow, cta_spr.shape[0] / 2 + grow
            a = 0.8 * (1 - v)
            th = 4
            fill_rect(f, ccx - hw, ccy - hh, ccx + hw, ccy - hh + th, WHITE, a)
            fill_rect(f, ccx - hw, ccy + hh - th, ccx + hw, ccy + hh, WHITE, a)
            fill_rect(f, ccx - hw, ccy - hh, ccx - hw + th, ccy + hh, WHITE, a)
            fill_rect(f, ccx + hw - th, ccy - hh, ccx + hw, ccy + hh, WHITE, a)
    # tap indicator
    if 28.30 <= t < 29.35:
        tx, ty = 790, 1580
        mv = ease_out_cubic(prog(t, 28.30, tap_t))
        x = lerp(tx + 180, tx, mv)
        y = lerp(ty + 260, ty, mv)
        al = prog(t, 28.30, 28.45) * (1 - prog(t, 29.10, 29.35))
        sc = 1 - 0.18 * math.sin(math.pi * prog(t, tap_t, tap_t + 0.18))
        if t >= tap_t:
            v = prog(t, tap_t, tap_t + 0.5)
            blit(f, TAP_RING, x, y, scale=lerp(0.6, 2.4, ease_out_cubic(v)), alpha=(1 - v) * 0.8)
        blit(f, TAP, x, y, scale=sc, alpha=al * 0.9)
        blit(f, TAP_EDGE, x, y, scale=sc, alpha=al)


# =============================================================== frame assembly
class FrameSource:
    """Sequential decoder with a small random-access window (look-ahead/-behind for transitions)."""

    def __init__(self, path):
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE, bufsize=W * H * 3 * 4)
        self.n = W * H * 3
        self.cache = {}
        self.next = 0

    def get(self, idx):
        idx = max(0, min(idx, SRC_FRAMES - 1))
        while self.next <= idx:
            buf = self.p.stdout.read(self.n)
            if len(buf) < self.n:
                break
            self.cache[self.next] = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            self.next += 1
        if idx not in self.cache:
            idx = max(k for k in self.cache if k <= idx)
        return self.cache[idx]

    def trim(self, keep_from):
        for k in [k for k in self.cache if k < keep_from]:
            del self.cache[k]


SRCF = None
_compose_cache = {}
CI_GARDEN, CI_SAUNA, CI_WIDE = round(CUT_GARDEN * FPS), round(CUT_SAUNA * FPS), round(CUT_WIDE * FPS)
SLAT_T0 = 25.98                # start of the zoom-into-box match cut


def bg_fx(f, t):
    for t0, cx, cy, rmax, dur, amp in SHOCKS:
        if t0 <= t < t0 + dur and segment_end(t0) == segment_end(t):
            u = prog(t, t0, t0 + dur)
            f = fx.shockwave(f, cx, cy, lerp(30, rmax, ease_out_cubic(u)), lerp(40, 120, u), amp * (1 - u) ** 1.3)
    return f


def compose(idx):
    """Picture + camera + motion graphics for frame idx (no subtitles, no transition FX). Cached; do not mutate."""
    if idx in _compose_cache:
        return _compose_cache[idx]
    t = idx / FPS
    if t >= CUT_END:
        f = np.empty((H, W, 3), np.float32)
        draw_endcard(f, t)
    else:
        f = SRCF.get(idx).astype(np.float32) / 255.0
        f = apply_camera(f, t)
        f = bg_fx(f, t)
        freeze_fx(f, t, idx)
        for t0, amp, dur in FLASHES:
            if t0 <= t < t0 + dur:
                a = amp * (1 - prog(t, t0, t0 + dur)) ** 1.5
                f *= 1 - a
                f += a
        draw_hook(f, t)
        draw_numbers(f, t)
        draw_cards(f, t)
        draw_summary(f, t)
    _compose_cache[idx] = f
    if len(_compose_cache) > 28:
        for k in sorted(_compose_cache)[: len(_compose_cache) - 28]:
            del _compose_cache[k]
    return f


def tr_zoom_through(idx, t):
    """Freeze frame -> garden: accelerate INTO her face, burst out of the garden."""
    if t < CUT_GARDEN:
        e = ease_in_cubic(prog(t, CUT_GARDEN - 0.30, CUT_GARDEN))
        f = fx._scale_about(compose(idx), 1 + 1.35 * e, 540, 540)
        f = fx.radial_blur(f, 0.32 * e, 540, 540)
        f = fx.chroma(f, 20 * e, 540, 540)
        return fx.brighten(f, 0.6 * e ** 3)
    e = 1 - ease_out_cubic(prog(t, CUT_GARDEN, CUT_GARDEN + 0.42))
    f = fx._scale_about(compose(idx), 1 + 0.5 * e, W / 2, H * 0.45)
    f = fx.radial_blur(f, 0.24 * e, W / 2, H * 0.45)
    f = fx.chroma(f, 16 * e)
    return fx.light_streak(f, H * 0.42, 1.3 * e ** 1.4)


def tr_whip(idx, t):
    """Fence -> sauna: horizontal whip pan, both shots side by side with motion blur."""
    t0, t1 = CUT_SAUNA - 0.20, CUT_SAUNA + 0.24

    def pos(tt):
        return ease_in_out_cubic(prog(tt, t0, t1))
    p = pos(t)
    speed = abs(pos(t + 0.5 / FPS) - pos(t - 0.5 / FPS)) * W
    out_f = compose(idx if idx < CI_SAUNA else CI_SAUNA - 1)
    in_f = compose(idx if idx >= CI_SAUNA else CI_SAUNA)
    o = int(round(p * W))
    res = np.empty_like(out_f)
    res[:, : W - o] = out_f[:, o:]
    res[:, W - o:] = in_f[:, :o]
    res = fx.motion_blur_x(res, min(speed * 0.95, 300))
    m = math.sin(math.pi * prog(t, t0, t1))
    res = fx.chroma(res, 10 * m)
    return fx.brighten(res, 0.22 * m)


def tr_spin(idx, t):
    """Whirlpool -> wide shot: spin-zoom out of one shot and into the next."""
    if t < CUT_WIDE:
        u = prog(t, CUT_WIDE - 0.22, CUT_WIDE)
        e = ease_in_cubic(u)
        dang = 28 * 3 * u * u / (0.22 * FPS)
        f = fx._scale_about(compose(idx), 1 + 0.55 * e, W / 2, H / 2, rot=28 * e)
        f = fx.spin_blur(f, dang * 1.3)
        f = fx.radial_blur(f, 0.22 * e)
        f = fx.chroma(f, 14 * e)
        return fx.brighten(f, 0.4 * e ** 3)
    v = prog(t, CUT_WIDE, CUT_WIDE + 0.30)
    e = 1 - ease_out_cubic(v)
    dang = 28 * 3 * (1 - v) ** 2 / (0.30 * FPS)
    f = fx._scale_about(compose(idx), 1 + 0.5 * e, W / 2, H / 2, rot=-28 * e)
    f = fx.spin_blur(f, dang * 1.3)
    f = fx.radial_blur(f, 0.2 * e)
    return fx.chroma(f, 12 * e)


def frame_out(idx):
    t = idx / FPS
    if CUT_SAUNA - 0.20 <= t < CUT_SAUNA + 0.24:
        f = tr_whip(idx, t)
    elif CUT_WIDE - 0.22 <= t < CUT_WIDE + 0.30:
        f = tr_spin(idx, t)
    elif CUT_GARDEN - 0.30 <= t < CUT_GARDEN + 0.42:
        f = tr_zoom_through(idx, t)
    else:
        f = compose(idx)
        if t < 0.30:                                   # intro: burst in from a zoom blur
            f = fx.radial_blur(f, 0.24 * (1 - ease_out_cubic(prog(t, 0, 0.30))), W / 2, H * 0.3)
        if CUT_FREEZE <= t < CUT_FREEZE + 0.22:          # freeze-frame hit
            f = fx.radial_blur(f, 0.12 * (1 - prog(t, CUT_FREEZE, CUT_FREEZE + 0.22)) ** 2, 520, 450)
        if SLAT_T0 <= t < CUT_END:                       # match cut: zoom INTO the navy savings box
            u = prog(t, SLAT_T0, CUT_END)
            e = u * u
            zx, zy = 215, 320                            # navy area left of the number
            f = fx._scale_about(f, math.exp(math.log(30.0) * e), zx, zy)
            f = fx.radial_blur(f, 0.30 * e, zx, zy)
            f = fx.chroma(f, 14 * e, zx, zy)
        if CUT_END <= t < CUT_END + 0.35:                # end card settles
            e = 1 - ease_out_cubic(prog(t, CUT_END, CUT_END + 0.35))
            f = fx._scale_about(f, 1 + 0.08 * e, W / 2, H / 2, border=cv2.BORDER_REPLICATE)
            f = fx.radial_blur(f, 0.07 * e)
    for t0, px, dur in CHROMA:
        if t0 <= t < t0 + dur:
            f = fx.chroma(f, px * (1 - prog(t, t0, t0 + dur)) ** 1.5)
    if any(f is v for v in _compose_cache.values()):
        f = f.copy()
    if t < 26.02:
        draw_subtitles(f, t)
    np.clip(f, 0, 1, out=f)
    return f


def render_frame(idx):
    return frame_out(idx)


def main():
    global SRCF
    SRCF = FrameSource(SRC)
    if sys.argv[3] == "--stills":
        times = sorted(float(x) for x in sys.argv[4].split(","))
        out_dir = sys.argv[5]
        for tt in times:
            idx = int(round(tt * FPS))
            img = (frame_out(idx) * 255).astype(np.uint8)
            Image.fromarray(img).save(f"{out_dir}/still_{tt:06.2f}.png")
        return

    audio, out = sys.argv[3], sys.argv[4]
    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", audio,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-t", f"{OUT_DURATION:.3f}", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for idx in range(OUT_FRAMES):
        img = frame_out(idx)
        enc.stdin.write((img * 255 + 0.5).astype(np.uint8).tobytes())
        SRCF.trim(idx - 30)
        if (idx + 1) % 60 == 0:
            print(f"frame {idx + 1}/{OUT_FRAMES}", flush=True)
    enc.stdin.close()
    enc.wait()
    print("done", out)


if __name__ == "__main__":
    main()
