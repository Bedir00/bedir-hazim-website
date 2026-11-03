# Schwarzer unendlicher Raum (futuristisch) – Hintergrund für das Black-Friday-Banner

16:9-Video (1920×1080, 60 fps): Neon-Portale stehen in einer endlosen schwarzen Leere, der schwarz
polierte Boden mit Lichtraster läuft zu den Seiten ins Nichts aus. Komplett selbst gerendert
(eigener Raytracer, `render.cpp`), keine KI-Generierung, keine Stock-Assets.

## Die optischen Täuschungen

1. **Unendliche Selbstähnlichkeit:** Hinter jedem Portal steht ein exakt halb so großes Portal,
   dahinter wieder eines – ohne Ende. Auch Bodenraster und Lichtpartikel sind selbstähnlich
   (log-polares Raster um den Fluchtpunkt), deshalb gibt es nirgends eine sichtbare „Level-Grenze“.
2. **Perfekte Endlosschleife:** Die Kamera fliegt mit konstanter *logarithmischer* Geschwindigkeit
   auf den Fluchtpunkt zu. Nach 7,5 s steht sie an exakt derselben relativen Stelle vor dem nächsten
   Portal – das letzte Bild geht nahtlos ins erste über. Man schrumpft endlos, ohne es zu merken.
3. **Leere statt Wände:** Links, rechts und oben gibt es nichts – der Boden verliert sich im Schwarz.
4. **Ton:** Shepard-Risset-Glissando – ein Ton, der endlos zu steigen scheint, aber nie oben ankommt.
   Er steigt genau eine Oktave pro Portal (Portal halb so groß = Frequenz doppelt so hoch) und loopt
   ebenfalls nahtlos.

Futuristische Details: Doppel-Neonkonturen mit abgeschrägten Ecken, Energiefeld-Schimmer in den
Öffnungen, Lichtimpulse auf der „Landebahn“, funkelnde Partikel mit Unschärfe, leichtes Rollen der
Kamera, Bloom und chromatische Aberration.

## Dateien

| Datei | Zweck |
|---|---|
| `unendlicher-raum_16x9_30s.mp4` | 30 s mit Ton (Social, YouTube, Präsentation) |
| `unendlicher-raum_16x9_loop.mp4` | 7,5 s nahtlose Schleife ohne Ton (Website-Banner) |
| `standbild_16x9.png` | Standbild (erstes Bild der Schleife) für statische Banner / Poster-Frame |
| `render.cpp` / `audio.py` / `build.sh` | Quellcode – `./build.sh` erzeugt alles neu |

## Für das Banner

- Die obere Bildhälfte ist schwarze Leere → viel Platz für „BLACK FRIDAY“ und den Rabatt.
- Das vorderste Portal ist das hellste Element und rahmt die Bildmitte (z. B. für den CTA).
- Farbe umschaltbar: `PALETTE=cyan` (Standard), `PALETTE=gold` oder `PALETTE=white` vor `./build.sh`.
- Andere Formate (9:16, 1:1) über `W`/`H` in `build.sh`, z. B. `W=1080 H=1920 ./build.sh`.
- Website-Einbindung als Endlos-Loop:

```html
<video src="unendlicher-raum_16x9_loop.mp4" autoplay muted loop playsinline></video>
```
