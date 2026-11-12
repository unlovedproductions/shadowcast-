#!/usr/bin/env bash
# Fetch Mixkit free pack into backend/assets/{music,broll}/ and convert for ShadowCast.
# Requires: curl, ffmpeg. Safe to re-run (skips existing targets).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MUSIC_DIR="$ROOT/backend/assets/music"
BROLL_DIR="$ROOT/backend/assets/broll"
TMP="${TMPDIR:-/tmp}/shadowcast-media-pack.$$"
mkdir -p "$MUSIC_DIR" "$BROLL_DIR" "$TMP"
trap 'rm -rf "$TMP"' EXIT

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 required on PATH"; exit 1; }; }
need curl
need ffmpeg

fetch_music() {
  local mood="$1" url="$2" src dest
  dest="$MUSIC_DIR/${mood}.wav"
  if [[ -f "$dest" ]]; then
    echo "skip music $mood (exists)"
    return 0
  fi
  src="$TMP/${mood}.mp3"
  echo "fetch music $mood"
  curl -fsSL -o "$src" "$url"
  ffmpeg -y -i "$src" -ac 1 -ar 44100 -c:a pcm_s16le "$dest" >/dev/null 2>&1
  echo "wrote $dest"
}

fetch_broll() {
  local name="$1" url="$2" src dest
  dest="$BROLL_DIR/${name}.mp4"
  if [[ -f "$dest" ]]; then
    echo "skip broll $name (exists)"
    return 0
  fi
  src="$TMP/${name}.src.mp4"
  echo "fetch broll $name"
  curl -fsSL -o "$src" "$url"
  ffmpeg -y -i "$src" -t 10 -an -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p "$dest" >/dev/null 2>&1
  echo "wrote $dest"
}

# Music — Mixkit Free Stock Music (see backend/assets/music/ATTRIBUTION.md)
fetch_music chill "https://assets.mixkit.co/music/138/138.mp3"
fetch_music energetic "https://assets.mixkit.co/music/80/80.mp3"
fetch_music dramatic "https://assets.mixkit.co/music/601/601.mp3"
fetch_music minimal "https://assets.mixkit.co/music/441/441.mp3"

# B-roll — Mixkit Free Stock Video (see backend/assets/broll/ATTRIBUTION.md)
fetch_broll pad "https://assets.mixkit.co/videos/46635/46635-720.mp4"
fetch_broll default "https://assets.mixkit.co/videos/99786/99786-1080.mp4"
fetch_broll pros "https://assets.mixkit.co/videos/4809/4809-720.mp4"
fetch_broll cons "https://assets.mixkit.co/videos/31771/31771-720.mp4"
fetch_broll verdict "https://assets.mixkit.co/videos/43527/43527-1080.mp4"
fetch_broll comparison "https://assets.mixkit.co/videos/9757/9757-720.mp4"

echo "done. music=$(ls -1 "$MUSIC_DIR"/*.wav 2>/dev/null | wc -l) broll=$(ls -1 "$BROLL_DIR"/*.mp4 2>/dev/null | wc -l)"
