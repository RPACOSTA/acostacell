#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv-codespaces/bin/python ]; then
    echo "Execute bash .devcontainer/setup.sh antes de iniciar o estúdio." >&2
    exit 1
fi

export PATH="$PWD/.venv-codespaces/bin:$PATH"
export GRADIO_SERVER_PORT="${GRADIO_SERVER_PORT:-7860}"
log=.venv-codespaces/voice-studio.log
lock=".venv-codespaces/voice-studio-${GRADIO_SERVER_PORT}.lock"

# A restarted Codespace starts the server again. A second hook invocation leaves it running.
nohup flock -n "$lock" .venv-codespaces/bin/python app.py </dev/null >>"$log" 2>&1 &
url="http://127.0.0.1:${GRADIO_SERVER_PORT}/config"

for ((attempt = 0; attempt < 60; attempt++)); do
    if curl -fsS --max-time 2 "$url" 2>/dev/null | grep -F "Rick's Voice Studio V001" >/dev/null; then
        exit 0
    fi
    sleep 1
done

echo "O estúdio não iniciou. Consulte o log em $log." >&2
exit 1
