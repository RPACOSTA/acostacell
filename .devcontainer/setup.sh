#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! python3 -c 'import os, sys; sys.exit(not (os.confstr("CS_GNU_LIBC_VERSION") or "").startswith("glibc "))' 2>/dev/null; then
    echo "O Python deste terminal não reportou glibc. O PyTorch CPU do estúdio usa a imagem Debian definida no projeto." >&2
    echo "Se o Codespace já foi reconstruído, abra Codespaces: View Creation Log no VS Code para identificar o erro de criação." >&2
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
