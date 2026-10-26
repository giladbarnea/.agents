#!/usr/bin/env bash
# Mix narration over the ducked music bed, mux it with the rendered frames, and make a <30 MB 720p copy.
set -euo pipefail
cd "$(dirname "$0")"
name="${1:-explainer}"
ffmpeg -v error -y -i build/narration.wav -i build/music.wav -filter_complex \
    "[0:a]asplit=2[voice][key];[1:a]volume=0.3[music];[music][key]sidechaincompress=threshold=0.02:ratio=5:attack=40:release=700[ducked];[voice][ducked]amix=inputs=2:normalize=0,alimiter=limit=0.95[out]" \
    -map "[out]" -c:a aac -b:a 192k build/mix.m4a
ffmpeg -v error -y -i build/video_silent.mp4 -i build/mix.m4a -map 0:v -map 1:a -c copy -shortest -movflags +faststart "$name.mp4"
ffmpeg -v error -y -i "$name.mp4" -vf scale=720:720 -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart "$name-720.mp4"
ffprobe -v error -show_entries stream=codec_type,duration -of compact "$name.mp4"
ls -la "$name.mp4" "$name-720.mp4"
