#!/usr/bin/env bash
# Screencast (SIN-1432): Rohvideo aus frontend/e2e/screencast.spec.ts auf ca. 60 s kuerzen und als MP4 (H.264) + WebM
# nach docs/assets/ legen, wenn beide unter 10 MB bleiben; sonst nur in tmp/screencast/ lassen und den Pfad nennen.
# Aufruf (Demo laeuft, siehe spec): bash scripts/screencast.sh [rohvideo.webm]
set -euo pipefail
cd "$(dirname "$0")/.."
RAW="${1:-tmp/screencast/rohvideo.webm}"
TMP=tmp/screencast
LIMIT=$((10 * 1024 * 1024))
command -v ffmpeg >/dev/null || { echo "ffmpeg fehlt" >&2; exit 1; }
[ -f "$RAW" ] || { echo "Rohvideo fehlt: $RAW" >&2; exit 1; }
mkdir -p "$TMP" docs/assets

# Auf 60 s begrenzen (-t), 1280x720, 25 fps; kuerzere Aufnahmen bleiben unveraendert
ffmpeg -y -i "$RAW" -t 60 -vf "scale=1280:720,fps=25" -c:v libx264 -pix_fmt yuv420p -crf 26 -an -movflags +faststart "$TMP/stromlauf-demo.mp4"
ffmpeg -y -i "$RAW" -t 60 -vf "scale=1280:720,fps=25" -c:v libvpx-vp9 -crf 36 -b:v 0 -an "$TMP/stromlauf-demo.webm"

size() { stat -c %s "$1" 2>/dev/null || stat -f %z "$1"; }
if [ "$(size "$TMP/stromlauf-demo.mp4")" -lt "$LIMIT" ] && [ "$(size "$TMP/stromlauf-demo.webm")" -lt "$LIMIT" ]; then
  cp "$TMP/stromlauf-demo.mp4" "$TMP/stromlauf-demo.webm" docs/assets/
  echo "Abgelegt: docs/assets/stromlauf-demo.mp4 und .webm"
else
  echo "Mindestens eine Datei ueber 10 MB: nur lokal unter $TMP/ (nicht einchecken)"
fi
