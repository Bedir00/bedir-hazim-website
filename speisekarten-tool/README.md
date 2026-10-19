# Speisekarten-CI-Tool

Web-App, die **beliebig viele Speisekarten einzeln gegen die Corporate Identity (CI) des jeweiligen
Restaurants prüft** und jede Karte automatisch **im CI neu setzt** – als druckfertiges PDF und als
responsive Web-Karte.

- **Eingabe:** PDF, Fotos/Scans (JPG, PNG, WEBP …) oder URLs von Online-Speisekarten; Upload vieler
  Dateien auf einmal oder Massenimport per CSV (`Kundenname;URL`).
- **CI pro Restaurant:** Farben, Schriften, Logo, Preisformat, Layout-Stil, Tonalität und frei
  formulierte Regeln (jede Regel wird als eigener Prüfpunkt bewertet).
- **Prüfung:** Kombination aus gemessenen und KI-gestützten Prüfpunkten, zusammengefasst zu einem
  CI-Score von 0–100.
- **Redesign:** Inhalt (Rubriken, Gerichte, Beschreibungen, Preise, Varianten, Allergene) wird
  extrahiert und in einer CI-Vorlage neu gesetzt (Stile: klassisch, modern, minimal).
- **Export:** Gesamtreport als CSV (Excel-kompatibel), alle Redesigns + Prüfberichte als ZIP.

## Wie geprüft wird

| Prüfpunkt | Methode |
|---|---|
| Farben | Gemessen: dominante Farben aller Seiten, Abstand zur CI-Palette nach CIEDE2000. Weiß/Grau/Schwarz optional erlaubt. |
| Schriften | Gemessen bei PDF (eingebettete Fonts) und Webseiten (berechnete CSS-Schriften). Bei Fotos schätzt die KI. |
| Preisformat | Gemessen: alle Preise gegen das CI-Format (z. B. `12,50 €`). |
| Logo, Layout, Lesbarkeit, Tonalität, Konsistenz, eigene CI-Regeln | KI-Bewertung (Claude, mit Bild und ausgelesenem Text). |

Jeder Prüfpunkt ist `erfüllt` (100), `Abweichung` (50) oder `Verstoß` (0); der Score ist der Mittelwert.

Im Redesign werden Kontrastprobleme der CI automatisch abgefangen (Text/Hintergrund mind. 4,5:1,
WCAG AA) und als Hinweis angezeigt.

## Installation

Voraussetzung: Python 3.11+.

```bash
cd speisekarten-tool
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # Headless-Browser für PDF-Export und URL-Screenshots
export ANTHROPIC_API_KEY=sk-ant-...  # Zugang zur Claude-API
python -m app                        # → http://127.0.0.1:8000
```

## Bedienung

1. **Kunde anlegen** und im Tab „CI-Profil“ Farben, Schriften, Logo, Preisformat und Regeln
   hinterlegen. Die Vorschau rechts zeigt sofort eine Musterkarte im CI.
2. Im Tab „Speisekarten“ **Dateien hineinziehen und/oder URLs einfügen** → „Prüfen starten“.
   Alle Karten laufen parallel durch die Warteschlange (Einlesen → KI-Prüfung → Redesign).
3. Eine Zeile anklicken für den **Prüfbericht** mit Vorher/Nachher-Vergleich, Downloads und der
   Möglichkeit, den erfassten Inhalt zu korrigieren (danach wird nur das Redesign neu gesetzt).
4. Nach einer CI-Änderung „**Redesigns aktualisieren**“ – setzt alle Karten mit der neuen CI neu,
   ohne erneute KI-Kosten.

Für viele Restaurants auf einmal: „URLs massenhaft importieren“ mit Zeilen `Kundenname;URL`.

## Konfiguration (Umgebungsvariablen)

| Variable | Standard | Bedeutung |
|---|---|---|
| `ANTHROPIC_API_KEY` | – | API-Schlüssel (alternativ ein Profil via `ant auth login`) |
| `MENU_TOOL_MODEL` | `claude-opus-5-5` | Claude-Modell |
| `MENU_TOOL_EFFORT` | `high` | Gründlichkeit (`low` … `max`); niedriger = günstiger/schneller |
| `MENU_TOOL_CONCURRENCY` | `4` | Gleichzeitig verarbeitete Karten |
| `MENU_TOOL_MAX_PAGES` | `8` | Max. Seiten/Bildausschnitte pro Karte |
| `MENU_TOOL_MAX_TOKENS` | `32000` | Max. Länge der KI-Antwort |
| `MENU_TOOL_DATA_DIR` | `./data` | Datenbank, Uploads und Ergebnisse |
| `MENU_TOOL_CHROMIUM` | – | Pfad zu einem vorhandenen Chromium statt `playwright install` |
| `MENU_TOOL_ALLOW_PRIVATE_URLS` | `false` | URLs auf interne Adressen erlauben |
| `MENU_TOOL_HOST` / `MENU_TOOL_PORT` | `127.0.0.1` / `8000` | Server-Adresse |

Die KI-Anfragen nutzen Prompt-Caching für das CI-Profil (spart bei vielen Karten desselben
Restaurants Kosten) und einen automatischen Modell-Fallback, falls eine Anfrage abgelehnt wird.

## Hinweise

- **Schriften im Redesign** werden von Google Fonts geladen. Für Hausschriften, die dort nicht
  verfügbar sind, die Schrift auf dem Server installieren – sonst greift eine Ersatzschrift.
- **Fotos auf der Karte** fließen in die Farbmessung ein und können den Farbwert verschlechtern;
  der KI-Befund zu Farben ordnet das ein.
- **Betrieb im Internet:** Die App hat keine Benutzeranmeldung. Nur hinter einem Login/Reverse-Proxy
  öffentlich betreiben. URLs auf interne Adressen werden standardmäßig blockiert (Weiterleitungen
  auf interne Adressen werden dabei nicht erfasst).

## Entwicklung

```bash
pip install -r requirements-dev.txt
pytest
```

Die Tests ersetzen Claude durch einen Fake-Analyzer und laufen ohne API-Schlüssel.

## Aufbau

```
app/
  main.py        Web-API (FastAPI) und Exporte
  pipeline.py    Warteschlange und Ablauf je Karte
  ingest.py      Einlesen von PDF, Bild, URL
  analyzer.py    KI-Analyse (Claude, strukturierte Ausgabe)
  checks.py      Gemessene Prüfungen, Preisformat, Score
  color.py       Farbmessung (CIEDE2000, Kontrast)
  redesign.py    HTML/PDF-Erzeugung im CI
  templates/     Vorlage der neu gesetzten Karte
  static/        Oberfläche
```
