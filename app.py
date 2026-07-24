#!/usr/bin/env python3
"""Menu-bar front-end for the dictate.py pipeline.

Shows the active language's flag (🇬🇧 / 🇺🇦) when idle. Hold the hotkey
(right-Option) to record — 🔴 while recording, 📅 if the take is a reminder.
Takes queue and transcribe sequentially; pending takes show as ⏳N, so you can
keep recording without waiting. Results go to the clipboard. While holding, tap
right-Shift to switch language, Delete to cancel, or R to send the take to
Reminders (a reminder flashes 📅 on success, ⚠️ on error). The menu has Reset
(clear the queue and recover) and Quit.
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
FLASH_TICKS = 12                     # how long a result glyph lingers (~2.4s)


class DictateApp(rumps.App):
    def __init__(self):
        dictate.load_settings()
        super().__init__(FLAGS.get(dictate.LANGUAGE, "🏳️"))
        self._pending_note = None
        self._flash = None            # transient result glyph: 📅 (reminder) / ⚠️ (error)
        self._flash_ticks = 0
        self.menu = [self._language_menu(), rumps.MenuItem("Reset", callback=self._reset)]

        self._request_permissions()

        # Pipeline callbacks fire on background threads, but AppKit must only be
        # touched on the main thread — the Timer repaints from live core state.
        self.core = dictate.Dictation(on_done=self._on_done, on_language=self._on_language)
        rumps.Timer(self._refresh, 0.2).start()
        self.listener = self.core.listener()
        self.listener.start()
        threading.Thread(target=dictate.warm_up, daemon=True).start()

        atexit.register(self._cleanup)
        signal.signal(signal.SIGINT, lambda *_: rumps.quit_application())

    @staticmethod
    def _request_permissions():
        """Prompt for the two grants the hotkey needs: Accessibility (to copy)
        and Input Monitoring (to see the key). Both attach to the "Dictate"
        bundle and stick once enabled."""
        if not AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}):
            print("Enable 'Dictate' in Privacy & Security → Accessibility, then relaunch.")
        if not CGPreflightListenEventAccess():
            CGRequestListenEventAccess()
            print("Enable 'Dictate' in Privacy & Security → Input Monitoring, then relaunch.")

    def _glyph(self):
        """Menu-bar title for the current state (rumps reserves `_icon`)."""
        c = self.core
        if c.recording:
            return "📅" if c.reminder_mode else "🔴"
        if c.pending:
            return f"⏳{c.pending}"
        return self._flash or FLAGS.get(dictate.LANGUAGE, "🏳️")

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

    def _reset(self, _sender):
        self.core.reset()
        self._flash, self._flash_ticks = None, 0

    def _on_done(self, outcome, detail):
        # Worker thread: flash a result glyph and post a notification.
        if outcome == "reminder_ok":
            self._flash, self._flash_ticks = "📅", FLASH_TICKS
            self._pending_note = ("Added to Reminders", detail or "")
        elif outcome == "error":
            self._flash, self._flash_ticks = "⚠️", FLASH_TICKS
            self._pending_note = ("Dictation error", detail or "see the log")

    def _on_language(self, code, label):
        self._pending_note = ("Dictate", f"{FLAGS.get(code, '')} {label}")

    def _refresh(self, _timer):
        self.title = self._glyph()
        if self._flash_ticks:
            self._flash_ticks -= 1
            if not self._flash_ticks:
                self._flash = None
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
        if self.core.recording:
            self.core.recorder.stop()

    def run(self):
        # Menu-bar only, no Dock icon. The bundle sets LSUIElement; this also
        # covers running `python app.py` directly, which has no Info.plist.
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory)
        super().run()


if __name__ == "__main__":
    DictateApp().run()
