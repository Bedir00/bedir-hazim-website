"""Farbanalyse: dominante Farben, CIEDE2000-Abstand, Kontrast."""

import math
from io import BytesIO

from PIL import Image

RGB = tuple[int, int, int]


def hex_to_rgb(value: str) -> RGB:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _srgb_to_linear(channel: float) -> float:
    channel /= 255
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    # sRGB -> XYZ (D65)
    x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) / 0.95047
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e_2000(rgb1: RGB, rgb2: RGB) -> float:
    """Wahrgenommener Farbabstand nach CIEDE2000 (≈1 kaum sichtbar, >10 deutlich anders)."""
    l1, a1, b1 = rgb_to_lab(rgb1)
    l2, a2, b2 = rgb_to_lab(rgb2)

    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(c_bar**7 / (c_bar**7 + 25**7)))
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360

    dlp = l2 - l1
    dcp = c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dhp_big = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp / 2))

    lp_bar = (l1 + l2) / 2
    cp_bar = (c1p + c2p) / 2
    if c1p * c2p == 0:
        hp_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hp_bar = (h1p + h2p + 360) / 2
    else:
        hp_bar = (h1p + h2p - 360) / 2

    t = (
        1
        - 0.17 * math.cos(math.radians(hp_bar - 30))
        + 0.24 * math.cos(math.radians(2 * hp_bar))
        + 0.32 * math.cos(math.radians(3 * hp_bar + 6))
        - 0.20 * math.cos(math.radians(4 * hp_bar - 63))
    )
    d_theta = 30 * math.exp(-(((hp_bar - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cp_bar**7 / (cp_bar**7 + 25**7))
    sl = 1 + (0.015 * (lp_bar - 50) ** 2) / math.sqrt(20 + (lp_bar - 50) ** 2)
    sc = 1 + 0.045 * cp_bar
    sh = 1 + 0.015 * cp_bar * t
    rt = -math.sin(math.radians(2 * d_theta)) * rc

    return math.sqrt(
        (dlp / sl) ** 2 + (dcp / sc) ** 2 + (dhp_big / sh) ** 2 + rt * (dcp / sc) * (dhp_big / sh)
    )


def is_neutral(rgb: RGB, max_chroma: float = 8.0) -> bool:
    """Weiß, Grau, Schwarz und Papiertöne (sehr geringe Buntheit)."""
    _, a, b = rgb_to_lab(rgb)
    return math.hypot(a, b) <= max_chroma


def relative_luminance(rgb: RGB) -> float:
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(rgb1: RGB, rgb2: RGB) -> float:
    l1, l2 = sorted((relative_luminance(rgb1), relative_luminance(rgb2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def dominant_colors(image_bytes: bytes, count: int = 10) -> list[tuple[RGB, float]]:
    """Dominante Farben eines Bildes mit ihrem Flächenanteil (0–1), absteigend sortiert."""
    with Image.open(BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((300, 300))
        quantized = img.quantize(colors=count, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette() or []
        counts = quantized.getcolors() or []
    total = sum(n for n, _ in counts) or 1
    result = []
    for n, index in counts:
        rgb = tuple(palette[index * 3 : index * 3 + 3])
        result.append((rgb, n / total))
    result.sort(key=lambda item: item[1], reverse=True)
    return result


def merge_color_shares(per_page: list[list[tuple[RGB, float]]]) -> list[tuple[RGB, float]]:
    """Mittelt die Farbanteile über mehrere Seiten und fasst sehr ähnliche Farben zusammen."""
    merged: list[list] = []
    pages = max(len(per_page), 1)
    for colors in per_page:
        for rgb, share in colors:
            for entry in merged:
                if delta_e_2000(entry[0], rgb) < 5:
                    entry[1] += share / pages
                    break
            else:
                merged.append([rgb, share / pages])
    merged.sort(key=lambda item: item[1], reverse=True)
    return [(tuple(rgb), share) for rgb, share in merged]
