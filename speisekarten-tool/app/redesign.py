"""Redesign: Karteninhalt im CI-Layout als HTML (Web) und druckfertiges PDF."""

import base64
import mimetypes
from pathlib import Path
from urllib.parse import quote_plus

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .browser import BrowserManager
from .checks import format_price
from .color import contrast_ratio, hex_to_rgb, rgb_to_hex
from .models import CIProfile, MenuContent

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))

# Schriften, die lokal/systemseitig vorhanden sind und nicht von Google Fonts geladen werden.
SYSTEM_FONTS = {"arial", "helvetica", "helvetica neue", "georgia", "times new roman", "verdana", "garamond"}


def google_fonts_url(fonts: list[str]) -> str | None:
    families = [f for f in dict.fromkeys(fonts) if f and f.lower() not in SYSTEM_FONTS]
    if not families:
        return None
    query = "&".join(f"family={quote_plus(f)}:wght@400;500;600;700" for f in families)
    return f"https://fonts.googleapis.com/css2?{query}&display=swap"


def _mix(hex1: str, hex2: str, ratio: float) -> str:
    a, b = hex_to_rgb(hex1), hex_to_rgb(hex2)
    return rgb_to_hex(tuple(round(x * (1 - ratio) + y * ratio) for x, y in zip(a, b)))


def _best_on(background: str) -> str:
    bg = hex_to_rgb(background)
    return "#FFFFFF" if contrast_ratio(bg, (255, 255, 255)) >= contrast_ratio(bg, (0, 0, 0)) else "#111111"


def _logo_data_uri(logo_path: Path | None) -> str | None:
    if not logo_path or not logo_path.exists():
        return None
    mime = mimetypes.guess_type(logo_path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(logo_path.read_bytes()).decode('ascii')}"


def render_html(ci: CIProfile, menu: MenuContent, logo_path: Path | None = None, mode: str = "print") -> tuple[str, list[str]]:
    """Gibt (HTML, Hinweise) zurück. Hinweise beschreiben automatische Korrekturen."""
    notes: list[str] = []
    colors = ci.colors.model_copy()

    # Lesbarkeit absichern: Text/Hintergrund mindestens WCAG AA (4,5:1).
    ratio = contrast_ratio(hex_to_rgb(colors.text), hex_to_rgb(colors.background))
    if ratio < 4.5:
        fixed = _best_on(colors.background)
        notes.append(
            f"Textfarbe {colors.text} hat nur {ratio:.1f}:1 Kontrast zum Hintergrund – im Redesign {fixed} verwendet."
        )
        colors.text = fixed
    accent_ratio = contrast_ratio(hex_to_rgb(colors.accent), hex_to_rgb(colors.background))
    if accent_ratio < 3:
        notes.append(f"Akzentfarbe {colors.accent} ist für Preise zu kontrastarm ({accent_ratio:.1f}:1) – Primärfarbe verwendet.")
        colors.accent = colors.primary

    items = 0
    sections = []
    for section in menu.sections:
        rendered_items = []
        for item in section.items:
            items += 1
            rendered_items.append(
                {
                    **item.model_dump(),
                    "display_price": format_price(item.price_value, ci.price_format, item.price_text)
                    if not item.variants
                    else (format_price(item.price_value, ci.price_format) if item.price_value is not None else ""),
                    "display_variants": [
                        {"label": v.label, "price": format_price(v.price_value, ci.price_format, v.price_text)}
                        for v in item.variants
                    ],
                }
            )
        sections.append({"title": section.title, "note": section.note, "entries": rendered_items})

    footer_notes = list(menu.footer_notes)
    if ci.footer_note and ci.footer_note not in footer_notes:
        footer_notes.append(ci.footer_note)

    template = _env.get_template("menu.html.j2")
    html = template.render(
        ci=ci,
        c=colors,
        menu={"language": menu.language, "sections": sections},
        title=ci.restaurant_name or menu.restaurant_name or "Speisekarte",
        logo_data_uri=_logo_data_uri(logo_path),
        show_name_with_logo=False,
        fonts_url=google_fonts_url([ci.heading_font, ci.body_font]),
        on_primary=_best_on(colors.primary),
        muted=_mix(colors.text, colors.background, 0.35),
        two_columns=items > 16 and ci.page_format != "A5",
        footer_notes=footer_notes,
        mode=mode,
    )
    return html, notes


async def render_pdf(html: str, browser: BrowserManager, page_format: str) -> bytes:
    chromium = await browser.get()
    page = await chromium.new_page()
    try:
        try:
            await page.set_content(html, wait_until="networkidle", timeout=20_000)
        except Exception:
            # Ohne Netz (Google Fonts nicht erreichbar) trotzdem mit Ersatzschriften drucken.
            await page.set_content(html, wait_until="load", timeout=20_000)
        await page.evaluate("() => document.fonts.ready")
        return await page.pdf(format=page_format, print_background=True, prefer_css_page_size=True)
    finally:
        await page.close()
