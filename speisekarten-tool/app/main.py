"""Web-App: CI-Profile verwalten, Speisekarten massenhaft prüfen, Redesigns erzeugen."""

import csv
import io
import json
import os
import re
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from .analyzer import Analyzer, ClaudeAnalyzer
from .browser import BrowserManager
from .config import Settings
from .db import Database, new_id
from .ingest import IMAGE_EXTENSIONS
from .models import CIProfile, MenuContent
from .pipeline import Pipeline
from .redesign import render_html

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
OUTPUT_FILES = {"redesign.pdf", "redesign-web.html", "redesign-druck.html"}
LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}

DEMO_MENU = MenuContent(
    restaurant_name="Demo",
    sections=[
        {
            "title": "Vorspeisen",
            "items": [
                {"name": "Burrata", "description": "Tomaten, Basilikum, Olivenöl", "price_value": 12.5, "tags": ["vegetarisch"], "allergens": ["G"]},
                {"name": "Rindertatar", "description": "Kapern, Eigelb, Röstbrot", "price_value": 16.9, "allergens": ["A", "C"]},
            ],
        },
        {
            "title": "Hauptgerichte",
            "items": [
                {"name": "Wiener Schnitzel", "description": "Kartoffel-Gurken-Salat, Preiselbeeren", "price_value": 24.0, "allergens": ["A", "C", "G"]},
                {"name": "Risotto", "description": "Steinpilze, Parmesan", "price_value": 19.5, "tags": ["vegetarisch"]},
            ],
        },
        {
            "title": "Getränke",
            "items": [
                {"name": "Hauslimonade", "variants": [{"label": "0,3 l", "price_value": 3.9}, {"label": "0,5 l", "price_value": 5.5}]},
            ],
        },
    ],
    footer_notes=["Allergene: A Gluten · C Ei · G Milch", "Alle Preise inkl. MwSt."],
)


class ClientIn(BaseModel):
    ci: CIProfile


def _safe_name(name: str) -> str:
    name = Path(name or "datei").name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120] or "datei"


