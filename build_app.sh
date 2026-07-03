#!/bin/sh
# Build the menu-bar Dictate.app (py2app, alias mode) and install it to
# ~/Applications. Alias mode references this repo + venv by absolute path, so
# rebuild after moving the repo or recreating the venv.
set -e
cd "$(dirname "$0")"

PY="./.venv/bin/python"
APP="$HOME/Applications/Dictate.app"

if [ ! -x "$PY" ]; then
    echo "error: $PY not found — create the venv first (see README)." >&2
    exit 1
fi
if ! "$PY" -c "import py2app" 2>/dev/null; then
    echo "Installing py2app (build-only)…"
    "$PY" -m pip install py2app
fi

echo "Building…"
rm -rf build dist
"$PY" setup.py py2app -A >/dev/null

echo "Installing to $APP"
mkdir -p "$HOME/Applications"
rm -rf "$APP"
ditto dist/Dictate.app "$APP"
rm -rf build dist   # don't leave a second bundle with the same id in the repo

LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP"

echo "Built $APP"
echo "Launch it once, grant Microphone + Accessibility + Input Monitoring, then"
echo "add it to Login Items (System Settings → General → Login Items)."
