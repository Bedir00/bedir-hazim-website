"""Full-frame transition / impact effects (float32 RGB frames, 0..1)."""
import math
import numpy as np
import cv2

from gfx import W, H

_YY, _XX = np.mgrid[0:H, 0:W].astype(np.float32)


def _scale_about(f, s, cx, cy, rot=0.0, border=cv2.BORDER_REFLECT_101):
    M = cv2.getRotationMatrix2D((cx, cy), rot, s)
    return cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=border)


def radial_blur(f, strength, cx=W / 2, cy=H / 2, n=8):
    """Zoom blur: average of progressively scaled copies (strength = max extra scale)."""
    if strength < 0.004:
        return f
    small = cv2.resize(f, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    acc = np.zeros_like(small)
    for k in range(n):
        s = 1 + strength * k / (n - 1)
        M = cv2.getRotationMatrix2D((cx / 2, cy / 2), 0, s)
        acc += cv2.warpAffine(small, M, (W // 2, H // 2), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    acc /= n
    blurred = cv2.resize(acc, (W, H), interpolation=cv2.INTER_LINEAR)
    # keep a little of the sharp frame so it never looks mushy
    keep = max(0.0, 0.35 - strength * 2.5)
    return blurred * (1 - keep) + f * keep


def spin_blur(f, angle_span, cx=W / 2, cy=H / 2, n=7):
    if abs(angle_span) < 0.3:
        return f
    small = cv2.resize(f, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    acc = np.zeros_like(small)
    for k in range(n):
        a = angle_span * (k / (n - 1) - 0.5)
        M = cv2.getRotationMatrix2D((cx / 2, cy / 2), a, 1.0)
        acc += cv2.warpAffine(small, M, (W // 2, H // 2), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return cv2.resize(acc / n, (W, H), interpolation=cv2.INTER_LINEAR)


def chroma(f, px, cx=W / 2, cy=H / 2):
    """Radial chromatic aberration: red scaled out, blue scaled in by ~px at the frame edge."""
    if px < 0.4:
        return f
    k = px / (H / 2)
    out = f.copy()
    out[..., 0] = _scale_about(np.ascontiguousarray(f[..., 0]), 1 + k, cx, cy)
    out[..., 2] = _scale_about(np.ascontiguousarray(f[..., 2]), 1 - k, cx, cy)
    return out


def motion_blur_x(f, k):
    k = int(k)
    if k < 3:
        return f
    return cv2.blur(f, (k, 1), borderType=cv2.BORDER_REFLECT_101)


def shockwave(f, cx, cy, radius, width, amp):
    """Refraction ring expanding from (cx, cy)."""
    if amp < 0.3:
        return f
    dx, dy = _XX - cx, _YY - cy
    r = np.sqrt(dx * dx + dy * dy) + 1e-3
    z = (r - radius) / width
    g = np.exp(-z * z)
    off = amp * z * g
    mx = (_XX - off * dx / r).astype(np.float32)
    my = (_YY - off * dy / r).astype(np.float32)
    out = cv2.remap(f, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    out += (g * (amp / 260.0))[..., None]   # faint bright rim
    return out


def light_streak(f, y, strength, color=(1.0, 0.95, 0.86), length=1.0):
    """Anamorphic horizontal streak + glow centred on row y."""
    if strength < 0.01:
        return f
    ys = (_YY[:, :1] - y) / 6.0
    core = np.exp(-ys * ys)
    glow = np.exp(-((_YY[:, :1] - y) / 120.0) ** 2) * 0.35
    xs = np.exp(-((_XX[:1, :] - W / 2) / (W * 0.55 * length)) ** 2)
    m = (core + glow) * xs * strength
    return f + m[..., None] * np.array(color, np.float32)


def brighten(f, a):
    if a <= 0:
        return f
    return f * (1 - a) + a


def bloom(f, strength, threshold=0.62, sigma=28):
    """Cinematic highlight bloom: blurred bright areas added back (glow instead of a white flash)."""
    if strength < 0.01:
        return f
    small = cv2.resize(f, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    hi = np.clip((small - threshold) / (1 - threshold), 0, 1) ** 1.5
    glow = cv2.GaussianBlur(hi, (0, 0), sigma / 4)
    glow = cv2.resize(glow, (W, H), interpolation=cv2.INTER_LINEAR)
    warm = np.array([1.0, 0.93, 0.82], np.float32)
    return f + glow * warm * strength
