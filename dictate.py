#!/usr/bin/env python3
"""Local push-to-talk dictation: MLX-Whisper -> Ollama cleanup -> paste at cursor."""

import os
import sys
import time
import json
import queue
import shutil
import threading
import subprocess
import urllib.request
from pathlib import Path

import numpy as np
import sounddevice as sd
import pyperclip
import mlx_whisper
import ollama
from pynput import keyboard

HOTKEY = keyboard.Key.alt_r
# Hold HOTKEY and tap this to cycle through LANGUAGES (the in-progress take is
# discarded, not transcribed). Right-Option + right-Shift by default.
LANG_CYCLE_KEY = keyboard.Key.shift_r
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
OLLAMA_MODEL = "gemma3:12b"
OLLAMA_HOST = "http://127.0.0.1:11434"
SAMPLE_RATE = 16_000
MIN_SECONDS = 0.3
AUTO_PASTE = True

# Spoken language for Whisper. `None` = auto-detect (handy if you switch
# languages mid-session, slightly less accurate on very short clips); a code
# like "en" or "uk" pins it. The menu-bar app (app.py) can change this live,
# and the choice is remembered across restarts in SETTINGS_FILE.
LANGUAGE = "en"
LANGUAGES = {            # menu label -> Whisper code (None = auto-detect)
    "English": "en",
    "Ukrainian": "uk",
    "Auto-detect": None,
}
SETTINGS_FILE = Path.home() / ".config" / "local-whisper-dictate" / "settings.json"


def load_settings():
    """Restore the saved language choice into LANGUAGE (no-op if none saved)."""
    global LANGUAGE
    try:
        LANGUAGE = json.loads(SETTINGS_FILE.read_text()).get("language", LANGUAGE)
    except Exception:
        pass
    return LANGUAGE


def save_language(code):
    """Set the active language and persist it for the next launch."""
    global LANGUAGE
    LANGUAGE = code
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps({"language": code}))
    except Exception as e:
        print(f"  [warn] couldn't save language: {e}", file=sys.stderr)

CLEANUP_PROMPT = """You are a transcription cleanup tool. You receive raw \
speech-to-text and return a polished version.

- Fix grammar, punctuation, capitalization, and obvious transcription errors.
- Never add, drop, or reinterpret meaning. Clean only what was said.
- Always respond in the same language as the input. Never translate.
- Remove filler words and false starts.
- If the speaker asks for a list ("bullet points", "as a list", "list these", \
"списком", "по пунктах"), reformat the relevant statements as a markdown \
bullet list and remove the instruction itself from the output.
- Otherwise return clean prose.

Output only the cleaned text: no preamble, no explanation, no quotes."""


class Recorder:
    """Opens the mic only while a key is held, so macOS shows the recording
    indicator during dictation instead of for the whole session."""

    def __init__(self):
        self.frames: "queue.Queue[np.ndarray]" = queue.Queue()
        self.stream = None

    @property
    def active(self) -> bool:
        return self.stream is not None

    def _capture(self, indata, frames, time_info, status):
        if status:
            print(f"  [audio] {status}", file=sys.stderr)
        self.frames.put(indata.copy())

    def start(self):
        with self.frames.mutex:
            self.frames.queue.clear()
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._capture,
        )
        self.stream.start()

    def stop(self) -> np.ndarray:
        stream, self.stream = self.stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        chunks = []
        while not self.frames.empty():
            chunks.append(self.frames.get())
        if not chunks:
            return np.empty(0, dtype=np.float32)
        return np.concatenate(chunks).flatten().astype(np.float32)


def transcribe(audio: np.ndarray) -> str:
    result = mlx_whisper.transcribe(audio, path_or_hf_repo=WHISPER_MODEL, language=LANGUAGE)
    return result["text"].strip()


def clean_up(text: str) -> str:
    reply = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": CLEANUP_PROMPT},
            {"role": "user", "content": text},
        ],
        options={"temperature": 0.1},
    )
    return reply["message"]["content"].strip()


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen(OLLAMA_HOST, timeout=1)
        return True
    except Exception:
        return False


