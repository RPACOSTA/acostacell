#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! getconf GNU_LIBC_VERSION >/dev/null 2>&1; then
    echo "O PyTorch CPU do estúdio precisa de glibc. No VS Code do Codespace, execute Codespaces: Rebuild Container para carregar a imagem Debian do projeto." >&2
    exit 1
fi

if [ ! -x .venv-codespaces/bin/python ]; then
    python3 -m venv .venv-codespaces
fi

if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
    # Debian's FFmpeg package includes ffprobe, which Gradio uses to check the exported WAV.
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends ffmpeg
fi
ffmpeg -version >/dev/null
ffprobe -version >/dev/null

.venv-codespaces/bin/python -m pip install --disable-pip-version-check gradio==6.32.0 -r requirements.txt
