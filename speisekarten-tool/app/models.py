"""Datenmodelle: CI-Profil, extrahierter Karteninhalt, Prüfergebnisse."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

HEX_PATTERN = r"^#[0-9a-fA-F]{6}$"

PriceFormat = Literal["12,50 €", "€ 12,50", "12,50", "12.50 €", "$12.50"]
LayoutStyle = Literal["klassisch", "modern", "minimal"]
PageFormat = Literal["A4", "A3", "A5", "Letter"]
CheckStatus = Literal["pass", "warn", "fail"]


class CIColors(BaseModel):
    primary: str = Field("#1F3A2E", pattern=HEX_PATTERN)
    secondary: str = Field("#C8A96A", pattern=HEX_PATTERN)
    accent: str = Field("#B5452F", pattern=HEX_PATTERN)
    background: str = Field("#FBF8F2", pattern=HEX_PATTERN)
    text: str = Field("#222222", pattern=HEX_PATTERN)
    # Weitere zulässige Farben (z. B. Sekundärpalette).
    extra: list[str] = Field(default_factory=list)

    @field_validator("primary", "secondary", "accent", "background", "text")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("extra")
    @classmethod
    def _valid_extra(cls, values: list[str]) -> list[str]:
        import re

        cleaned = []
        for value in values:
            value = value.strip()
            if not re.match(HEX_PATTERN, value):
                raise ValueError(f"Ungültige Farbe: {value!r} (erwartet #RRGGBB)")
            cleaned.append(value.upper())
        return cleaned

    def palette(self) -> list[str]:
        return [self.primary, self.secondary, self.accent, self.background, self.text, *self.extra]


class CIProfile(BaseModel):
    """Corporate Identity eines Restaurants."""

    restaurant_name: str
    colors: CIColors = Field(default_factory=CIColors)
    heading_font: str = "Playfair Display"
    body_font: str = "Source Sans 3"
    # Weitere erlaubte Schriften (z. B. Akzidenz für Preise).
    extra_fonts: list[str] = Field(default_factory=list)
    price_format: PriceFormat = "12,50 €"
    layout_style: LayoutStyle = "klassisch"
    page_format: PageFormat = "A4"
    tagline: str = ""
    tone_of_voice: str = ""
    # Freitext-Regeln, z. B. "Allergenkennzeichnung Pflicht", "Logo oben zentriert".
    rules: list[str] = Field(default_factory=list)
    # Farbabweichung (CIEDE2000), ab der eine Farbe als „nicht CI“ gilt.
    color_tolerance: float = Field(12.0, ge=1, le=50)
    # Neutrale Töne (Weiß/Grau/Schwarz, z. B. Papier) nicht als Verstoß werten.
    allow_neutrals: bool = True
    footer_note: str = ""

    def allowed_fonts(self) -> list[str]:
        return [self.heading_font, self.body_font, *self.extra_fonts]


# ---------------------------------------------------------------------------
# Von der KI extrahierter Inhalt
# ---------------------------------------------------------------------------


class PriceVariant(BaseModel):
    label: str
    price_text: str | None = None
    price_value: float | None = None


class MenuItem(BaseModel):
    name: str
    description: str | None = None
    # Preis exakt wie auf der Karte gedruckt, z. B. "12,50 €" oder "0,3l 3,90 / 0,5l 5,50".
    price_text: str | None = None
    # Hauptpreis als Zahl (falls eindeutig), für die Neuformatierung im Redesign.
    price_value: float | None = None
    # Zusätzliche Varianten, z. B. Größen: ["0,3 l", "0,5 l"] mit Preisen.
    variants: list[PriceVariant] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, description="z. B. vegan, vegetarisch, scharf, neu")
    allergens: list[str] = Field(default_factory=list, description="Allergenkennzeichnung wie auf der Karte")


class MenuSection(BaseModel):
    title: str
    note: str | None = None
    items: list[MenuItem]


class MenuContent(BaseModel):
    restaurant_name: str | None = None
    language: str = "de"
    sections: list[MenuSection]
    footer_notes: list[str] = Field(default_factory=list, description="z. B. Allergenlegende, MwSt.-Hinweis")


class CICheck(BaseModel):
    category: str = Field(description="z. B. Farben, Typografie, Logo, Layout, Preise, Tonalität, Pflichtangaben")
    criterion: str
    status: CheckStatus
    finding: str
    recommendation: str
    source: Literal["ki", "automatisch"] = "ki"


class AIAnalysis(BaseModel):
    """Strukturierte Antwort der KI für eine Speisekarte."""

    menu: MenuContent
    checks: list[CICheck]
    summary: str
    observed_colors: list[str] = Field(default_factory=list, description="Dominante Farben als #RRGGBB")
    observed_fonts: list[str] = Field(default_factory=list, description="Erkannte/vermutete Schriftarten")
    logo_present: bool | None = None


class MenuReport(BaseModel):
    """Gesamtergebnis einer Prüfung – wird in der Datenbank gespeichert."""

    score: int
    summary: str
    checks: list[CICheck]
    menu: MenuContent
    observed_colors: list[str] = Field(default_factory=list)
    observed_fonts: list[str] = Field(default_factory=list)
    dominant_colors: list[dict] = Field(default_factory=list)
    pages: list[str] = Field(default_factory=list, description="Dateinamen der Vorschau-Bilder")
    model: str | None = None
    usage: dict | None = None

