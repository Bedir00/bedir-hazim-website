# Home Deluxe – Black Friday TikTok-Spot (25 % auf alles)

**Datei:** `HomeDeluxe_BlackFriday_TikTok_Untertitel_MotionGraphics.mp4`
1080×1920 · 30 fps · H.264 + AAC 48 kHz · 29,9 s · Lautheit −14 LUFS / True Peak ≤ −1 dBTP (TikTok-Norm)

## Was eingebaut wurde

### TikTok-Untertitel (klassisch)
- Box `#fefefe`, Text `#0f2334`, Poppins Bold 56 px, je Zeile eine abgerundete Box (klassischer TikTok-Look)
- Phrasenweise und wortgenau auf die Sprache getimt (Whisper-Wort-Timestamps), kurzer Pop-In
- Produktnamen korrekt geschrieben: Zaun **Alira**, Sauna **Lagom Deluxe**, Whirlpool **Stream Big**
- Position y ≈ 1300 px: innerhalb der TikTok-Safe-Zone, frei von UI und Produkten

### Motion Graphics (CI: Navy/Weiß, Poppins, eckige Boxen)
| Zeit | Element |
|---|---|
| 0,0 s | Zoom-Punch-In |
| 1,26 s | „BLACK FRIDAY“-Badge, der mit Kamerawackler ins Bild knallt |
| 2,24 s | „10 % RABATT“-Sticker; ab 4,03 s durchgestrichen, dann fällt er aus dem Bild |
| 4,03 s | Freeze in Schwarz-Weiß mit Vignette, Filmkorn und langsamem Push-In |
| 5,23 s | Weißer Flash und Zoom-Punch auf den Beat-Drop |
| 5,7–7,2 s | „15 %“ und „20 %“ erscheinen, werden durchgestrichen und fliegen raus |
| 7,24 s | „25 %“-Slam mit Druckwelle, danach „AUF ALLES“ |
| 10,5 s | Produktkarte Zaun ALIRA mit Callout-Linie und Zähler „ÜBER 280 € GESPART“ |
| 15,25 s | Produktkarte Fasssauna LAGOM DELUXE mit Zähler „ÜBER 1.200 € GESPART“ |
| 18,55 s | Produktkarte Outdoor-Whirlpool STREAM BIG mit Zähler „ÜBER 1.200 € GESPART“ (Linie folgt der Kamera) |
| 21,4 s | Drei Spar-Chips verschmelzen zur Gesamtsumme „ZUSAMMEN ÜBER 2.700 € GESPART“ (Zähler) |
| 24,05 s | Banner „NUR AM BLACK-FRIDAY-WOCHENENDE“ |
| 26,05 s | Navy-Wipe in die Endcard |
| 26,4 s | Animierte Endcard: Logo, Balken, 25 %-Slam, Staffelung, CTA-Pop, Puls und Tap-Animation |

Die Zähler landen jeweils genau, wenn die Sprecherin den Betrag nennt. Kamerawackler sitzen auf jedem Aufprall (Zaunelemente, Sauna, Whirlpool).

### Sound
- **Eigene Musik**, synthetisch erzeugt, damit sie lizenzfrei ist. Future House mit ca. 125 BPM in f-Moll. Das Tempo ist so gewählt, dass genau 11 Takte zwischen Drop (5,23 s) und Endcard (26,37 s) passen.
  - Intro mit verspieltem Pizzicato-Groove
  - Bei 4,03 s Scratch und Record-Stop
  - Drop auf den Garten-Schnitt
  - Kurzer Break bei 20,6 s, Re-Drop auf „2.700“
  - Schluss-Hit auf der Endcard
- **Sounddesign:** Whooshes, Impacts, Riser, Reverse-Cymbal, dumpfe Aufpralle der Zaunelemente, Wasser-Splash, Zähler-Ticks, Ka-Ching, Pops, Funkeln und Klick auf den CTA
- **Mix:** Die Stimme wurde mit EQ und Kompressor bearbeitet. Die Musik duckt automatisch unter die Sprache (ca. −9 dB), dadurch liegt die Stimme im Schnitt rund 12 dB über dem Bett. Zum Schluss Normalisierung auf −14 LUFS.

## Neu rendern

Benötigt: Python 3 mit `numpy`, `scipy`, `opencv-python-headless`, `Pillow`, dazu `ffmpeg` und Poppins (400–900, TTF) in einem Ordner.

```bash
cd build
ffmpeg -i ORIGINAL.mp4 -vn -c:a pcm_s16le orig.wav
ffmpeg -i orig.wav -af "highpass=f=75,equalizer=f=3500:t=q:w=1.2:g=2,acompressor=threshold=-22dB:ratio=3:attack=6:release=140:makeup=3" -ar 48000 -ac 2 voice.wav
python3 audio.py voice.wav ./out
ffmpeg -i out/mix.wav -af loudnorm=I=-14:TP=-1:LRA=11 -ar 48000 out/mix_final.wav
python3 render.py ORIGINAL.mp4 /pfad/zu/poppins out/mix_final.wav final.mp4
# Vorschau-Standbilder:
python3 render.py ORIGINAL.mp4 /pfad/zu/poppins --stills 2.7,7.6,16.2 ./stills
```

Alle Zeiten (Schnitte, Aufpralle, Untertitel) stehen zentral in `build/timeline.py`.
