# First Chance – Instagram Story (Apple-Stil)

1080×1920 (9:16), 30 fps, 30 s · `first-chance_instagram-story.mp4`

## Script (überarbeitet – für Voiceover oder Caption)

> Hallo ihr Lieben,
> wir haben Neuigkeiten: Second Chance & more verabschiedet sich offiziell von Second-Hand-Ware.
> Weil ihr so oft danach gefragt habt, gibt es bei uns ab sofort unsere eigenen, brandneuen Kollektionen.
> Neues Kapitel, neuer Name: Aus Second Chance wird **First Chance**.
> Entdeckt unsere neue Herbst-/Winter-Mode, Schmuck und Accessoires.
> Kommt vorbei – bei First Chance in Espelkamp.
> Wir freuen uns auf euch!

## On-Screen-Texte (Storyboard)

| Zeit | Text | Clip |
|---|---|---|
| 0–2,8 s | *Second Chance & more* – **Wir haben Neuigkeiten.** | – |
| 2,8–6 s | **Tschüss, ~~Second Hand.~~** – Danke für die schöne Zeit. | – |
| 6–10 s | *Ihr habt gefragt.* – **Unsere eigenen Kollektionen.** | Fellweste (IMG_8428) |
| 10–14 s | *Neues Kapitel. Neuer Name.* – **Second → First Chance** | – |
| 14–22,5 s | *Jetzt neu.* – **Herbst / Winter.** Mäntel · Jacken · Strick · Schmuck · Accessoires | IMG_8414, 8422, 8427, 8403, 8400 |
| 22,5–25,7 s | **Kommt vorbei.** | Schaufenster (IMG_8433) |
| 25,7–30 s | **First Chance** · Espelkamp · Wir freuen uns auf euch. | – |

Instagram-Safe-Zones beachtet: oben 250 px und unten 300 px bleiben frei von wichtigen Inhalten.

## Neu erzeugen

```bash
./prepare.sh /pfad/zu/den/IMG_xxxx.mov-clips   # Clips -> Bildfolgen (frames/)
node render.js first-chance_instagram-story.mp4  # benötigt Playwright + ffmpeg
node render.js --preview 4.6 12.9 28.5           # einzelne Vorschaubilder
```

Texte, Timing und Farben stehen in `story.html` (Abschnitt „Zeitplan“ bzw. `:root`).
