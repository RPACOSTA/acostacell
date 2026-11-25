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

if ! command -v ffmpeg >/dev/null; then
    # This release ships manylinux2014 wheels for Linux x86-64 and ARM64.
    .venv-codespaces/bin/python -m pip install --disable-pip-version-check \
        --index-url https://pypi.org/simple --only-binary=imageio-ffmpeg imageio-ffmpeg==0.6.0
    ffmpeg_path=$(.venv-codespaces/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
    ln -sfn "$ffmpeg_path" .venv-codespaces/bin/ffmpeg
    .venv-codespaces/bin/ffmpeg -version >/dev/null
fi

.venv-codespaces/bin/python -m pip install --disable-pip-version-check gradio==6.32.0 -r requirements.txt
