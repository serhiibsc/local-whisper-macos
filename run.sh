#!/bin/sh
# Launch the menu-bar dictation app from this repo's venv.
# Used both for running by hand (./run.sh) and from the launchd login agent.
cd "$(dirname "$0")"
exec .venv/bin/python app.py
