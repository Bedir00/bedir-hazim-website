import asyncio
import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import _parse_import, create_app

from .conftest import CHROMIUM, FakeAnalyzer, make_pdf

pytestmark = pytest.mark.skipif(not CHROMIUM, reason="Chromium für PDF-Export nicht gefunden")


def wait_done(client, client_id, expected, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        menus = client.get(f"/api/menus?client_id={client_id}").json()
        if len(menus) == expected and all(m["status"] in {"done", "error"} for m in menus):
            return menus
        time.sleep(0.2)
    raise AssertionError(f"Zeitüberschreitung: {menus}")


def test_full_batch_flow(settings):
    analyzer = FakeAnalyzer()
    app = create_app(settings, analyzer)
    with TestClient(app) as client:
        ci = {
            "restaurant_name": "Trattoria Roma",
            "colors": {"primary": "#C81E1E", "secondary": "#1E5AC8", "accent": "#C81E1E", "background": "#FFFFFF", "text": "#222222"},
            "heading_font": "Playfair Display",
            "body_font": "Helvetica",
            "rules": ["Allergene müssen gekennzeichnet sein"],
        }
        res = client.post("/api/clients", json={"ci": ci})
        assert res.status_code == 201, res.text
        client_id = res.json()["id"]
        assert client.post("/api/clients", json={"ci": ci}).status_code == 409

        on_brand = make_pdf(["Pizza Margherita ... 9,50 EUR", "Lasagne ... 12,90 EUR"], color=(200 / 255, 30 / 255, 30 / 255))
        off_brand = make_pdf(["Tiramisu ... 6,00 EUR"], color=(0.1, 0.7, 0.2))
        files = [
            ("files", ("karte-1.pdf", on_brand, "application/pdf")),
            ("files", ("karte-2.pdf", off_brand, "application/pdf")),
            ("files", ("notizen.txt", b"x", "text/plain")),
        ]
        res = client.post(f"/api/clients/{client_id}/menus", files=files, data={"urls": ""})
        assert res.status_code == 201, res.text
        body = res.json()
        assert len(body["created"]) == 2 and body["rejected"][0]["source"] == "notizen.txt"

        menus = wait_done(client, client_id, 2)
        assert all(m["status"] == "done" for m in menus), menus
        by_source = {m["source"]: client.get(f"/api/menus/{m['id']}").json() for m in menus}

        good, bad = by_source["karte-1.pdf"], by_source["karte-2.pdf"]
        color_good = next(c for c in good["report"]["checks"] if c["category"] == "Farben")
        color_bad = next(c for c in bad["report"]["checks"] if c["category"] == "Farben")
        assert color_good["status"] == "pass"
        assert color_bad["status"] in {"warn", "fail"}
        assert good["score"] > bad["score"]
        assert good["fails"] >= 1  # Logo-Verstoß der Fake-KI
        fonts = next(c for c in good["report"]["checks"] if c["category"] == "Typografie")
        assert fonts["source"] == "automatisch" and fonts["status"] == "pass"  # nur Helvetica (laut CI erlaubt)

        pdf = client.get(f"/api/menus/{good['id']}/files/redesign.pdf")
        assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
        web = client.get(f"/api/menus/{good['id']}/files/redesign-web.html").text
        assert "Pizza Margherita" in web and "9,50 €" in web
        assert client.get(f"/api/menus/{good['id']}/files/seite-1.png").status_code == 200
        assert client.get(f"/api/menus/{good['id']}/files/..%2Fmenu_tool.sqlite3").status_code == 404

        # CI-Änderung -> Redesign ohne neue KI-Prüfung neu setzen
        calls = len(analyzer.calls)
        ci["price_format"] = "€ 12,50"
        assert client.put(f"/api/clients/{client_id}", json={"ci": ci}).status_code == 200
        assert client.post(f"/api/clients/{client_id}/redesign").json() == {"updated": 2}
        assert "€ 9,50" in client.get(f"/api/menus/{good['id']}/files/redesign-web.html").text
        assert len(analyzer.calls) == calls

        # Inhalt manuell korrigieren
        content = good["report"]["menu"]
        content["sections"][0]["items"][0]["name"] = "Pizza Napoli"
        assert client.put(f"/api/menus/{good['id']}/content", json=content).status_code == 200
        assert "Pizza Napoli" in client.get(f"/api/menus/{good['id']}/files/redesign-web.html").text

        csv_text = client.get(f"/api/export/report.csv?client_id={client_id}").text
        assert "karte-1.pdf" in csv_text and "Trattoria Roma" in csv_text
        archive = zipfile.ZipFile(io.BytesIO(client.get("/api/export/redesigns.zip").content))
        names = archive.namelist()
        assert sum(n.endswith("redesign.pdf") for n in names) == 2
        assert all(n.startswith("Trattoria_Roma/") for n in names)

        preview = client.get(f"/api/clients/{client_id}/preview")
        assert preview.status_code == 200 and "Wiener Schnitzel" in preview.text

        # Massenimport: unbekannter Kunde wird abgelehnt
        res = client.post("/api/import-urls", data={"text": "Kunde;URL\nUnbekannt;https://example.com/karte"})
        assert res.json()["rejected"][0]["reason"].startswith("Kunde")

        assert client.delete(f"/api/clients/{client_id}").status_code == 204
        assert client.get("/api/clients").json() == []


def test_url_to_private_address_is_blocked(settings):
    app = create_app(settings, FakeAnalyzer())
    with TestClient(app) as client:
        client_id = client.post("/api/clients", json={"ci": {"restaurant_name": "X"}}).json()["id"]
        client.post(f"/api/clients/{client_id}/menus", data={"urls": "http://127.0.0.1:9/karte"})
        menu = wait_done(client, client_id, 1)[0]
        assert menu["status"] == "error" and "interne Adresse" in menu["error"]


def test_parse_import_variants():
    rows = _parse_import("Kunde;URL\nA;https://a.de\nB\thttps://b.de\nC, https://c.de/x\n# Kommentar\nkaputt")
    assert rows == [("A", "https://a.de"), ("B", "https://b.de"), ("C", "https://c.de/x")]
