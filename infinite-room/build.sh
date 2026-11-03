#!/usr/bin/env bash
# Erzeugt das Video "Schwarzer unendlicher Raum" komplett aus dem Quellcode.
#   ./build.sh            -> 1920x1080, 60 fps, 7,5 s pro Raum, 4 Schleifen (30 s)
# Benötigt: g++, ffmpeg, python3 + numpy
set -euo pipefail
cd "$(dirname "$0")"

W=${W:-1920}; H=${H:-1080}; FPS=${FPS:-60}; PERIOD=${PERIOD:-7.5}; LOOPS=${LOOPS:-4}; SPP=${SPP:-3}
FRAMES=$(python3 -c "print(round($FPS*$PERIOD))")
OUT=${OUT:-out}
mkdir -p "$OUT"

g++ -O3 -march=native -ffast-math -std=c++17 -pthread render.cpp -o render

# 1) eine nahtlose Schleife rendern (letztes Bild geht exakt ins erste über)
./render "$W" "$H" "$FRAMES" "$SPP" \
  | ffmpeg -loglevel error -y -f rawvideo -pix_fmt rgb24 -s "${W}x${H}" -r "$FPS" -i - \
      -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -profile:v high \
      -g "$FRAMES" -keyint_min "$FRAMES" -movflags +faststart "$OUT/loop_master.mp4"

# 2) Ton: Shepard-Risset-Glissando, eine Oktave pro Raum
python3 audio.py "$PERIOD" "$LOOPS" "$OUT/audio.wav"

# 3) Endlos-Loop ohne Ton (für Website-Banner: <video autoplay muted loop playsinline>)
ffmpeg -loglevel error -y -i "$OUT/loop_master.mp4" -c:v libx264 -preset slow -crf 20 \
  -pix_fmt yuv420p -profile:v high -movflags +faststart -an "$OUT/unendlicher-raum_16x9_loop.mp4"

# 4) 30-Sekunden-Video mit Ton (Social / YouTube)
ffmpeg -loglevel error -y -stream_loop $((LOOPS - 1)) -i "$OUT/loop_master.mp4" -i "$OUT/audio.wav" \
  -map 0:v -map 1:a -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -profile:v high \
  -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT/unendlicher-raum_16x9_30s.mp4"

echo "fertig: $OUT/"