def _ollama_bin():
    """Locate the `ollama` CLI, incl. Homebrew paths missing from launchd PATH."""
    return shutil.which("ollama") or next(
        (p for p in ("/opt/homebrew/bin/ollama", "/usr/local/bin/ollama")
         if os.path.exists(p)),
        None,
    )


def ensure_ollama(timeout: float = 30) -> bool:
    """Make sure the Ollama server is reachable, starting `ollama serve` if not.

    Uses the headless CLI server (no menu-bar app) and only starts it when
    nothing is already listening, so it won't clash with a running instance.
    """
    if _ollama_up():
        return True
    binary = _ollama_bin()
    if binary:
        subprocess.Popen(
            [binary, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # detach so it outlives app restarts
        )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _ollama_up():
            return True
        time.sleep(0.5)
    return False


def paste(text: str):
    pyperclip.copy(text)
    if not AUTO_PASTE:
        return
    kb = keyboard.Controller()
    time.sleep(0.05)
    with kb.pressed(keyboard.Key.cmd):
        kb.tap("v")


def run_pipeline(audio: np.ndarray):
    if audio.size < SAMPLE_RATE * MIN_SECONDS:
        print("  (too short, skipped)\n")
        return
    started = time.time()
    heard = transcribe(audio)
    if not heard:
        print("  (no speech detected)\n")
        return
    print(f"  heard:   {heard}")
    cleaned = clean_up(heard)
    print(f"  cleaned: {cleaned}")
    paste(cleaned)
    print(f"  -> {'pasted' if AUTO_PASTE else 'copied'}  ({time.time() - started:.1f}s)\n")


class Dictation:
    """Wires the hotkey to record -> transcribe -> clean -> paste.

    `on_state` is called with "recording" / "busy" / "idle" so a UI (e.g. the
    menu-bar app) can reflect status; it defaults to a no-op for terminal use.
    """

    def __init__(self, on_state=None, on_language=None):
        self.recorder = Recorder()
        self.busy = threading.Lock()
        self.on_state = on_state or (lambda state: None)
        self.on_language = on_language or (lambda code, label: None)

    def on_press(self, key):
        if key == LANG_CYCLE_KEY and self.recorder.active:
            self.recorder.stop()            # drop the in-progress take
            self.on_state("idle")
            self._cycle_language()
            return
        if key == HOTKEY and not self.recorder.active:
            self.recorder.start()
            self.on_state("recording")
            print("● recording…")

    def _cycle_language(self):
        labels = list(LANGUAGES)
        i = labels.index(next(l for l in labels if LANGUAGES[l] == LANGUAGE)) \
            if LANGUAGE in LANGUAGES.values() else -1
        label = labels[(i + 1) % len(labels)]
        save_language(LANGUAGES[label])
        print(f"  language → {label} ({LANGUAGES[label] or 'auto-detect'})")
        self.on_language(LANGUAGES[label], label)

    def on_release(self, key):
        if key != HOTKEY or not self.recorder.active:
            return
        audio = self.recorder.stop()
        self.on_state("busy")
        print("◌ processing…")
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio: np.ndarray):
        if not self.busy.acquire(blocking=False):
            return  # drop overlapping utterances instead of queueing them
        try:
            run_pipeline(audio)
        except Exception as e:
            print(f"  [error] {e}\n", file=sys.stderr)
        finally:
            self.busy.release()
            self.on_state("idle")

    def listener(self) -> keyboard.Listener:
        return keyboard.Listener(on_press=self.on_press, on_release=self.on_release)

    def run(self):
        load_settings()
        print(f"Whisper: {WHISPER_MODEL}  ({LANGUAGE or 'auto-detect'})")
        print(f"Cleanup: {OLLAMA_MODEL}")
        if not ensure_ollama():
            print("  [warn] Ollama not reachable — cleanup will fail until it starts.",
                  file=sys.stderr)
        print(f"Hold {HOTKEY} to dictate. Ctrl-C to quit.\n")
        with self.listener() as listener:
            try:
                listener.join()
            except KeyboardInterrupt:
                print("\nbye.")


def main():
    Dictation().run()


if __name__ == "__main__":
    main()
