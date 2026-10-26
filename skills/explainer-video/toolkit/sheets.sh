#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/build"
rm -f sheet_*.jpg
ls stills/s*.png | sort > list.txt
split -l 12 list.txt chunk_
index=0
for chunk in chunk_*; do
    inputs=()
    while read -r file; do inputs+=(-i "$file"); done < "$chunk"
    count=$(wc -l < "$chunk" | tr -d ' ')
    filter=""
    for ((i = 0; i < count; i++)); do filter+="[$i:v]scale=600:600[v$i];"; done
    for ((i = 0; i < count; i++)); do filter+="[v$i]"; done
    layout=""
    for ((i = 0; i < count; i++)); do
        layout+="$(( (i % 4) * 600 ))_$(( (i / 4) * 600 ))|"
    done
    filter+="xstack=inputs=$count:layout=${layout%|}:fill=white"
    ffmpeg -v error -y "${inputs[@]}" -filter_complex "$filter" -q:v 3 "sheet_$index.jpg"
    index=$((index + 1))
done
rm -f chunk_* list.txt
ls sheet_*
