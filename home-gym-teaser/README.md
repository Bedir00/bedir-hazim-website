# Home Gym – Teaser-Videos der Landingpages

Fünf kurze Motion-Graphics-Videos (9:16, 1080 × 1920, 13–16 s) mit deutschem Voice-over, eins pro Landingpage.
Ablauf: Problem → Lösung mit 3 Vorteilen → kostenloses Probetraining.

| Datei | Landingpage | 3D-Objekt |
|---|---|---|
| `export/hg-teaser-einstieg.mp4` | Einstieg | Hex-Kurzhantel |
| `export/hg-teaser-kurse.mp4` | Kurse & Ladies | Gyroskop-Ringe |
| `export/hg-teaser-kampfsport.mp4` | Boxen & BJJ | Boxsack |
| `export/hg-teaser-hyrox.mp4` | Hyrox & Functional | Kettlebell |
| `export/hg-teaser-flexibel.mp4` | 24/7 Training | Uhr |

Die Videos liegen in Shopify unter Inhalte → Dateien und sind im Theme „HOME GYM“ je Landingpage im Feld
„Hochkant-Video im Hero“ eingetragen.

## Neu erzeugen

Texte, Vorteile und Sprechertexte stehen in `scripts.json`. In `vo` stehen die Sätze so, wie die Stimme sie
aussprechen soll (z. B. „Hohm Dschimm“ für „Home Gym“).

```bash
npm i three@0.170.0 playwright           # Chromium muss für Playwright vorhanden sein
pip install piper-tts numpy               # ffmpeg muss installiert sein
# Stimme: de_DE-thorsten-high von huggingface.co/rhasspy/piper-voices nach voices/
# Schrift: hg-archivo.woff2 aus dem Theme als archivo.woff2 daneben legen
python3 vo.py                 # Voice-over je Satz
node render.js kampfsport     # Bild (Three.js in Chromium) → out/kampfsport.silent.mp4
python3 mix.py kampfsport     # Stimme + leiser Klangteppich, −16 LUFS → out/kampfsport.mp4
```

Stimme: Piper „Thorsten“ (Open Source). Klangteppich: im Skript synthetisch erzeugt, keine fremde Musik.
