# local-whisper-macos

Local push-to-talk dictation for Apple Silicon. Hold a key, speak, release —
your speech is transcribed on-device with [MLX-Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper),
cleaned up by a local LLM via [Ollama](https://ollama.com), and pasted at the cursor.

Everything runs offline. No cloud, no API keys, no audio leaves the machine.

The cleanup pass fixes grammar and punctuation, and if you *say* something like
"bullet points" or "as a list", it reformats your statements into a markdown list.

## Requirements

- Apple Silicon Mac (built and tested on M4 Pro / 24 GB)
- Python 3.10+
- [Ollama](https://ollama.com) installed — the cleanup pass talks to a local
  Ollama server. You don't need to start it yourself: on launch the app runs
  `ollama serve` (headless, no menu-bar icon) if nothing is already listening.
  The CLI (`brew install ollama`) is enough; the GUI app/cask isn't required.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Pull both models up front (~3 GB total). Both downloads are resumable —
# if your connection drops, just re-run the command to continue.
python -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')"  # Whisper (~1.5 GB)
ollama pull gemma3:12b                                                                                               # cleanup model (~1.5 GB)

python dictate.py
```

Hold **right-Option (⌥)**, speak, release.

macOS will ask for **Microphone** and **Accessibility** permissions
(System Settings → Privacy & Security). Accessibility is what lets it paste
at the cursor — grant both or it records but can't type.

The mic only opens **while you hold the key**, so the macOS recording
indicator appears just during dictation (not the whole session). That orange
dot can't be hidden while the mic is live — it's enforced by the OS.

## Menu-bar app

Prefer a menu-bar icon over a terminal window? Run `app.py` instead — same
pipeline, wrapped in a 🎙️ menu-bar item (🔴 while recording, ⏳ while
processing) with a **Quit** menu.

```bash
python app.py
```

It reuses everything from `dictate.py`, so all the configuration below still
applies (and it starts Ollama for you). To run it at login as a menu-bar-only
app, see [Run at login](#run-at-login-recommended) below.

## Configuration

All knobs are constants at the top of `dictate.py`:

| Constant | Default | Notes |
|---|---|---|
| `HOTKEY` | `Key.alt_r` | push-to-talk key (hold to dictate) |
| `LANG_CYCLE_KEY` | `Key.shift_r` | tap while holding `HOTKEY` to cycle language |
| `WHISPER_MODEL` | `whisper-large-v3-turbo` | MLX, runs on the GPU |
| `OLLAMA_MODEL` | `gemma3:12b` | cleanup model |
| `LANGUAGE` | `"en"` | spoken language; see [Language](#language) |
| `AUTO_PASTE` | `True` | `False` = copy to clipboard only |
| `CLEANUP_PROMPT` | — | edit to change cleanup behavior |

### Language

Whisper transcribes in whatever language `LANGUAGE` is set to. Built-in choices
are **English** (`"en"`), **Ukrainian** (`"uk"`), and **Auto-detect** (`None` —
handy if you switch languages mid-session, a touch less accurate on very short
clips). Any [Whisper language code](https://github.com/openai/whisper#available-models-and-languages)
works if you set it by hand. The cleanup pass replies in the same language and
never translates.

Switch language **without reaching for the menu**: hold the push-to-talk key and
tap **right-Shift** (`HOTKEY` + `LANG_CYCLE_KEY`) to cycle
English → Ukrainian → Auto-detect. That take is discarded (not transcribed), and
the menu-bar app shows a notification with the new language. Or pick it from the
**Language** submenu (🎙️ icon → Language). Either way the choice is remembered
across restarts in `~/.config/local-whisper-dictate/settings.json`, and the
terminal `dictate.py` honours the same saved choice.

### Choosing a cleanup model

The cleanup task is simple instruction-following, so size has diminishing
returns past ~12B, and **reasoning/"thinking" models are the wrong tool**
(they add seconds of latency to every utterance). Good picks:

- `gemma3:12b` — default; cleanest prose at this size, non-thinking, fast.
- `qwen3:8b` — leaner alternative if you want lower latency.

Both fit alongside Whisper on 24 GB with headroom.

## Run at login (recommended)

`build_app.sh` packages `app.py` into a **menu-bar-only** `Dictate.app` (via
[py2app](https://py2app.readthedocs.io) in *alias* mode) and installs it to
`~/Applications`. This is the recommended way to run it at login:

- The app's identity is **"Dictate"**, so macOS attributes **Microphone** and
  **Accessibility** to *Dictate* and the grants **stick**. A thin shell wrapper
  runs *as Homebrew's Python*, so those permissions attach to "Python", are
  fragile, and the hotkey silently fails — this is the whole reason to bundle.
- `LSUIElement` keeps it **menu-bar only** — no Dock icon, hidden from Cmd-Tab.
- **Alias mode** means the bundle *references* your venv and source rather than
  copying mlx/torch/etc., so it's small and edits to `app.py` / `dictate.py`
  take effect **without rebuilding**.

```bash
./build_app.sh        # builds + installs ~/Applications/Dictate.app
```

It installs `py2app` into your venv on first run (build-only; not needed to run
the terminal `dictate.py`). Then:

1. **Launch once** (Spotlight → "Dictate", or double-click it in
   `~/Applications`) and approve **Microphone** (prompted on first record) and
   **Accessibility** in System Settings → Privacy & Security → Accessibility
   (enable `Dictate`). Without Accessibility it records but can't type.
2. **Add to Login Items:** System Settings → General → Login Items → **+** →
   pick `Dictate`.

Logs go to `~/Library/Logs/Dictate.{log,err}`. Because it's an *alias* build the
bundle references this repo and venv by path — **re-run `./build_app.sh` after
moving the repo or recreating the venv**.

> **Avoid the raw launchd agent for this.** `com.github.USER.dictate.plist` is
> still here as a template, but a launchd-spawned `python` runs as "Python", so
> Accessibility doesn't stick (you'll see `This process is not trusted!` in the
> log and the hotkey won't work). If you do use it, set `KeepAlive` →
> `SuccessfulExit=false` (as the template now does) so quitting from the menu
> stays quit instead of respawning, and `launchctl unload …` to stop it.

## License

MIT
