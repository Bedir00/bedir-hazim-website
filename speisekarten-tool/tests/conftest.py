import os
from pathlib import Path

import pymupdf
import pytest

from app.config import Settings
from app.ingest import IngestedMenu
from app.models import AIAnalysis, CICheck, CIProfile, MenuContent

CHROMIUM = os.environ.get("MENU_TOOL_CHROMIUM") or next(
    (str(p) for p in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")), None
)


class FakeAnalyzer:
    """Ersetzt Claude in Tests: liest Gerichte aus dem PDF-Text ("Name ... Preis")."""

    def __init__(self):
        self.calls: list[tuple[CIProfile, IngestedMenu]] = []

    async def analyze(self, ci, menu):
        self.calls.append((ci, menu))
        items = []
        for line in menu.text.splitlines():
            if " ... " in line:
                name, price = line.split(" ... ")
                value = float(price.replace("EUR", "").replace(",", ".").strip())
                items.append({"name": name.strip(), "price_text": price.strip(), "price_value": value})
        analysis = AIAnalysis(
            menu=MenuContent(restaurant_name=ci.restaurant_name, sections=[{"title": "Hauptgerichte", "items": items}]),
            checks=[
                CICheck(category="Logo", criterion="Logo vorhanden", status="fail", finding="Kein Logo.", recommendation="Logo oben platzieren."),
                CICheck(category="Layout", criterion="Weißraum", status="pass", finding="Ausreichend.", recommendation="–"),
            ],
            summary="Testfazit.",
            observed_colors=["#FFFFFF"],
            observed_fonts=["Helvetica"],
            logo_present=False,
        )
        return analysis, {"model": "fake", "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MENU_TOOL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MENU_TOOL_CONCURRENCY", "2")
    if CHROMIUM:
        monkeypatch.setenv("MENU_TOOL_CHROMIUM", CHROMIUM)
    return Settings()


def make_pdf(lines: list[str], color=(0.8, 0.1, 0.1)) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(pymupdf.Rect(0, 0, 595, 200), color=color, fill=color)
    y = 260
    for line in lines:
        page.insert_text((60, y), line, fontname="helv", fontsize=14)
        y += 24
    data = doc.tobytes()
    doc.close()
    return data
