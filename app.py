#!/usr/bin/env python3
"""Menu-bar front-end for the dictate.py pipeline.

Blank when idle. Hold the hotkey (right-Option) and the active language's flag
appears (🇬🇧 / 🇺🇦) — that's "listening" and a way to check the language; a
short hold isn't transcribed. Processing shows ⏳. While holding, tap right-Shift
to switch language, Delete to cancel, or R to send the take to Apple Reminders
(📅). A reminder flashes 📅 on success or 🔴 on error.
"""

import os
import sys
import atexit
import signal
import threading

# As a bundled .app there is no terminal, so mirror output to a log file. utf-8
# is required — the bundle's default ascii locale would choke on emoji/Ukrainian.
if not (sys.stdout and sys.stdout.isatty()):
    try:
        logdir = os.path.expanduser("~/Library/Logs")
        os.makedirs(logdir, exist_ok=True)
        sys.stdout = open(f"{logdir}/Dictate.log", "a", buffering=1, encoding="utf-8")
        sys.stderr = open(f"{logdir}/Dictate.err", "a", buffering=1, encoding="utf-8")
    except OSError:
        pass

import rumps
import AppKit
from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
from Quartz import CGPreflightListenEventAccess, CGRequestListenEventAccess

import dictate

FLAGS = {"en": "🇬🇧", "uk": "🇺🇦"}   # change "🇬🇧" to "🇺🇸" if you prefer


def _icon(state):
    """Menu-bar glyph for a pipeline state (blank when idle)."""
    if state == "recording":
        return FLAGS.get(dictate.LANGUAGE, "🏳️")
    if state in ("recording_reminder", "reminder_ok"):
        return "📅"
    if state == "busy":
        return "⏳"
    if state == "error":
        return "🔴"
    return ""


class DictateApp(rumps.App):
    def __init__(self):
        dictate.load_settings()
        super().__init__(_icon("idle"))
        self.state = "idle"
        self._pending_note = None
        self._transient_ticks = 0        # counts a "reminder_ok"/"error" back to idle
        self.menu = [self._language_menu()]

        self._request_permissions()

        # Pipeline callbacks fire on background threads, but AppKit must only be
        # touched on the main thread — so they stash state and a Timer repaints.
        self.core = dictate.Dictation(on_state=self._on_state,
                                      on_language=self._on_language,
                                      on_notify=self._on_notify)
        rumps.Timer(self._refresh, 0.2).start()
        self.listener = self.core.listener()
        self.listener.start()
        threading.Thread(target=dictate.warm_up, daemon=True).start()

        atexit.register(self._cleanup)
        signal.signal(signal.SIGINT, lambda *_: rumps.quit_application())

    @staticmethod
    def _request_permissions():
        """Prompt for the two grants the hotkey needs: Accessibility (to paste)
        and Input Monitoring (to see the key). Both attach to the "Dictate"
        bundle and stick once enabled."""
        if not AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}):
            print("Enable 'Dictate' in Privacy & Security → Accessibility, then relaunch.")
        if not CGPreflightListenEventAccess():
            CGRequestListenEventAccess()
            print("Enable 'Dictate' in Privacy & Security → Input Monitoring, then relaunch.")

    def _language_menu(self):
        menu = rumps.MenuItem("Language")
        self._lang_items = []
        for label, code in dictate.LANGUAGES.items():
            item = rumps.MenuItem(f"{FLAGS.get(code, '')} {label}", callback=self._set_language)
            item.code = code
            menu.add(item)
            self._lang_items.append(item)
        return menu

    def _set_language(self, sender):
        dictate.save_language(sender.code)   # _refresh syncs the checkmarks

    def _on_language(self, code, label):
        self._pending_note = ("Dictate", f"{FLAGS.get(code, '')} {label}")

    def _on_notify(self, title, message):
        self._pending_note = (title, message)

    def _on_state(self, state):
        self.state = state
        self._transient_ticks = 12 if state in ("reminder_ok", "error") else 0

    def _refresh(self, _timer):
        self.title = _icon(self.state)
        if self._transient_ticks:
            self._transient_ticks -= 1
            if not self._transient_ticks:
                self.state = "idle"
        for item in self._lang_items:
            item.state = (item.code == dictate.LANGUAGE)
        if self._pending_note:
            title, message = self._pending_note
            self._pending_note = None
            try:
                rumps.notification(title, "", message)
            except Exception:
                pass

    def _cleanup(self):
        try:
            self.listener.stop()
        except Exception:
            pass
        if self.core.recorder.active:
            self.core.recorder.stop()

    def run(self):
        # Menu-bar only, no Dock icon. The bundle sets LSUIElement; this also
        # covers running `python app.py` directly, which has no Info.plist.
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory)
        super().run()


if __name__ == "__main__":
    DictateApp().run()
