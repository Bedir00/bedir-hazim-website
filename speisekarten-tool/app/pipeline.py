"""Verarbeitungs-Pipeline und Warteschlange für die Stapelprüfung."""

import asyncio
import logging
import shutil
from pathlib import Path

from .analyzer import AnalysisError, Analyzer
from .browser import BrowserManager
from .checks import check_colors, check_fonts, check_prices, score
from .color import dominant_colors, merge_color_shares
from .config import Settings
from .db import Database
from .ingest import IngestError, ingest_file, ingest_url
from .models import CIProfile, MenuContent, MenuReport
from .redesign import render_html, render_pdf

log = logging.getLogger("menu_tool")


class Pipeline:
    def __init__(self, settings: Settings, db: Database, analyzer: Analyzer, browser: BrowserManager):
        self.settings = settings
        self.db = db
        self.analyzer = analyzer
        self.browser = browser
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._pending: set[str] = set()
        self._workers: list[asyncio.Task] = []

    # ---- Warteschlange --------------------------------------------------

    def start(self) -> None:
        # Nach einem Neustart liegengebliebene Aufträge wieder aufnehmen.
        for menu in self.db.menus_by_status("queued", "processing"):
            self.enqueue(menu["id"])
        self._workers = [
            asyncio.create_task(self._worker(), name=f"menu-worker-{n}") for n in range(self.settings.concurrency)
        ]

    async def stop(self) -> None:
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []

    def enqueue(self, menu_id: str) -> None:
        self.db.update_menu(menu_id, status="queued", stage="Wartet", error=None)
        if menu_id not in self._pending:
            self._pending.add(menu_id)
            self._queue.put_nowait(menu_id)

    @property
    def queued(self) -> int:
        return len(self._pending)

    async def wait_idle(self) -> None:
        await self._queue.join()

    async def _worker(self) -> None:
        while True:
            menu_id = await self._queue.get()
            self._pending.discard(menu_id)
            try:
                await self.process(menu_id)
            except Exception:  # Worker darf nie sterben
                log.exception("Unerwarteter Fehler bei %s", menu_id)
                self.db.update_menu(menu_id, status="error", stage=None, error="Interner Fehler – siehe Server-Log.")
            finally:
                self._queue.task_done()

    # ---- Verarbeitung ---------------------------------------------------

    def output_dir(self, menu_id: str) -> Path:
        return self.settings.outputs_dir / menu_id

    async def process(self, menu_id: str) -> None:
        menu = self.db.get_menu(menu_id)
        if menu is None:
            return  # inzwischen gelöscht
        client = self.db.get_client(menu["client_id"])
        ci = CIProfile.model_validate(client["ci"])
        out = self.output_dir(menu_id)
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)

        try:
            self.db.update_menu(menu_id, status="processing", stage="Einlesen")
            if menu["source_type"] == "url":
                ingested = await ingest_url(
                    menu["source"], self.browser, self.settings.max_pages, self.settings.allow_private_urls
                )
            else:
                data = Path(menu["file_path"]).read_bytes()
                ingested = await asyncio.to_thread(ingest_file, data, menu["source"], self.settings.max_pages)

            page_names = []
            for index, png in enumerate(ingested.pages, start=1):
                name = f"seite-{index}.png"
                (out / name).write_bytes(png)
                page_names.append(name)

            colors = await asyncio.to_thread(
                lambda: merge_color_shares([dominant_colors(p) for p in ingested.pages])
            )

            self.db.update_menu(menu_id, stage="KI-Prüfung")
            analysis, meta = await self.analyzer.analyze(ci, ingested)

            color_check, color_details = check_colors(ci, colors)
            auto_checks = [color_check]
            if font_check := check_fonts(ci, ingested.fonts):
                auto_checks.append(font_check)
            if price_check := check_prices(ci, analysis.menu):
                auto_checks.append(price_check)
            checks = auto_checks + [c.model_copy(update={"source": "ki"}) for c in analysis.checks]

            report = MenuReport(
                score=score(checks),
                summary=analysis.summary,
                checks=checks,
                menu=analysis.menu,
                observed_colors=analysis.observed_colors,
                observed_fonts=list(dict.fromkeys([*ingested.fonts, *analysis.observed_fonts])),
                dominant_colors=color_details,
                pages=page_names,
                model=meta.get("model"),
                usage=meta.get("usage"),
            )
            self.db.update_menu(menu_id, stage="Redesign", score=report.score, report=report.model_dump())
            notes = await self.build_redesign(menu_id, ci, report.menu, client.get("logo_path"))
            self.db.update_menu(menu_id, status="done", stage=None, redesign_notes=notes)
        except (IngestError, AnalysisError) as exc:
            self.db.update_menu(menu_id, status="error", stage=None, error=str(exc))

    async def build_redesign(self, menu_id: str, ci: CIProfile, content: MenuContent, logo_path: str | None) -> list[str]:
        out = self.output_dir(menu_id)
        out.mkdir(parents=True, exist_ok=True)
        logo = Path(logo_path) if logo_path else None
        print_html, notes = render_html(ci, content, logo, mode="print")
        web_html, _ = render_html(ci, content, logo, mode="web")
        (out / "redesign-druck.html").write_text(print_html, encoding="utf-8")
        (out / "redesign-web.html").write_text(web_html, encoding="utf-8")
        pdf = await render_pdf(print_html, self.browser, ci.page_format)
        (out / "redesign.pdf").write_bytes(pdf)
        return notes

    async def regenerate_redesign(self, menu_id: str) -> list[str]:
        """Redesign mit aktueller CI neu setzen, ohne erneute KI-Prüfung."""
        menu = self.db.get_menu(menu_id)
        client = self.db.get_client(menu["client_id"])
        ci = CIProfile.model_validate(client["ci"])
        content = MenuContent.model_validate(menu["report"]["menu"])
        notes = await self.build_redesign(menu_id, ci, content, client.get("logo_path"))
        self.db.update_menu(menu_id, redesign_notes=notes)
        return notes
