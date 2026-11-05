# Home Deluxe – Black Friday TikTok-Spot (25 % auf alles)

| Datei | Version |
|---|---|
| `HomeDeluxe_BlackFriday_TikTok_Untertitel_MotionGraphics.mp4` | **v4:** alle Szenen neu in Higgsfield |
| `HomeDeluxe_BlackFriday_TikTok_Mix_UGC-neu_Produktszenen-original.mp4` | **Mix:** neue UGC-Szene, Produktszenen aus dem Original-Spot |

Beide Dateien: 1080×1920 · 24 fps · H.264 + AAC 48 kHz · 34,4 s · −14 LUFS, Peak ≤ −1,5 dBFS (TikTok-Norm)

## Mix-Version: neue UGC-Szene + Original-Produktszenen

| Zeit | Bild | Herkunft |
|---|---|---|
| 0,0–5,4 s | UGC-Hook der Creatorin | neu (v4, Higgsfield) |
| 5,4–7,4 s | Kamerafahrt durchs Wohnzimmer auf die Terrassentür zu, mit Speed-Ramp (erst langsam, dann beschleunigend) | neu (v4, Kling 4.0) |
| 7,4 s | Durchbruch durch die Tür in den Garten: Zoom mit Gegenlicht-Bloom und Light-Streak, genau auf dem Beat-Drop | Übergang |
| 7,4–13,1 s | Zaun-Elemente fallen, in Echtzeit | Original-Spot |
| 13,1–18,75 s | fertiger Zaun in Zeitlupe (Motion-Interpolation), langsame Kamerafahrt | Original-Spot |
| 18,75–26,2 s | Sauna und Whirlpool fallen in den Garten. Der Whirlpool fliegt wie im Original ohne Schnitt herein. | Original-Spot |
| 26,2–31,3 s | Totale mit allen Produkten, langsame Kamerafahrt | Original-Spot |
| 31,3–34,4 s | Endcard | wie v4 |

**Gleich wie in v4:**
- Voiceover (Nora und Vlad), Untertitel, Motion Graphics, Musik und Mix
- Übergänge Whip-Pan, Spin-Zoom und Match-Cut

**Angepasst auf die Originalbilder:**
- **Tempo:** Die Original-Szenen wurden auf das Voiceover-Raster getimt.
- **Grafik:** Die Produktkarten zeigen auf das Produkt im Originalbild.
- **Aufprall:** Shockwaves und Impact-Sounds liegen auf den gemessenen Einschlägen im Original.
- **Kamera:** Die fest stehenden Original-Shots haben eine langsame digitale Kamerafahrt bekommen.

Die Skripte liegen in `mix/build/`. Neu rendern wie bei v4, nur der Bildschnitt kommt aus `assemble_v5.py`:

```bash
cd mix/build
python3 assemble_v5.py ../../v4/build/clips ORIGINAL_SPOT.mp4 ./edit   # erzeugt edit/base_mix.mp4
python3 audio.py ../../v4/build/edit/vo_v4_proc.wav ./out              # danach Loudness wie bei v4
END_SRC=ORIGINAL_SPOT.mp4 python3 render.py edit/base_mix.mp4 /pfad/zu/poppins out/mix_final.wav mix.mp4
```

## Version 4: komplett neu in Higgsfield gedreht

Alle Bewegtbilder und beide Stimmen sind neu und in Higgsfield entstanden. Vom alten Spot sind nur Endcard-Elemente (Logo, Balken) übrig.

- **UGC-Szene:** Die Creatorin ist natürlicher, filmt sich selbst mit Handkamera und hat echte Wohnzimmer-Details.
- **Übergang aus der UGC-Szene:** Die Kamera fliegt durch die Terrassentür in den Garten. Es gibt keinen harten Schnitt mehr.
- **Gartenszenen:** fotoreal und mit bewegter Kamera (Drohne, Gimbal, Kran). Die Produkte fallen mit echtem Gewicht ins Bild.
- **Stimmen:** Beide sind muttersprachlich und ohne Versprecher. Die Produktszenen spricht eine tiefe Männerstimme.

