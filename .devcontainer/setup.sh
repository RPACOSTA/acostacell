#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v ffmpeg >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends ffmpeg
fi

if [ ! -x .venv/bin/python ]; then
    python -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check gradio==6.32.0 -r requirements.txt
