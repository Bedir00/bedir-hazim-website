"""Einlesen von Speisekarten aus PDF, Bild oder URL.

Ergebnis ist immer dasselbe Format: Seitenbilder (PNG) für die visuelle Prüfung,
der auslesbare Text (falls vorhanden) und die tatsächlich verwendeten Schriften
(aus PDF-Metadaten bzw. berechneten CSS-Styles – bei Fotos nicht ermittelbar).
"""

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass, field
from io import BytesIO
from urllib.parse import urlparse

import pymupdf
from PIL import Image, ImageOps

from .browser import BrowserManager

MAX_EDGE = 2000
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


class IngestError(Exception):
    pass


@dataclass
class IngestedMenu:
    kind: str  # pdf | image | url
    pages: list[bytes]  # PNG-Bytes
    text: str = ""
    fonts: list[str] = field(default_factory=list)
    title: str | None = None
    truncated: bool = False


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _to_png(img: Image.Image) -> bytes:
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE))
    buffer = BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def normalize_font_name(name: str) -> str:
    """'ABCDEF+Montserrat-BoldItalic' -> 'Montserrat'; 'PlayfairDisplay' -> 'Playfair Display'."""
    name = name.split("+", 1)[-1]
    name = re.split(r"[-,]", name, maxsplit=1)[0]
    name = re.sub(r"(MT|PS|Std|Pro|LT)$", "", name)
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    return name.strip().strip("'\"")


def font_key(name: str) -> str:
    """Vergleichsschlüssel: Kleinbuchstaben, ohne Leerzeichen/Ziffern-Suffixe."""
    return re.sub(r"[^a-z]", "", normalize_font_name(name).lower())


# ---------------------------------------------------------------------------
# PDF & Bild
# ---------------------------------------------------------------------------


def ingest_pdf(data: bytes, max_pages: int) -> IngestedMenu:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF wirft verschiedene Fehlertypen
        raise IngestError(f"PDF konnte nicht geöffnet werden: {exc}") from exc

    pages: list[bytes] = []
    texts: list[str] = []
    fonts: dict[str, None] = {}
    with doc:
        for index, page in enumerate(doc):
            if index >= max_pages:
                break
            texts.append(page.get_text())
            for font in page.get_fonts(full=True):
                basefont = font[3]
                if basefont:
                    fonts[normalize_font_name(basefont)] = None
            longest = max(page.rect.width, page.rect.height) or 1
            zoom = min(MAX_EDGE / longest, 200 / 72)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            pages.append(pix.tobytes("png"))
        truncated = doc.page_count > max_pages
        title = (doc.metadata or {}).get("title") or None

    if not pages:
        raise IngestError("PDF enthält keine Seiten.")
    return IngestedMenu(
        kind="pdf",
        pages=pages,
        text="\n\n".join(t.strip() for t in texts).strip(),
        fonts=[f for f in fonts if f],
        title=title,
        truncated=truncated,
    )


def ingest_image(data: bytes) -> IngestedMenu:
    try:
        with Image.open(BytesIO(data)) as img:
            frames = getattr(img, "n_frames", 1)
            img.seek(0)
            png = _to_png(img)
    except Exception as exc:
        raise IngestError(f"Bild konnte nicht gelesen werden: {exc}") from exc
    return IngestedMenu(kind="image", pages=[png], truncated=frames > 1)


def ingest_file(data: bytes, filename: str, max_pages: int) -> IngestedMenu:
    lower = filename.lower()
    if lower.endswith(".pdf") or data[:5] == b"%PDF-":
        return ingest_pdf(data, max_pages)
    if any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return ingest_image(data)
    raise IngestError(f"Dateityp nicht unterstützt: {filename} (erlaubt: PDF, JPG, PNG, WEBP …)")


# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------


async def assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise IngestError(f"Ungültige URL: {url}")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, None)
    except socket.gaierror as exc:
        raise IngestError(f"Host nicht gefunden: {parsed.hostname}") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise IngestError(f"URL zeigt auf eine interne Adresse ({address}) und wird blockiert.")


_FONT_SCRIPT = """
() => {
  const weights = {};
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.textContent.trim();
    if (!text || !node.parentElement) continue;
    const style = getComputedStyle(node.parentElement);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    const family = style.fontFamily.split(',')[0].trim().replace(/^['"]|['"]$/g, '');
    weights[family] = (weights[family] || 0) + text.length;
  }
  return Object.entries(weights).sort((a, b) => b[1] - a[1]).map(e => e[0]);
}
"""


async def ingest_url(
    url: str,
    browser: BrowserManager,
    max_pages: int,
    allow_private: bool = False,
) -> IngestedMenu:
    if not allow_private:
        await assert_public_url(url)

    chromium = await browser.get()
    context = await chromium.new_context(
        viewport={"width": 1280, "height": 1600},
        device_scale_factor=1,
        locale="de-DE",
    )
    try:
        # Direkt verlinkte PDFs/Bilder erkennen.
        response = await context.request.get(url, timeout=30_000, max_redirects=5)
        content_type = (response.headers.get("content-type") or "").lower()
        if not response.ok:
            raise IngestError(f"URL lieferte HTTP {response.status}.")
        if "pdf" in content_type:
            return ingest_pdf(await response.body(), max_pages)
        if content_type.startswith("image/"):
            return ingest_image(await response.body())

        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=45_000)
        await page.wait_for_timeout(500)
        title = await page.title()
        text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        fonts = [normalize_font_name(f) for f in await page.evaluate(_FONT_SCRIPT)][:6]
        screenshot = await page.screenshot(full_page=True, type="png")
    finally:
        await context.close()

    pages, truncated = _split_tall_screenshot(screenshot, max_pages)
    return IngestedMenu(
        kind="url",
        pages=pages,
        text=text.strip(),
        fonts=[f for f in dict.fromkeys(fonts) if f],
        title=title or None,
        truncated=truncated,
    )


def _split_tall_screenshot(data: bytes, max_pages: int, slice_height: int = 1800) -> tuple[list[bytes], bool]:
    with Image.open(BytesIO(data)) as img:
        img = img.convert("RGB")
        width, height = img.size
        slices = []
        top = 0
        while top < height and len(slices) < max_pages:
            bottom = min(top + slice_height, height)
            slices.append(_to_png(img.crop((0, top, width, bottom))))
            top = bottom
    return slices, top < height