### Arbeitsweise: zuerst die Keyframes, dann das Video
Für jede Szene wurden zuerst die Start- und Endframes als Standbild gebaut und abgenommen (`v4/keyframes/`, Übersicht in `00_storyboard.jpg`). Erst danach wurde animiert.

- **Image-to-Video:** Die Videomodelle bekamen diese Frames als Start- bzw. Endbild.
- **Produkttreue:** Form, Farbe und Proportionen der Produkte stimmen dadurch mit den echten Home-Deluxe-Produkten überein.
- **Durchgehender Garten:** In allen Szenen ist es derselbe Garten, derselbe Rasen und dasselbe Licht.

### Welches KI-Modell für welche Szene

| Szene | Zeit | Keyframe-Modell | Video-Modell | Warum |
|---|---|---|---|---|
| S1 UGC-Hook („Leute, Leute, Black Friday …“) | 0,0–5,4 s | **Soul 2** (fotoreale Personen, iPhone-Selfie-Look) | **Intone** (Talking Head), danach **Sync Lipsync 3** | Intone liefert die natürlichste Mimik und Handkamera. Sync Lipsync 3 legt die Lippen exakt auf die saubere Sprachaufnahme. |
| S2 Kamerafahrt durch die Terrassentür | 5,4–7,4 s | **Nano Banana Pro** (Innenraum, Garten-Masterplate) | **Kling 4.0** (Start- + Endframe) | Kling hält eine Kamerafahrt zwischen zwei vorgegebenen Bildern am saubersten. |
| S3a Zaun ALIRA fällt Element für Element | 7,4–13,1 s | Nano Banana Pro (mit Produktfotos als Referenz) | **Kling 4.0** (Start- + Endframe) | Das Ende muss exakt auf dem fertigen Zaun landen, deshalb mit Endframe. |
| S3b Zaun-Hero (Gimbal-Fahrt an den Lamellen) | 13,1–18,75 s | identischer Frame wie Ende S3a | **Kling 4.0** | nahtloser Anschluss an S3a, ruhige Produktfahrt |
| S4 Sauna LAGOM DELUXE kracht in den Garten | 18,75–22,4 s | Nano Banana Pro | **MiniMax H3** (Bake-off-Sieger) | höchste Produkttreue, glaubwürdigster Aufprall |
| S5 Whirlpool STREAM BIG mit Wasserkrone | 22,4–26,2 s | Nano Banana Pro | **MiniMax H3** | beste Wassersimulation, Wanne bleibt formstabil |
| S6 Blue-Hour-Hero (Drohne steigt auf) | 26,2–31,3 s | Nano Banana Pro | **MiniMax H3** (gegen Kling 4.0 getestet) | Alle drei Produkte bleiben sichtbar und unverformt. |
| Endcard | 31,3–34,4 s | Originalelemente | Motion Graphics | |

**Bake-off an der Sauna-Szene:** Drei Modelle haben denselben Prompt mit denselben Keyframes bekommen. Die Ergebnisse wurden Bild für Bild und zusätzlich mit einer KI-VFX-Bewertung verglichen.

| Modell | Credits | Ergebnis |
|---|---|---|
| Veo 3.1 | 60 | Schöner Staub, aber Rasenstücke schweben unphysikalisch. |
| Kling 4.0 | 19,5 | Gute Dynamik, aber das Saunadach verformt sich beim Aufprall. |
| **MiniMax H3** | 12 | **Sieger:** Die Sauna bleibt formstabil, der Aufprall wirkt glaubwürdig. |

### Stimmen
Beide Stimmen kommen aus **ElevenLabs v4 in Higgsfield**.

**Auswahl (Casting):**
- **Vorgehen:** Pro Rolle wurden mehrere Stimmen und Takes erzeugt.
- **Akzent:** Eine KI hat die Takes auf Akzent geprüft.
- **Versprecher:** Ein Whisper-Transkript hat die Takes auf Versprecher geprüft.
- **Tiefe:** Die Stimmlage wurde per Grundfrequenz-Analyse (F0) gemessen.

