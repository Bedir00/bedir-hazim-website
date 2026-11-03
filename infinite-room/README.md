# Schwarzer unendlicher Raum – Hintergrund für das Black-Friday-Banner

16:9-Video (1920×1080, 60 fps) eines schwarzen Raums, der sich endlos anfühlt.
Komplett selbst gerendert (eigener Raytracer, `render.cpp`), keine KI-Generierung, keine Stock-Assets.

## Die optischen Täuschungen

1. **Droste-Effekt:** Der goldene Torbogen führt in eine exakte Kopie desselben Raums im halben Maßstab,
   die wieder einen Torbogen hat – unendlich verschachtelt.
2. **Perfekte Endlosschleife:** Die Kamera fliegt mit konstanter *logarithmischer* Geschwindigkeit auf den
   Fluchtpunkt zu. Nach 7,5 s steht sie an exakt derselben relativen Stelle im nächsten Raum –
   das letzte Bild geht nahtlos ins erste über (gemessen: PSNR 86 dB zwischen t = 1 und t = 0).
3. **Spiegelwände + polierter Boden:** Lichtlinien und Lichtkugeln wiederholen sich seitlich ins Unendliche.
4. **Ton:** Shepard-Risset-Glissando – ein Ton, der endlos zu steigen scheint, aber nie oben ankommt.
   Er steigt genau eine Oktave pro Raum und loopt ebenfalls nahtlos.

## Dateien

| Datei | Zweck |
|---|---|
| `unendlicher-raum_16x9_30s.mp4` | 30 s mit Ton (Social, YouTube, Präsentation) |
| `unendlicher-raum_16x9_loop.mp4` | 7,5 s nahtlose Schleife ohne Ton (Website-Banner) |
| `render.cpp` / `audio.py` / `build.sh` | Quellcode – `./build.sh` erzeugt alles neu |

## Für das Banner

- Die schwarze Fläche **über dem Torbogen** ist bewusst frei gehalten → Platz für „BLACK FRIDAY“.
- Der Torbogen (mit Bodenspiegelung als „Kapsel“) ist das hellste Element → Rahmen für Rabatt/CTA.
- Website-Einbindung als Endlos-Loop:

```html
<video src="unendlicher-raum_16x9_loop.mp4" autoplay muted loop playsinline></video>
```

Andere Formate (z. B. 9:16, 1:1) lassen sich über `W`/`H` in `build.sh` direkt neu rendern.
