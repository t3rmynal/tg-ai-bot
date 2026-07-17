#!/usr/bin/env bash
# one-shot dev: start the python core, wait for it, open the tauri window
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
[ -x "$PY" ] || PY=python3

"$PY" -m tgai &
CORE_PID=$!
trap 'kill "$CORE_PID" 2>/dev/null || true' EXIT

# wait for the api to come up
for _ in $(seq 1 40); do
  if curl -sf http://127.0.0.1:8471/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

pnpm -C desktop tauri dev