| Rolle | Stimme | Charakter |
|---|---|---|
| Creatorin (UGC-Hook) | **Nora** | junge, natürliche Muttersprachlerin, ironisch-genervt, wie gesprochen und nicht vorgelesen |
| Produktsprecher | **Vlad** | tief, ruhig und autoritär, Trailer- bzw. Werbesprecher. Die Betonung wurde pro Satz über Regie-Tags gesteuert. |

**Regie pro Szene (Produktsprecher):**
| Szene | Regie |
|---|---|
| Einstieg | bestimmt und tief |
| „Nicht 15, nicht 20“ | Spannung aufbauen |
| „25 %“ | kraftvoll und punchy |
| „Klingt nach wenig?“ | verschmitzt |
| Zaun | selbstbewusst |
| Sauna | warm und entspannt |
| Whirlpool | energisch |
| Summe | groß und beeindruckend |
| „Nur am Black-Friday-Wochenende“ | dringlich |
| „Home Deluxe“ | warmer Sign-off |

**Versprecher-Prüfung:** Die komplette Tonspur wurde mit Whisper transkribiert. Das Ergebnis stimmt Wort für Wort mit dem Skript überein, auch „Zaun Alira“, „Sauna Lagom Deluxe“ und „Whirlpool Stream Big“.

**UGC-Szene:**
- **Lippen:** Intone synthetisiert beim Lip-Sync die Stimme neu, mit leicht metallischem Klang und einem Versprecher. Deshalb wurde das Video mit **Sync Lipsync 3** noch einmal auf die **unveränderte Originalaufnahme** gelippt.
- **Ton:** Im Spot läuft die saubere Aufnahme.

### Übergänge
| Zeit | Übergang |
|---|---|
| 0,0 s | Burst-In aus Zoom-Blur |
| 5,06–5,80 s | **Zoom-Through mit Bloom:** Die Kamera beschleunigt auf die Terrassentür zu. Warmes Gegenlicht überstrahlt das Bild, es gibt keine Weißblende mehr. Dann folgt die FPV-Fahrt hinaus in den Garten, mit Light-Streak. |
| 7,4 s | **Beat-Drop:** Die Kamera landet im Garten, gleichzeitig schlägt das erste Zaunelement ein. |
| 13,13 s | nahtloser Übergang Zaun-Drop → Zaun-Hero (identischer Frame) |
| 18,75 s | **Whip-Pan:** Zaun und Sauna stehen kurz nebeneinander, dann fällt die Sauna ins Bild. |
| 20,1 s | **Sauna-Aufprall:** Shockwave am Aufprallpunkt, Shake, RGB-Split |
| 22,42 s | **Crash-Zoom** auf die Sauna, der Whirlpool fällt herein. |
| 23,0 s | **Whirlpool-Aufprall:** Wasserkrone, Shockwave, Splash-Sound |
| 26,17 s | **Spin-Zoom** in den Blue-Hour-Hero-Shot |
| 30,9–31,3 s | **Match-Cut:** Zoom in die navyblaue „2.700 €“-Box, die zur Endcard wird |

### TikTok-Untertitel (klassisch)
- **Look:** Box `#fefefe`, Text `#0f2334`, Poppins Bold, je Zeile eine Box, kurzer Pop-In.
- **Timing:** Phrasengenau auf beide Stimmen, die Untertitel überlappen nie.
- **Schreibweise:** Zaun **Alira**, Sauna **Lagom Deluxe**, Whirlpool **Stream Big**.

