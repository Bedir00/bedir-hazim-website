#!/usr/bin/env bash
# Extrahiert die iPhone-Clips als Bildfolgen (3:4-Ausschnitt, 800x1067, 30 fps) für story.html.
# Usage: ./prepare.sh <ordner-mit-den-IMG_xxxx.mov-dateien>
set -euo pipefail
cd "$(dirname "$0")"
SRC=${1:?Ordner mit den Clips angeben}
mkdir -p frames
echo "window.CLIPS = {" > frames/clips.js
# name   IMG-Nr  vertikale Position des Ausschnitts (0 = oben, 1 = unten)
while read -r name img cy; do
  f=$(ls "$SRC"/*IMG_"$img".mov | head -1)
  mkdir -p "frames/$name"
  ffmpeg -nostdin -loglevel error -y -i "$f" -an \
    -vf "crop=2160:2880:0:(3840-2880)*$cy,scale=800:1067:flags=lanczos,fps=30" \
    -q:v 2 "frames/$name/%04d.jpg"
  n=$(ls "frames/$name" | wc -l)
  echo "  $name: { n: $n }," >> frames/clips.js
  echo "$name (IMG_$img): $n Bilder"
done <<'LIST'
vest   8428 0.30
coat   8414 0.50
flower 8422 0.45
knit   8427 0.50
jewel  8403 0.45
acc    8400 0.45
window 8433 0.75
LIST
echo "};" >> frames/clips.js
