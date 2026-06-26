#!/bin/sh
# Build ~/Applications/Dictate.app (menu-bar only) via py2app, in alias mode.
#
# Alias mode keeps the bundle thin: it references this repo's venv and source
# instead of copying mlx/torch/etc. into the app, so the build is fast and edits
# to app.py / dictate.py take effect without rebuilding. The important win over a
# plain shell wrapper: the running process's identity is "Dictate" (not
# Homebrew's Python.app), so macOS attributes Microphone and Accessibility to
# Dictate and the grants stick. LSUIElement (set in setup.py) keeps it menu-bar
# only — no Dock icon, hidden from Cmd-Tab.
#
# Because it's an alias build, the app references this repo + venv by absolute
# path: rebuild after moving the repo or recreating the venv.
set -e

cd "$(dirname "$0")"
PY="./.venv/bin/python"
APP="$HOME/Applications/Dictate.app"

if [ ! -x "$PY" ]; then
    echo "error: $PY not found. Create the venv first (see README Setup)." >&2
    exit 1
fi

# py2app is only needed to build, not to run — install on demand.
if ! "$PY" -c "import py2app" 2>/dev/null; then
    echo "Installing py2app (build-only dependency)…"
    "$PY" -m pip install py2app
fi

echo "Building (py2app alias)…"
rm -rf build dist
"$PY" setup.py py2app -A >/dev/null

echo "Installing to $APP"
mkdir -p "$HOME/Applications"
rm -rf "$APP"
ditto dist/Dictate.app "$APP"

# Register so Spotlight/Finder pick it up immediately.
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP"

echo "Built: $APP"
echo "Next: launch it once (Spotlight → Dictate), grant Microphone + Accessibility,"
echo "      then add it to Login Items (System Settings → General → Login Items)."
