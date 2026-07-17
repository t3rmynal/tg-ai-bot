#!/usr/bin/env bash
# qa gate: lint, tests, long dash grep, frontend lint/build
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
RUFF=.venv/bin/ruff
[ -x "$PY" ] || PY=python3
[ -x "$RUFF" ] || RUFF=ruff

"$RUFF" check .
"$PY" -m pytest -q

# long dashes (em u+2014, en u+2013) are banned everywhere in the repo
if LC_ALL=C grep -rIn -e $'\xe2\x80\x94' -e $'\xe2\x80\x93' \
    --exclude-dir=.git --exclude-dir=.venv --exclude-dir=venv \
    --exclude-dir=node_modules --exclude-dir=__pycache__ \
    --exclude-dir=.next --exclude-dir=out --exclude-dir=target \
    --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache .; then
  echo "long dash found, replace with a short dash"
  exit 1
fi

# frontend gate, only when the desktop app and pnpm exist
if [ -d desktop ] && command -v pnpm >/dev/null 2>&1; then
  pnpm -C desktop lint
  pnpm -C desktop build
fi

echo "qa ok"
