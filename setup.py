"""py2app build for Dictate.

Alias mode: the bundle references this repo's venv and source (no copying), and
the running process's identity is "Dictate", so macOS attaches Microphone,
Accessibility, and Automation grants to it. Run `./build_app.sh` to build and
install to ~/Applications.
"""
from setuptools import setup

setup(
    app=["app.py"],
    name="Dictate",
    options={"py2app": {
        "argv_emulation": False,
        "plist": {
            "CFBundleName": "Dictate",
            "CFBundleIdentifier": "com.github.serhiibsc.dictate",
            "CFBundleShortVersionString": "1.0",
            "LSUIElement": True,  # menu-bar only: no Dock icon, hidden from Cmd-Tab
            "NSMicrophoneUsageDescription":
                "Dictate records your voice while you hold the hotkey.",
            "NSAppleEventsUsageDescription":
                "Dictate adds your dictations to Apple Reminders.",
        },
    }},
)
