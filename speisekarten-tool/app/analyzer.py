"""KI-Analyse mit Claude: Inhalt extrahieren und gegen die CI prüfen."""

import base64
import json
from typing import Protocol

import anthropic

from .ingest import IngestedMenu
from .models import AIAnalysis, CIProfile

SYSTEM_PROMPT = """Du bist Brand-Design-Prüfer:in für Restaurant-Speisekarten. Du erhältst Bilder \
einer Speisekarte (ggf. mit ausgelesenem Text) und das Corporate-Identity-Profil (CI) des Restaurants.

Deine zwei Aufgaben:

1. Inhalt vollständig und originalgetreu erfassen – alle Rubriken, Gerichte, Beschreibungen, Preise, \
Varianten (z. B. Größen), Kennzeichnungen (vegan, scharf …) und Allergen-/Zusatzstoffangaben. Nichts \
erfinden, nichts weglassen, Originalsprache beibehalten. Schreibfehler im Gerichtsnamen dürfen korrigiert \
werden. `price_text` exakt wie gedruckt, `price_value` als Zahl, wenn eindeutig. Bei mehreren Preisen pro \
Gericht (Größen) `variants` verwenden. Liegt ausgelesener Text vor, nutze ihn für exakte Schreibweisen und \
Preise; die Bilder sind maßgeblich für Struktur und Gestaltung. Bei Webseiten nur die Speisekarte erfassen, \
nicht Navigation, Impressum oder Cookie-Banner.

2. Die Gestaltung gegen das CI-Profil prüfen. Erzeuge pro Kriterium einen Check (status pass/warn/fail) mit \
konkretem Befund und umsetzbarer Empfehlung. Prüfe mindestens: Farben, Typografie (Schriftcharakter und \
Hierarchie), Logo (vorhanden, Platzierung, Schutzzone), Layout/Weißraum/Lesbarkeit, Tonalität der Texte, \
Konsistenz (Preise, Schreibweisen, Kennzeichnungen) sowie jede einzelne Regel aus `rules` als eigenen Check. \
Sei streng, aber fair: "warn" für kleinere Abweichungen, "fail" für klare Verstöße. Bei Fotos/Scans sind \
Schriften nur vermutbar – kennzeichne Unsicherheit im Befund.

`observed_colors`: die 3–8 prägenden Farben der Karte als #RRGGBB. `observed_fonts`: erkannte oder vermutete \
Schriftarten. `summary`: 2–3 Sätze Gesamturteil auf Deutsch. Alle Befunde und Empfehlungen auf Deutsch."""


class Analyzer(Protocol):
    async def analyze(self, ci: CIProfile, menu: IngestedMenu) -> tuple[AIAnalysis, dict]: ...


class AnalysisError(Exception):
    pass


class ClaudeAnalyzer:
    def __init__(self, model: str, effort: str, max_tokens: int, client: anthropic.AsyncAnthropic | None = None):
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = client

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        # Lazy, damit die App auch ohne Zugangsdaten startet (Fehler erst beim Prüfen).
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(max_retries=4)
        return self._client

    def _content(self, menu: IngestedMenu) -> list[dict]:
        blocks: list[dict] = []
        for index, page in enumerate(menu.pages, start=1):
            blocks.append({"type": "text", "text": f"Seite/Ausschnitt {index}:"})
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.standard_b64encode(page).decode("ascii"),
                    },
                }
            )
        info = [f"Quelle: {menu.kind}"]
        if menu.title:
            info.append(f"Titel: {menu.title}")
        if menu.fonts:
            info.append("Technisch ausgelesene Schriften: " + ", ".join(menu.fonts))
        if menu.truncated:
            info.append("Hinweis: Es wurden nur die ersten Seiten übermittelt.")
        if menu.text:
            info.append("Ausgelesener Text:\n<text>\n" + menu.text[:60_000] + "\n</text>")
        info.append("Erfasse den Inhalt und prüfe die Karte gegen das CI-Profil.")
        blocks.append({"type": "text", "text": "\n".join(info)})
        return blocks

    async def analyze(self, ci: CIProfile, menu: IngestedMenu) -> tuple[AIAnalysis, dict]:
        ci_json = json.dumps(ci.model_dump(), ensure_ascii=False, indent=2, sort_keys=True)
        try:
            async with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config={"effort": self.effort},
                system=[
                    {"type": "text", "text": SYSTEM_PROMPT},
                    {
                        "type": "text",
                        "text": f"CI-Profil:\n<ci>\n{ci_json}\n</ci>",
                        # Pro Restaurant identisch -> bei Stapelverarbeitung aus dem Cache.
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
                messages=[{"role": "user", "content": self._content(menu)}],
                output_format=AIAnalysis,
            ) as stream:
                message = await stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise AnalysisError("Anthropic-Zugang fehlt oder ist ungültig (ANTHROPIC_API_KEY prüfen).") from exc
        except anthropic.BadRequestError as exc:
            raise AnalysisError(f"Anfrage abgelehnt: {exc.message}") from exc
        except anthropic.RateLimitError as exc:
            raise AnalysisError("Rate-Limit erreicht – Parallelität (MENU_TOOL_CONCURRENCY) senken.") from exc
        except anthropic.APIStatusError as exc:
            raise AnalysisError(f"API-Fehler {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AnalysisError("Keine Verbindung zur Anthropic-API.") from exc

        if message.stop_reason == "refusal":
            raise AnalysisError("Die KI hat die Analyse abgelehnt.")
        if message.stop_reason == "max_tokens":
            raise AnalysisError("Antwort zu lang – MENU_TOOL_MAX_TOKENS erhöhen.")
        result = message.parsed_output
        if result is None:
            raise AnalysisError("Antwort der KI konnte nicht gelesen werden.")

        usage = message.usage
        meta = {
            "model": message.model,
            "usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_input_tokens": usage.cache_read_input_tokens or 0,
                "cache_creation_input_tokens": usage.cache_creation_input_tokens or 0,
            },
        }
        return result, meta
