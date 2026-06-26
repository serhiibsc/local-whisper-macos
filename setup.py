"""py2app build for Dictate.

Alias mode keeps the bundle thin — it references this repo's venv and source
instead of copying mlx/torch/etc. into the app, and edits to app.py take effect
without a rebuild. The win over the old thin shell wrapper: the running process
*is* Dictate (not Homebrew's Python.app), so macOS attributes Microphone and
Accessibility to "Dictate" and the grants stick.

Build (alias):  .venv/bin/python setup.py py2app -A
Most people just run ./build_app.sh, which wraps this and installs to
~/Applications.
"""
from setuptools import setup

setup(
    app=["app.py"],
    name="Dictate",
    options={
        "py2app": {
            "argv_emulation": False,
            "plist": {
                "CFBundleName": "Dictate",
                "CFBundleDisplayName": "Dictate",
                "CFBundleIdentifier": "com.github.serhiibsc.dictate",
                "CFBundleVersion": "1.0",
                "CFBundleShortVersionString": "1.0",
                # Menu-bar only: no Dock icon, hidden from Cmd-Tab.
                "LSUIElement": True,
                "NSMicrophoneUsageDescription":
                    "Dictate records your voice while you hold the hotkey.",
            },
        }
    },
)
