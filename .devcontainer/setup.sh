#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check \
    --only-binary=imageio-ffmpeg gradio==6.32.0 imageio-ffmpeg==0.8.1 -r requirements.txt

# The wheel provides FFmpeg on Linux without a system package manager.
ffmpeg_path=$(.venv/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
ln -sfn "$ffmpeg_path" .venv/bin/ffmpeg
.venv/bin/ffmpeg -version >/dev/null
