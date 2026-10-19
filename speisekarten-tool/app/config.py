"""Zentrale Einstellungen – alles über Umgebungsvariablen steuerbar."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "ja", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("MENU_TOOL_DATA_DIR", "data")).resolve()
    )
    model: str = field(default_factory=lambda: os.environ.get("MENU_TOOL_MODEL", "claude-opus-5-5"))
    effort: str = field(default_factory=lambda: os.environ.get("MENU_TOOL_EFFORT", "high"))
    max_tokens: int = field(default_factory=lambda: int(os.environ.get("MENU_TOOL_MAX_TOKENS", "32000")))
    # Wie viele Speisekarten gleichzeitig verarbeitet werden.
    concurrency: int = field(default_factory=lambda: int(os.environ.get("MENU_TOOL_CONCURRENCY", "4")))
    # Maximal an die KI geschickte Seiten/Bildausschnitte pro Karte.
    max_pages: int = field(default_factory=lambda: int(os.environ.get("MENU_TOOL_MAX_PAGES", "8")))
    # Pfad zu einem vorhandenen Chromium (z. B. wenn `playwright install` nicht möglich ist).
    chromium_path: str | None = field(default_factory=lambda: os.environ.get("MENU_TOOL_CHROMIUM") or None)
    # URLs auf interne/private Adressen blockieren (Schutz vor SSRF bei öffentlichem Betrieb).
    allow_private_urls: bool = field(default_factory=lambda: _env_bool("MENU_TOOL_ALLOW_PRIVATE_URLS", False))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "menu_tool.sqlite3"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.uploads_dir, self.outputs_dir):
            path.mkdir(parents=True, exist_ok=True)
