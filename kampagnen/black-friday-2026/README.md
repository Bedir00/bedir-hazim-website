# Home Deluxe – Black Friday TikTok-Spot (25 % auf alles)

**Datei:** `HomeDeluxe_BlackFriday_TikTok_Untertitel_MotionGraphics.mp4`
1080×1920 · 30 fps · H.264 + AAC 48 kHz · 29,9 s · Lautheit −14 LUFS / Peak ≤ −1,5 dBFS (TikTok-Norm)

## Version 3
- **Neues Voiceover:** muttersprachlich-deutsche Stimme ohne englischen Akzent
- **Neue Übergänge:** aufwendiger und actiongeladener

## Was eingebaut wurde

### Voiceover (ab 4,1 s)
- **Stimme und Herkunft:** Neue Stimme „Orus“ aus Gemini TTS, deutsch und akzentfrei, im kraftvollen TV-Werbesprecher-Stil. Die Creatorin am Anfang (0–4 s) bleibt im Original.
- **Schnitt auf das Bild:** Der Take wird phrasenweise geschnitten (Whisper-Wortgrenzen und Energie-Minimum zwischen den Wörtern). Jede Phrase liegt exakt auf ihrem Bild-Moment, etwa „25 %“ auf dem Slam und die Produktnamen auf den Landungen.
- **Tempo:** Wo nötig, wurde das Tempo formant-erhaltend angepasst, maximal um 12 %.
- **Synchronität:** Untertitel, Spar-Zähler, Kinetic-Typo und Soundeffekte werden automatisch aus dem VO-Timing (`vo_timing.json`) abgeleitet. So bleibt alles synchron.

### Übergänge
| Zeit | Übergang |
|---|---|
| 0,0 s | Burst-In aus Zoom-Blur mit Flash und RGB-Split |
| 4,03 s | Freeze-Hit: Punch, Flash, RGB-Split, Shake, Kameraverschluss-Klick |
| 4,93–5,65 s | **Zoom-Through:** beschleunigte Fahrt in ihr Gesicht, Weißblende, Ausbruch in den Garten mit Light-Streak, alles auf dem Beat-Drop |
| 7,4 s | „25 %“-Slam mit Shockwave-Verzerrung des Hintergrunds |
| 13,33–13,77 s | **Whip-Pan:** Zaun-Shot und Sauna-Shot nebeneinander, Motion-Blur, Lichtblitz |
| 15,2 / 18,95 s | Landungen von Sauna und Whirlpool: Shockwave-Ring am Aufprallpunkt, Shake, RGB-Split, Impact-Sound |
| 21,11–21,63 s | **Spin-Zoom:** Rotation mit Zoom aus dem Whirlpool-Shot hinaus und in den Weitwinkel hinein |
| 25,98–26,37 s | **Match-Cut:** Zoom in die navyblaue „2.700 €“-Box, die zur Endcard wird; danach Settle-Zoom |

### TikTok-Untertitel (klassisch)
- **Look:** Box `#fefefe`, Text `#0f2334`, Poppins Bold 56 px, je Zeile eine abgerundete Box, kurzer Pop-In.
- **Timing:** Die Untertitel starten jeweils mit dem Phrasenbeginn und überlappen nie.
- **Schreibweise:** Zaun **Alira**, Sauna **Lagom Deluxe**, Whirlpool **Stream Big**.

### Motion Graphics (CI: Navy/Weiß, Poppins, eckige Boxen)
| Element | Inhalt |
|---|---|
| Hook | „BLACK FRIDAY“-Badge; „10 % RABATT“-Sticker, der durchgestrichen wird und herausfällt; S/W-Freeze mit Vignette und Filmkorn |
| Kinetic Typo | „15 %“ und „20 %“ werden durchgestrichen und fliegen raus. „25 %“ knallt mit Druckwelle ins Bild, dazu „AUF ALLES“. Alles folgt dem Voiceover. |
| Produktkarten | ALIRA, LAGOM DELUXE und STREAM BIG mit Callout-Linie und Spar-Zähler. Der Zähler landet, während der Betrag gesprochen wird. |
| Summe | Drei Spar-Chips verschmelzen zu „ZUSAMMEN ÜBER 2.700 € GESPART“, dazu das Banner „NUR AM BLACK-FRIDAY-WOCHENENDE“. |
| Endcard | Logo, Balken, „25 %“-Slam, gestaffelte Texte, CTA-Pop, Puls und Tap-Animation |

### Sound
- **Eigene Musik**, synthetisch und lizenzfrei: Future House mit ca. 125 BPM, genau 11 Takte von Drop zu Endcard. Bei 4,03 s Scratch und Record-Stop, Drop auf den Zoom-Through, Re-Drop auf „2.700“.
- **Sounddesign pro Übergang:**
  - Riser, Reverse-Cymbal und Whooshes
  - Whip-Swoosh beim Whip-Pan, Spin-Swell beim Spin-Zoom
  - Impacts auf den Landungen, Wasser-Splash
  - Zähler-Ticks, Ka-Ching, Pops, Funkeln und CTA-Klick
- **Mix:** Die Musik duckt unter die Sprache (ca. −9 dB), die Stimme liegt im Schnitt rund 11 dB über dem Bett. Zum Schluss −14 LUFS und Limiter.

## Neu rendern

Benötigt: Python 3 mit `numpy`, `scipy`, `opencv-python-headless`, `Pillow`, `faster-whisper`, dazu `ffmpeg` (mit rubberband) und Poppins (400–900, TTF).

```bash
cd build
ffmpeg -i ORIGINAL.mp4 -vn -c:a pcm_s16le orig.wav
# 1) Voiceover auf das Bild legen (erzeugt vo_track.wav + vo_timing.json)
python3 vo_assemble.py orig.wav assets/voiceover_orus_take2.wav ./out
cp out/vo_timing.json .
ffmpeg -i out/vo_track.wav -af "highpass=f=80,equalizer=f=300:t=q:w=1.0:g=-2,equalizer=f=3500:t=q:w=1.2:g=2.5,acompressor=threshold=-22dB:ratio=3:attack=5:release=120:makeup=3" -ar 48000 -ac 2 out/vo_proc.wav
# 2) Musik + SFX + Mix
python3 audio.py out/vo_proc.wav ./out
ffmpeg -i out/mix.wav -af "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.87:level=disabled" -ar 48000 out/mix_final.wav
# 3) Bild
python3 render.py ORIGINAL.mp4 /pfad/zu/poppins out/mix_final.wav final.mp4
# Vorschau-Standbilder:
python3 render.py ORIGINAL.mp4 /pfad/zu/poppins --stills 5.17,13.5,21.3,26.2 ./stills
```

- **Neuer VO-Take:** `tts.py` erzeugt ihn über die Gemini-API (Stimme `Orus`, Modell `gemini-3.1-flash-tts-preview`).
- **Zeiten:** Schnitte, Landungen und Musikraster stehen in `build/timeline.py`. Die VO-abhängigen Zeiten kommen aus `vo_timing.json`.
