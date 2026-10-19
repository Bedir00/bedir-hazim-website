from io import BytesIO

from PIL import Image

from app.checks import check_colors, check_fonts, check_prices, format_price, score
from app.color import contrast_ratio, delta_e_2000, dominant_colors, is_neutral
from app.ingest import font_key, ingest_file, normalize_font_name
from app.models import CICheck, CIColors, CIProfile, MenuContent
from app.redesign import google_fonts_url, render_html

from .conftest import make_pdf


def png(color, size=(200, 200)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_delta_e_reference_values():
    assert delta_e_2000((10, 20, 30), (10, 20, 30)) == 0
    assert delta_e_2000((0, 0, 0), (255, 255, 255)) > 99
    assert delta_e_2000((200, 30, 30), (204, 30, 32)) < 2
    # Sharma et al. Testpaar 1 (Lab 50/2.6772/-79.7751 vs 50/0/-82.7485 → 2.0425) über RGB nicht exakt,
    # aber Blau gegen leicht anderes Blau muss klein, Blau gegen Gelb groß sein.
    assert delta_e_2000((0, 0, 255), (0, 0, 240)) < 5
    assert delta_e_2000((0, 0, 255), (255, 255, 0)) > 50


def test_neutral_and_contrast():
    assert is_neutral((250, 250, 248))
    assert is_neutral((30, 30, 30))
    assert not is_neutral((200, 30, 30))
    assert round(contrast_ratio((0, 0, 0), (255, 255, 255))) == 21


def test_dominant_colors_shares():
    img = Image.new("RGB", (100, 100), (255, 255, 255))
    img.paste((200, 30, 30), (0, 0, 100, 25))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    colors = dominant_colors(buffer.getvalue())
    assert abs(colors[0][1] - 0.75) < 0.02
    assert any(delta_e_2000(rgb, (200, 30, 30)) < 3 and abs(share - 0.25) < 0.02 for rgb, share in colors)


def test_color_check_pass_and_fail():
    ci = CIProfile(restaurant_name="Test", colors=CIColors(primary="#C81E1E"))
    ok, _ = check_colors(ci, [((200, 30, 30), 0.3), ((255, 255, 255), 0.7)])
    assert ok.status == "pass"
    bad, details = check_colors(ci, [((20, 160, 40), 0.4), ((255, 255, 255), 0.6)])
    assert bad.status == "fail"
    assert details[0]["in_ci"] is False


def test_font_names_and_check():
    assert normalize_font_name("ABCDEF+Montserrat-BoldItalic") == "Montserrat"
    assert normalize_font_name("PlayfairDisplay-Regular") == "Playfair Display"
    assert font_key("Source Sans 3") == font_key("SourceSans3-Regular")
    ci = CIProfile(restaurant_name="T", heading_font="Playfair Display", body_font="Montserrat")
    assert check_fonts(ci, ["Montserrat", "PlayfairDisplay"]).status == "pass"
    assert check_fonts(ci, ["Montserrat", "Comic Sans"]).status == "warn"
    assert check_fonts(ci, ["Arial"]).status == "fail"
    assert check_fonts(ci, []) is None


def test_price_check_and_format():
    ci = CIProfile(restaurant_name="T", price_format="12,50 €")
    menu = MenuContent(sections=[{"title": "A", "items": [
        {"name": "x", "price_text": "12,50 €"}, {"name": "y", "price_text": "9.5"}, {"name": "z", "price_text": "8,00 €"}]}])
    check = check_prices(ci, menu)
    assert check.status == "warn" and "„9.5“" in check.finding
    assert format_price(9.5, "12,50 €") == "9,50 €"
    assert format_price(9.5, "$12.50") == "$9.50"
    assert format_price(None, "12,50 €", "nach Tagespreis") == "nach Tagespreis"


def test_score():
    def c(status):
        return CICheck(category="x", criterion="x", status=status, finding="", recommendation="")
    assert score([c("pass"), c("fail")]) == 50
    assert score([c("pass"), c("warn"), c("pass"), c("pass")]) == 88


def test_ingest_pdf_and_image():
    menu = ingest_file(make_pdf(["Schnitzel ... 18,50 EUR"]), "karte.pdf", max_pages=5)
    assert menu.kind == "pdf" and len(menu.pages) == 1
    assert "Schnitzel" in menu.text
    assert "Helvetica" in menu.fonts
    image = ingest_file(png((10, 10, 10)), "foto.JPG", max_pages=5)
    assert image.kind == "image" and image.pages[0][:4] == b"\x89PNG"


def test_render_html_formats_prices_and_fixes_contrast():
    ci = CIProfile(restaurant_name="Trattoria", colors=CIColors(text="#EEEEEE", background="#FFFFFF"), price_format="€ 12,50")
    menu = MenuContent(sections=[{"title": "Pasta", "items": [
        {"name": "Carbonara <scharf>", "price_text": "12.5", "price_value": 12.5, "allergens": ["A"]},
        {"name": "Wein", "variants": [{"label": "0,2 l", "price_value": 6}]}]}])
    html, notes = render_html(ci, menu)
    assert "€ 12,50" in html and "€ 6,00" in html
    assert "Carbonara &lt;scharf&gt;" in html  # escaped
    assert notes and "Kontrast" in notes[0]
    assert "--text: #111111" in html


def test_google_fonts_url():
    url = google_fonts_url(["Playfair Display", "Arial"])
    assert "family=Playfair+Display" in url and "Arial" not in url
