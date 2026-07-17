#!/usr/bin/env bash
# build the python core into a single binary and place it where tauri expects
# the sidecar (binaries/tgai-server-<target-triple>). run before a release build.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
TRIPLE="$($PY -c 'import subprocess; print(subprocess.check_output(["rustc","-Vv"]).decode().split("host: ")[1].split("\n")[0])')"

echo "building sidecar for $TRIPLE"

$PY -m pip install --quiet --upgrade pyinstaller
$PY -m pip install --quiet -e .

DIST="desktop/src-tauri/binaries"
mkdir -p "$DIST"

$PY -m PyInstaller --noconfirm --onefile --clean \
  --name tgai-server \
  --collect-submodules telethon \
  --collect-submodules uvicorn \
  --collect-submodules python_socks \
  --hidden-import aiohttp_socks \
  --distpath "$DIST/_out" \
  scripts/_sidecar_entry.py

EXT=""
case "$TRIPLE" in
  *windows*) EXT=".exe" ;;
esac

mv "$DIST/_out/tgai-server$EXT" "$DIST/tgai-server-$TRIPLE$EXT"
rm -rf "$DIST/_out" build tgai-server.spec
echo "sidecar ready: $DIST/tgai-server-$TRIPLE$EXT"
