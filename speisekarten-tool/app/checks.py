"""Automatische (regelbasierte) CI-Prüfungen und Bewertung."""

import re

from .color import delta_e_2000, hex_to_rgb, is_neutral, rgb_to_hex
from .ingest import font_key
from .models import CICheck, CIProfile, MenuContent

STATUS_POINTS = {"pass": 100, "warn": 50, "fail": 0}


def check_colors(ci: CIProfile, colors: list[tuple[tuple[int, int, int], float]]) -> tuple[CICheck, list[dict]]:
    """Wie viel Fläche der Karte ist in Farben außerhalb der CI-Palette gestaltet?"""
    palette = [hex_to_rgb(c) for c in ci.colors.palette()]
    details = []
    off_share = 0.0
    off_colors = []
    for rgb, share in colors:
        distance = min(delta_e_2000(rgb, p) for p in palette)
        neutral = ci.allow_neutrals and is_neutral(rgb)
        in_ci = distance <= ci.color_tolerance or neutral
        details.append(
            {
                "hex": rgb_to_hex(rgb),
                "share": round(share, 4),
                "delta_e": round(distance, 1),
                "in_ci": in_ci,
                "neutral": neutral,
            }
        )
        if not in_ci:
            off_share += share
            if share >= 0.02:
                off_colors.append(rgb_to_hex(rgb))

    percent = round(off_share * 100)
    if off_share < 0.10:
        status = "pass"
        finding = f"{100 - percent} % der Fläche liegen in der CI-Palette."
    elif off_share < 0.25:
        status = "warn"
        finding = f"{percent} % der Fläche nutzen Farben außerhalb der CI ({', '.join(off_colors[:4]) or '–'})."
    else:
        status = "fail"
        finding = f"{percent} % der Fläche nutzen Farben außerhalb der CI ({', '.join(off_colors[:4]) or '–'})."
    check = CICheck(
        category="Farben",
        criterion="Flächenanteil der CI-Farben (CIEDE2000, Toleranz "
        f"{ci.color_tolerance:g})",
        status=status,
        finding=finding,
        recommendation=(
            "Keine Maßnahme nötig."
            if status == "pass"
            else "Abweichende Farbflächen durch Primär-/Sekundärfarbe ersetzen: "
            + ", ".join(ci.colors.palette()[:3])
            + ". Hinweis: Fotos können den Wert verfälschen."
        ),
        source="automatisch",
    )
    return check, details


def check_fonts(ci: CIProfile, used_fonts: list[str]) -> CICheck | None:
    """Nur möglich, wenn die Schriften technisch auslesbar sind (PDF, Webseite)."""
    if not used_fonts:
        return None
    allowed = {font_key(f) for f in ci.allowed_fonts()}
    # Generische CSS-Familien zählen nicht als Verstoß, sind aber auch keine CI-Schrift.
    generic = {"serif", "sansserif", "monospace", "systemui", "cursive"}
    relevant = [f for f in used_fonts if font_key(f) not in generic]
    foreign = [f for f in relevant if font_key(f) not in allowed]
    ok = [f for f in relevant if font_key(f) in allowed]

    if not relevant:
        return None
    if not foreign:
        status, finding = "pass", f"Nur CI-Schriften verwendet: {', '.join(ok)}."
    elif ok:
        status, finding = "warn", f"Neben CI-Schriften ({', '.join(ok)}) auch fremde: {', '.join(foreign)}."
    else:
        status, finding = "fail", f"Keine CI-Schrift verwendet. Gefunden: {', '.join(foreign)}."
    return CICheck(
        category="Typografie",
        criterion=f"Schriften laut CI: {', '.join(ci.allowed_fonts())}",
        status=status,
        finding=finding,
        recommendation=(
            "Keine Maßnahme nötig."
            if status == "pass"
            else f"Überschriften in {ci.heading_font}, Fließtext/Gerichte in {ci.body_font} setzen."
        ),
        source="automatisch",
    )


PRICE_PATTERNS = {
    "12,50 €": re.compile(r"^\d{1,4},\d{2}\s?€$"),
    "€ 12,50": re.compile(r"^€\s?\d{1,4},\d{2}$"),
    "12,50": re.compile(r"^\d{1,4},\d{2}$"),
    "12.50 €": re.compile(r"^\d{1,4}\.\d{2}\s?€$"),
    "$12.50": re.compile(r"^\$\d{1,4}\.\d{2}$"),
}


def check_prices(ci: CIProfile, menu: MenuContent) -> CICheck | None:
    prices = [
        item.price_text.strip()
        for section in menu.sections
        for item in section.items
        if item.price_text and not item.variants
    ]
    if not prices:
        return None
    pattern = PRICE_PATTERNS[ci.price_format]
    wrong = [p for p in prices if not pattern.match(p)]
    share = len(wrong) / len(prices)
    if not wrong:
        status, finding = "pass", f"Alle {len(prices)} Preise im CI-Format „{ci.price_format}“."
    else:
        status = "warn" if share < 0.5 else "fail"
        examples = ", ".join(f"„{p}“" for p in wrong[:4])
        finding = f"{len(wrong)} von {len(prices)} Preisen weichen vom Format „{ci.price_format}“ ab, z. B. {examples}."
    return CICheck(
        category="Preise",
        criterion=f"Einheitliches Preisformat „{ci.price_format}“",
        status=status,
        finding=finding,
        recommendation="Keine Maßnahme nötig." if status == "pass" else "Alle Preise einheitlich formatieren (im Redesign automatisch umgesetzt).",
        source="automatisch",
    )


def format_price(value: float | None, fmt: str, fallback: str | None = None) -> str:
    """Formatiert einen Preis nach CI-Vorgabe. Ohne Zahlwert bleibt der Originaltext."""
    if value is None:
        return fallback or ""
    dot = f"{value:.2f}"
    comma = dot.replace(".", ",")
    return {
        "12,50 €": f"{comma} €",
        "€ 12,50": f"€ {comma}",
        "12,50": comma,
        "12.50 €": f"{dot} €",
        "$12.50": f"${dot}",
    }[fmt]


def score(checks: list[CICheck]) -> int:
    if not checks:
        return 0
    return round(sum(STATUS_POINTS[c.status] for c in checks) / len(checks))
