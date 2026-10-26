#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
total=$(uv run render.py total)
frames=$(awk "BEGIN { print int($total * 24 + 0.999) }")
workers=6
per=$(( (frames + workers - 1) / workers ))
rm -f build/part_*.mp4 build/parts.txt
for ((w = 0; w < workers; w++)); do
    first=$(( w * per ))
    last=$(( first + per < frames ? first + per : frames ))
    uv run render.py video "$first" "$last" "build/part_$w.mp4" &
    echo "file 'part_$w.mp4'" >> build/parts.txt
done
wait
ffmpeg -v error -y -f concat -safe 0 -i build/parts.txt -c copy build/video_silent.mp4
echo "frames=$frames"