def create_app(settings: Settings | None = None, analyzer: Analyzer | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.ensure_dirs()
    db = Database(settings.db_path)
    browser = BrowserManager(settings.chromium_path)
    analyzer = analyzer or ClaudeAnalyzer(settings.model, settings.effort, settings.max_tokens)
    pipeline = Pipeline(settings, db, analyzer, browser)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pipeline.start()
        yield
        await pipeline.stop()
        await browser.close()
        db.close()

    app = FastAPI(title="Speisekarten-CI-Tool", lifespan=lifespan)
    app.state.pipeline = pipeline
    app.state.db = db
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def get_client_or_404(client_id: str) -> dict:
        client = db.get_client(client_id)
        if client is None:
            raise HTTPException(404, "Kunde nicht gefunden")
        return client

    def get_menu_or_404(menu_id: str) -> dict:
        menu = db.get_menu(menu_id)
        if menu is None:
            raise HTTPException(404, "Speisekarte nicht gefunden")
        return menu

    # ---- Allgemein ------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/api/status")
    def status() -> dict:
        return {
            "credentials_found": bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
            "model": settings.model,
            "effort": settings.effort,
            "concurrency": settings.concurrency,
            "queued": pipeline.queued,
        }

    # ---- Kunden / CI ----------------------------------------------------

    @app.get("/api/clients")
    def list_clients() -> list[dict]:
        return db.list_clients()

    @app.post("/api/clients", status_code=201)
    def create_client(body: ClientIn) -> dict:
        if db.find_client_by_name(body.ci.restaurant_name):
            raise HTTPException(409, "Ein Kunde mit diesem Namen existiert bereits.")
        return db.create_client(body.ci.restaurant_name, body.ci.model_dump())

    @app.get("/api/clients/{client_id}")
    def get_client(client_id: str) -> dict:
        return get_client_or_404(client_id)

    @app.put("/api/clients/{client_id}")
    def update_client(client_id: str, body: ClientIn) -> dict:
        get_client_or_404(client_id)
        other = db.find_client_by_name(body.ci.restaurant_name)
        if other and other["id"] != client_id:
            raise HTTPException(409, "Ein Kunde mit diesem Namen existiert bereits.")
        return db.update_client(client_id, body.ci.restaurant_name, body.ci.model_dump())

    @app.delete("/api/clients/{client_id}", status_code=204)
    def delete_client(client_id: str) -> Response:
        get_client_or_404(client_id)
        for menu in db.list_menus(client_id):
            _remove_menu_files(menu)
        db.delete_client(client_id)
        return Response(status_code=204)

    @app.post("/api/clients/{client_id}/logo")
    async def upload_logo(client_id: str, file: UploadFile = File(...)) -> dict:
        client = get_client_or_404(client_id)
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in LOGO_EXTENSIONS:
            raise HTTPException(400, "Logo muss PNG, JPG, SVG oder WEBP sein.")
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, "Logo ist größer als 10 MB.")
        if client.get("logo_path"):
            Path(client["logo_path"]).unlink(missing_ok=True)
        path = settings.uploads_dir / f"logo-{client_id}-{new_id()}{suffix}"
        path.write_bytes(data)
        db.set_client_logo(client_id, str(path))
        return db.get_client(client_id)

    @app.delete("/api/clients/{client_id}/logo")
    def delete_logo(client_id: str) -> dict:
        client = get_client_or_404(client_id)
        if client.get("logo_path"):
            Path(client["logo_path"]).unlink(missing_ok=True)
        db.set_client_logo(client_id, None)
        return db.get_client(client_id)

    @app.get("/api/clients/{client_id}/logo")
    def get_logo(client_id: str) -> FileResponse:
        client = get_client_or_404(client_id)
        if not client.get("logo_path") or not Path(client["logo_path"]).exists():
            raise HTTPException(404, "Kein Logo hinterlegt")
        return FileResponse(client["logo_path"])

    @app.get("/api/clients/{client_id}/preview", response_class=HTMLResponse)
    def preview(client_id: str, mode: str = "print") -> str:
        """Muster-Karte im CI – zum Abstimmen des Profils vor der Stapelprüfung."""
        client = get_client_or_404(client_id)
        ci = CIProfile.model_validate(client["ci"])
        logo = Path(client["logo_path"]) if client.get("logo_path") else None
        html, _ = render_html(ci, DEMO_MENU, logo, mode="web" if mode == "web" else "print")
        return html

    # ---- Speisekarten hinzufügen ---------------------------------------

    @app.post("/api/clients/{client_id}/menus", status_code=201)
    async def add_menus(
        client_id: str,
        files: list[UploadFile] = File(default=[]),
        urls: str = Form(default=""),
    ) -> dict:
        get_client_or_404(client_id)
        created, rejected = [], []
        for upload in files:
            name = upload.filename or "datei"
            suffix = Path(name).suffix.lower()
            if suffix != ".pdf" and suffix not in IMAGE_EXTENSIONS:
                rejected.append({"source": name, "reason": "Dateityp nicht unterstützt"})
                continue
            data = await upload.read()
            if len(data) > MAX_UPLOAD_BYTES:
                rejected.append({"source": name, "reason": "Datei größer als 50 MB"})
                continue
            path = settings.uploads_dir / f"{new_id()}-{_safe_name(name)}"
            path.write_bytes(data)
            kind = "pdf" if suffix == ".pdf" else "image"
            created.append(db.create_menu(client_id, kind, name, str(path)))
        for url in _parse_urls(urls):
            created.append(db.create_menu(client_id, "url", url, None))
        for menu in created:
            pipeline.enqueue(menu["id"])
        if not created and not rejected:
            raise HTTPException(400, "Keine Dateien oder URLs übergeben.")
        return {"created": created, "rejected": rejected}

    @app.post("/api/import-urls", status_code=201)
    async def import_urls(file: UploadFile | None = File(default=None), text: str = Form(default="")) -> dict:
        """Massenimport: CSV/Text mit Zeilen „Kundenname;URL“ (auch Komma oder Tab getrennt)."""
        raw = text
        if file is not None:
            raw += "\n" + (await file.read()).decode("utf-8-sig", errors="replace")
        created, rejected = [], []
        for line_no, (name, url) in enumerate(_parse_import(raw), start=1):
            client = db.find_client_by_name(name)
            if client is None:
                rejected.append({"line": line_no, "source": url, "reason": f"Kunde „{name}“ unbekannt"})
                continue
            if not re.match(r"^https?://", url):
                rejected.append({"line": line_no, "source": url, "reason": "Keine gültige URL"})
                continue
            menu = db.create_menu(client["id"], "url", url, None)
            pipeline.enqueue(menu["id"])
            created.append(menu)
        return {"created": created, "rejected": rejected}

    # ---- Speisekarten verwalten ----------------------------------------

    @app.get("/api/menus")
    def list_menus(client_id: str | None = None) -> list[dict]:
        return db.list_menus(client_id)

    @app.get("/api/menus/{menu_id}")
    def get_menu(menu_id: str) -> dict:
        return get_menu_or_404(menu_id)

    @app.delete("/api/menus/{menu_id}", status_code=204)
    def delete_menu(menu_id: str) -> Response:
        menu = get_menu_or_404(menu_id)
        _remove_menu_files(menu)
        db.delete_menu(menu_id)
        return Response(status_code=204)

    @app.post("/api/menus/{menu_id}/reprocess")
    def reprocess(menu_id: str) -> dict:
        get_menu_or_404(menu_id)
        pipeline.enqueue(menu_id)
        return db.get_menu(menu_id)

    @app.post("/api/clients/{client_id}/reprocess")
    def reprocess_client(client_id: str, only_errors: bool = False) -> dict:
        get_client_or_404(client_id)
        count = 0
        for menu in db.list_menus(client_id):
            if menu["status"] in {"queued", "processing"} or (only_errors and menu["status"] != "error"):
                continue
            pipeline.enqueue(menu["id"])
            count += 1
        return {"queued": count}

    @app.post("/api/menus/{menu_id}/redesign")
    async def redesign(menu_id: str) -> dict:
        menu = get_menu_or_404(menu_id)
        if not menu.get("report"):
            raise HTTPException(409, "Karte wurde noch nicht geprüft.")
        await pipeline.regenerate_redesign(menu_id)
        return db.get_menu(menu_id)

    @app.post("/api/clients/{client_id}/redesign")
    async def redesign_client(client_id: str) -> dict:
        """Nach CI-Änderung alle Redesigns neu setzen – ohne neue KI-Kosten."""
        get_client_or_404(client_id)
        count = 0
        for menu in db.list_menus_with_reports(client_id):
            if menu["status"] == "done" and menu.get("report"):
                await pipeline.regenerate_redesign(menu["id"])
                count += 1
        return {"updated": count}

    @app.put("/api/menus/{menu_id}/content")
    async def update_content(menu_id: str, content: MenuContent) -> dict:
        """Extrahierten Inhalt manuell korrigieren und Redesign neu setzen."""
        menu = get_menu_or_404(menu_id)
        if not menu.get("report"):
            raise HTTPException(409, "Karte wurde noch nicht geprüft.")
        report = menu["report"]
        report["menu"] = content.model_dump()
        db.update_menu(menu_id, report=report)
        await pipeline.regenerate_redesign(menu_id)
        return db.get_menu(menu_id)

    @app.get("/api/menus/{menu_id}/files/{name}")
    def menu_file(menu_id: str, name: str, download: bool = False) -> FileResponse:
        menu = get_menu_or_404(menu_id)
        if name not in OUTPUT_FILES and not re.fullmatch(r"seite-\d+\.png", name):
            raise HTTPException(404, "Datei nicht gefunden")
        path = pipeline.output_dir(menu_id) / name
        if not path.exists():
            raise HTTPException(404, "Datei nicht gefunden")
        filename = None
        if download:
            client = db.get_client(menu["client_id"])
            filename = f"{_safe_name(client['name'])}-{_safe_name(Path(menu['source']).stem or menu_id)}-{name}"
        return FileResponse(path, filename=filename)

    @app.get("/api/menus/{menu_id}/original")
    def original(menu_id: str) -> Response:
        menu = get_menu_or_404(menu_id)
        if menu["source_type"] == "url":
            return Response(status_code=307, headers={"Location": menu["source"]})
        return FileResponse(menu["file_path"], filename=menu["source"])

    # ---- Export ---------------------------------------------------------

    @app.get("/api/export/report.csv")
    def export_csv(client_id: str | None = None) -> Response:
        clients = {c["id"]: c["name"] for c in db.list_clients()}
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(["Kunde", "Quelle", "Status", "Score", "Bestanden", "Warnungen", "Verstöße", "Wichtigste Verstöße", "Fazit"])
        for menu in db.list_menus_with_reports(client_id):
            checks = (menu.get("report") or {}).get("checks", [])
            fails = [c for c in checks if c["status"] == "fail"]
            writer.writerow(
                [
                    clients.get(menu["client_id"], ""),
                    menu["source"],
                    menu["status"],
                    menu["score"] if menu["score"] is not None else "",
                    sum(c["status"] == "pass" for c in checks),
                    sum(c["status"] == "warn" for c in checks),
                    len(fails),
                    " | ".join(f"{c['category']}: {c['finding']}" for c in fails[:3]),
                    (menu.get("report") or {}).get("summary", "") or menu.get("error") or "",
                ]
            )
        # BOM, damit Excel Umlaute korrekt anzeigt.
        return Response(
            "﻿" + buffer.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="ci-pruefung.csv"'},
        )

    @app.get("/api/export/redesigns.zip")
    def export_zip(client_id: str | None = None) -> StreamingResponse:
        clients = {c["id"]: c["name"] for c in db.list_clients()}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for menu in db.list_menus_with_reports(client_id):
                if menu["status"] != "done":
                    continue
                folder = _safe_name(clients.get(menu["client_id"], "kunde"))
                stem = f"{_safe_name(Path(menu['source']).stem)[:60]}-{menu['id']}"
                out = pipeline.output_dir(menu["id"])
                for name in ("redesign.pdf", "redesign-web.html"):
                    if (out / name).exists():
                        archive.write(out / name, f"{folder}/{stem}/{name}")
                archive.writestr(
                    f"{folder}/{stem}/pruefbericht.json",
                    json.dumps(menu["report"], ensure_ascii=False, indent=2),
                )
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="redesigns.zip"'},
        )

    def _remove_menu_files(menu: dict) -> None:
        if menu.get("file_path"):
            Path(menu["file_path"]).unlink(missing_ok=True)
        out = pipeline.output_dir(menu["id"])
        if out.exists():
            for child in out.iterdir():
                child.unlink()
            out.rmdir()

    @app.exception_handler(ValidationError)
    async def validation_error(_, exc: ValidationError):
        return Response(json.dumps({"detail": exc.errors()}, default=str), status_code=422, media_type="application/json")

    return app


def _parse_urls(text: str) -> list[str]:
    urls = []
    for token in re.split(r"[\s,;]+", text or ""):
        token = token.strip()
        if re.match(r"^https?://", token):
            urls.append(token)
    return list(dict.fromkeys(urls))


def _parse_import(raw: str) -> list[tuple[str, str]]:
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s*[;\t]\s*|\s*,\s*(?=https?://)", line, maxsplit=1)
        if len(parts) != 2:
            continue
        name, url = parts[0].strip().strip('"'), parts[1].strip().strip('"')
        if name.lower() in {"kunde", "name", "restaurant"}:
            continue  # Kopfzeile
        rows.append((name, url))
    return rows

