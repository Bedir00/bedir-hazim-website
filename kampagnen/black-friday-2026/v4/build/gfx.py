"""Small 2D motion-graphics toolkit: premultiplied RGBA sprites, transforms, easing, text."""
import math
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_DIR = None  # set by caller

NAVY = (15, 35, 52)        # #0f2334  (subtitle text / brand navy)
NAVY_END = (14, 33, 52)    # end-card background as delivered in the source
WHITE = (254, 254, 254)    # #fefefe
MUTED = (184, 196, 207)    # light label colour on navy
GREY = (102, 114, 125)     # #66727d

_font_cache = {}


def font(weight, size):
    key = (weight, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(f"{FONT_DIR}/Poppins-{weight}.ttf", size)
    return _font_cache[key]


# ----------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(t, t0, t1):
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return clamp((t - t0) / (t1 - t0))


def ease_out_cubic(u):
    return 1 - (1 - u) ** 3


def ease_in_cubic(u):
    return u ** 3


def ease_in_out_cubic(u):
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def ease_out_back(u, s=1.70158):
    u = u - 1
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def ease_out_expo(u):
    return 1 if u >= 1 else 1 - 2 ** (-10 * u)


def lerp(a, b, u):
    return a + (b - a) * u


# ----------------------------------------------------------------- sprites
def to_sprite(img):
    """PIL RGBA -> premultiplied float32 array."""
    a = np.asarray(img.convert("RGBA"), dtype=np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    return np.ascontiguousarray(a)


def supersampled(draw_fn, w, h, ss=3):
    """Draw at ss× resolution with draw_fn(draw, s) and downsample (anti-aliased shapes)."""
    big = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(big), ss, big)
    return big.resize((w, h), Image.LANCZOS)


def text_size(txt, f, tracking=0):
    if tracking == 0:
        l, t, r, b = f.getbbox(txt)
        return r - l, b - t, l, t
    w = sum(f.getlength(c) for c in txt) + tracking * (len(txt) - 1)
    l, t, r, b = f.getbbox(txt)
    return int(round(w)), b - t, l, t


def draw_text(draw, xy, txt, f, fill, tracking=0, anchor="ls"):
    if tracking == 0:
        draw.text(xy, txt, font=f, fill=fill, anchor=anchor)
        return
    x, y = xy
    for c in txt:
        draw.text((x, y), c, font=f, fill=fill, anchor=anchor)
        x += f.getlength(c) + tracking


def shadowed(sprite_img, blur=22, offset=(0, 12), opacity=0.38, pad=40):
    """Add a soft drop shadow around a PIL RGBA image; returns (img, pad)."""
    w, h = sprite_img.size
    out = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    a = np.asarray(sprite_img.split()[-1], dtype=np.float32)
    sh = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
    sh[pad + offset[1]:pad + offset[1] + h, pad + offset[0]:pad + offset[0] + w] = a
    sh = cv2.GaussianBlur(sh, (0, 0), blur) * opacity
    shadow = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.uint8)
    shadow[..., 3] = np.clip(sh, 0, 255).astype(np.uint8)
    out = Image.fromarray(shadow, "RGBA")
    out.alpha_composite(sprite_img, (pad, pad))
    return out, pad


def blit(dst, spr, x, y, scale=1.0, rot=0.0, alpha=1.0, anchor=(0.5, 0.5), sx=None, sy=None):
    """Composite premultiplied sprite onto dst (float32 HxWx3) with transform.

    (x, y) is where the sprite's anchor point lands. rot in degrees (clockwise positive).
    """
    if alpha <= 0.002:
        return
    h, w = spr.shape[:2]
    sx = scale if sx is None else sx * scale
    sy = scale if sy is None else sy * scale
    if sx <= 0.001 or sy <= 0.001:
        return
    ax, ay = anchor[0] * w, anchor[1] * h
    a = math.radians(rot)
    c, s = math.cos(a), math.sin(a)
    M = np.array([[c * sx, -s * sy, 0.0], [s * sx, c * sy, 0.0]])
    M[:, 2] = [x, y] - M[:, :2] @ np.array([ax, ay])
    corners = M @ np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], float).T
    x0 = int(max(0, math.floor(corners[0].min()) - 1))
    y0 = int(max(0, math.floor(corners[1].min()) - 1))
    x1 = int(min(dst.shape[1], math.ceil(corners[0].max()) + 1))
    y1 = int(min(dst.shape[0], math.ceil(corners[1].max()) + 1))
    if x1 <= x0 or y1 <= y0:
        return
    M2 = M.copy()
    M2[:, 2] -= [x0, y0]
    if abs(rot) < 1e-6 and abs(sx - 1) < 1e-6 and abs(sy - 1) < 1e-6 and float(M[0, 2]).is_integer() and float(M[1, 2]).is_integer():
        ox, oy = int(M[0, 2]), int(M[1, 2])
        sx0, sy0 = x0 - ox, y0 - oy
        out = spr[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
        if out.shape[0] != y1 - y0 or out.shape[1] != x1 - x0:
            out = cv2.warpAffine(spr, M2, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    else:
        out = cv2.warpAffine(spr, M2, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    if alpha < 1:
        out = out * alpha
    reg = dst[y0:y1, x0:x1]
    reg *= 1 - out[..., 3:4]
    if dst.shape[2] == 4:
        reg += out
    else:
        reg += out[..., :3]


def clip_sprite(spr, x0=0.0, x1=1.0, y0=0.0, y1=1.0):
    """Return a copy with alpha zeroed outside the normalised rectangle (soft 1px edge)."""
    h, w = spr.shape[:2]
    out = spr.copy()
    px0, px1 = x0 * w, x1 * w
    py0, py1 = y0 * h, y1 * h
    xs = np.arange(w) + 0.5
    ys = np.arange(h) + 0.5
    mx = np.clip(np.minimum(xs - px0, px1 - xs) + 0.5, 0, 1)
    my = np.clip(np.minimum(ys - py0, py1 - ys) + 0.5, 0, 1)
    out *= (my[:, None] * mx[None, :])[..., None]
    return out


def fill_rect(dst, x0, y0, x1, y1, color, alpha=1.0):
    x0, y0 = max(0, int(round(x0))), max(0, int(round(y0)))
    x1, y1 = min(dst.shape[1], int(round(x1))), min(dst.shape[0], int(round(y1)))
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return
    c = np.array(color, np.float32) / 255.0
    reg = dst[y0:y1, x0:x1]
    reg *= 1 - alpha
    reg += c * alpha


def ring_sprite(radius, thickness, color=WHITE):
    size = int(2 * (radius + thickness) + 4)

    def fn(d, s, img):
        c = size * s / 2
        r = radius * s
        d.ellipse([c - r - thickness * s / 2, c - r - thickness * s / 2, c + r + thickness * s / 2, c + r + thickness * s / 2],
                  outline=color + (255,), width=int(thickness * s))
    return to_sprite(supersampled(fn, size, size))


def disc_sprite(radius, color=WHITE, alpha=255):
    size = int(2 * radius + 4)

    def fn(d, s, img):
        c = size * s / 2
        r = radius * s
        d.ellipse([c - r, c - r, c + r, c + r], fill=color + (alpha,))
    return to_sprite(supersampled(fn, size, size))


def line_sprite(length, thickness, color=WHITE):
    img = Image.new("RGBA", (int(length) + 2, int(thickness) + 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle([1, 1, int(length), int(thickness)], fill=color + (255,))
    return to_sprite(img)
