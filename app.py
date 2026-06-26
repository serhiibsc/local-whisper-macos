#!/usr/bin/env python3
"""Menu-bar dictation app: a rumps wrapper around the dictate.py pipeline.

    python app.py

Puts a 🎙️ icon in the menu bar. Hold the hotkey (right-Option by default)
to dictate; the icon reflects recording / processing state. Quit from the menu
(or Ctrl-C if launched from a terminal).
"""

import os
import sys
import atexit
import signal
import threading

# Launched as a .app there's no terminal, so send output to a log file — a place
# to look when something misbehaves. ~/Library/Logs is the user-owned macOS spot.
try:
    _interactive = sys.stdout is not None and sys.stdout.isatty()
except Exception:
    _interactive = False
if not _interactive:
    try:
        _logdir = os.path.expanduser("~/Library/Logs")
        os.makedirs(_logdir, exist_ok=True)
        # utf-8 is essential: we log emojis, em-dashes, and Ukrainian transcripts;
        # the bundle's default ascii locale would raise UnicodeEncodeError.
        sys.stdout = open(os.path.join(_logdir, "Dictate.log"), "a",
                          buffering=1, encoding="utf-8")
        sys.stderr = open(os.path.join(_logdir, "Dictate.err"), "a",
                          buffering=1, encoding="utf-8")
    except OSError:
        pass

import rumps
import AppKit
from ApplicationServices import (
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)
from Quartz import (
    CGPreflightListenEventAccess,
    CGRequestListenEventAccess,
)

import dictate

ICONS = {"idle": "🎙️", "recording": "🔴", "busy": "⏳"}


class DictateApp(rumps.App):
    def __init__(self):
        super().__init__(ICONS["idle"])
        self.state = "idle"
        self._pending_note = None
        self.status_item = rumps.MenuItem("Status: idle")
        self.menu = [self.status_item, None, self._language_menu()]

        # Ask for Accessibility up front: this adds the app to System Settings →
        # Privacy & Security → Accessibility and shows the prompt. Without it
        # pynput can't see the hotkey and can't paste. As a real "Dictate"
        # bundle the grant attaches to this app and sticks across restarts.
        if not AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}):
            print("Accessibility not granted yet — enable 'Dictate' in System "
                  "Settings → Privacy & Security → Accessibility, then relaunch.",
                  flush=True)

        # Input Monitoring is a SEPARATE permission from Accessibility: it's what
        # lets pynput *see* the global hotkey (Accessibility only covers pasting).
        # Without it the listener gets no key events and nothing happens.
        if not CGPreflightListenEventAccess():
            CGRequestListenEventAccess()  # adds Dictate to the list + prompts
            print("Input Monitoring not granted yet — enable 'Dictate' in System "
                  "Settings → Privacy & Security → Input Monitoring, then relaunch.",
                  flush=True)

        # The pipeline fires callbacks on pynput / worker threads, but AppKit
        # must only be touched on the main thread. So the callbacks just stash
        # state, and a Timer (which runs on the main thread) repaints — the
        # same 0.2s tick also lets Python notice Ctrl-C during the Cocoa loop.
        self.core = dictate.Dictation(on_state=self._on_state,
                                      on_language=self._on_language)
        rumps.Timer(self._refresh, 0.2).start()
        self.listener = self.core.listener()
        self.listener.start()

        # Start Ollama in the background so the menu bar appears immediately.
        threading.Thread(target=dictate.ensure_ollama, daemon=True).start()

        # Quit cleanly however we're stopped: Quit menu, Ctrl-C, or otherwise.
        atexit.register(self._cleanup)
        signal.signal(signal.SIGINT, lambda *_: rumps.quit_application())

    def _language_menu(self):
        """A 'Language' submenu with a checkmark on the active language."""
        dictate.load_settings()
        menu = rumps.MenuItem("Language")
        self._lang_items = []
        for label, code in dictate.LANGUAGES.items():
            item = rumps.MenuItem(label, callback=self._set_language)
            item.state = (code == dictate.LANGUAGE)
            menu.add(item)
            self._lang_items.append(item)
        return menu

    def _set_language(self, sender):
        # Menu click; _refresh syncs the checkmarks (keeps one source of truth
        # so the right-Option+right-Shift hotkey path stays consistent too).
        dictate.save_language(dictate.LANGUAGES[sender.title])

    def _on_language(self, code, label):
        # Fired from the listener thread (hotkey cycle); _refresh, on the main
        # thread, picks this up and shows the notification.
        self._pending_note = label

    def _on_state(self, state):
        self.state = state

    def _refresh(self, _timer):
        self.title = ICONS[self.state]
        self.status_item.title = f"Status: {self.state}"
        for item in self._lang_items:
            item.state = (dictate.LANGUAGES[item.title] == dictate.LANGUAGE)
        if self._pending_note is not None:
            label, self._pending_note = self._pending_note, None
            try:
                rumps.notification("Dictate", "Language", f"Switched to {label}")
            except Exception:
                pass

    def _cleanup(self):
        try:
            self.listener.stop()
        except Exception:
            pass
        if self.core.recorder.stream is not None:
            self.core.recorder.stop()

    def run(self):
        # Menu-bar only: no Dock icon, hidden from Cmd-Tab. Set before rumps
        # builds the status bar (its LSUIElement on the bundle doesn't apply —
        # we exec into Homebrew's Python.app, whose Info.plist would win).
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory)
        super().run()


if __name__ == "__main__":
    DictateApp().run()
