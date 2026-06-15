#!/usr/bin/env bash
# Copies the layer-3 runtime files next to this page (they're the skill's
# canonical scripts, kept out of git here to avoid drift) and starts the
# annotation server. Then open http://127.0.0.1:8765/index.html
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
scripts="$here/../../scripts"
cp "$scripts"/{style.css,interactions.js,annotations.css,annotations.js,annotation-writer.mjs} "$here/"
cd "$here"
node annotation-writer.mjs
