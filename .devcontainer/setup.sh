#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi

if ! command -v ffmpeg >/dev/null; then
    # This release ships manylinux2014 wheels for Linux x86-64 and ARM64.
    .venv/bin/python -m pip install --disable-pip-version-check \
        --index-url https://pypi.org/simple --only-binary=imageio-ffmpeg imageio-ffmpeg==0.6.0
    ffmpeg_path=$(.venv/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
    ln -sfn "$ffmpeg_path" .venv/bin/ffmpeg
    .venv/bin/ffmpeg -version >/dev/null
fi

.venv/bin/python -m pip install --disable-pip-version-check gradio==6.32.0 -r requirements.txt