### Motion Graphics (CI: Navy/Weiß, Poppins, eckige Boxen)
| Element | Inhalt |
|---|---|
| Hook | „BLACK FRIDAY“-Badge, „10 % RABATT“-Sticker, der durchgestrichen wird und herausfällt |
| Kinetic Typo | „15 %“ und „20 %“ werden durchgestrichen. „25 %“ knallt mit Druckwelle ins Bild, dazu „AUF ALLES“. |
| Produktkarten | ALIRA, LAGOM DELUXE und STREAM BIG mit Callout-Linie und Spar-Zähler. Die Karten sind am Produkt im Bild verankert und wandern mit der Kamera. |
| Summe | Drei Spar-Chips verschmelzen zu „ZUSAMMEN ÜBER 2.700 € GESPART“, dazu das Banner „NUR AM BLACK-FRIDAY-WOCHENENDE“. |
| Endcard | Logo, Balken, „25 %“-Slam, gestaffelte Texte, CTA-Pop, Puls und Tap-Animation |

### Sound
- **Musik:** synthetisch und lizenzfrei, ca. 120 BPM. Genau 12 Takte vom Drop (Kamera landet im Garten) bis zur Endcard. Unter dem Spin-Zoom liegt ein Break, auf „2.700“ folgt der Re-Drop.
- **Sounddesign:**
  - Tür-Whoosh und FPV-Whoosh mit Reverse-Cymbal und Riser in den Drop
  - Aufprall-Thuds auf den gemessenen Einschlägen der Zaunelemente
  - Fall-Whoosh und Impact der Sauna
  - Crash-Zoom, dazu Whirlpool-Impact mit Wasser-Splash
  - Whip und Spin
  - Zähler-Ticks, Ka-Ching und Pops
- **Mix:** Die Musik duckt unter die Sprache, zum Schluss −14 LUFS (zweistufig) und Limiter.

## Neu rendern (v4)

Benötigt:
- **Python 3** mit `numpy`, `scipy`, `opencv-python-headless`, `Pillow` und `faster-whisper`
- **ffmpeg** mit rubberband und minterpolate
- **Schrift:** Poppins (400–900, TTF)

Die Higgsfield-Clips liegen nicht im Repo, weil sie zu groß sind. Sie stehen im Higgsfield-Projekt „Home Deluxe – Black Friday TikTok v4“.

```bash
cd v4/build
# 1) Bild: Clips auf das VO-Raster schneiden (Speed je Szene automatisch, Zeitlupe mit Motion-Interpolation)
python3 assemble_v4.py ./clips ./edit
# 2) Voiceover: UGC-Hook + Produktsprecher phrasenweise montieren (erzeugt vo_v4.wav + vo_v4.json)
WHISPER_DIR=./models python3 vo_v4.py assets/vo_female_nora_hook.mp3 assets/vo_male_vlad_take.mp3 ./edit
ffmpeg -i edit/vo_v4.wav -af "highpass=f=80,equalizer=f=300:t=q:w=1.0:g=-1.5,equalizer=f=3500:t=q:w=1.2:g=2,acompressor=threshold=-22dB:ratio=3:attack=5:release=120:makeup=3" -ar 48000 -ac 2 edit/vo_v4_proc.wav
# 3) Musik + SFX + Mix, dann Loudness
python3 audio.py edit/vo_v4_proc.wav ./out
ffmpeg -i out/mix.wav -af "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.87:level=disabled" -ar 48000 out/mix_final.wav
# 4) Grafik, Untertitel und Übergänge rendern
END_SRC=ORIGINAL_SPOT.mp4 python3 render.py edit/base_v4.mp4 /pfad/zu/poppins out/mix_final.wav final.mp4
# Vorschau-Standbilder:
END_SRC=ORIGINAL_SPOT.mp4 python3 render.py edit/base_v4.mp4 /pfad/zu/poppins --stills 5.4,7.5,20.1,23.1,28.0 ./stills
```

| Datei | Inhalt |
|---|---|
| `timeline.py` | alle Schnitte, gemessenen Aufprall-Zeiten, Musikraster, Untertitel und Grafik-Anker |
| `assemble_v4.py` | Szenentabelle: Clip, In- und Out-Punkt, Slot auf der Timeline |
| `align_voice.py` | Hilfswerkzeug (DTW + WSOLA), um eine saubere Aufnahme auf das Timing eines gelippten Videos zu legen |

Die v3-Skripte liegen weiter unter `build/`.
