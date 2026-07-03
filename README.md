# local-whisper-macos

Local push-to-talk dictation for Apple Silicon. Hold a key, speak, release — your
speech is transcribed on-device with [MLX-Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper),
tidied up by a local LLM via [Ollama](https://ollama.com), and pasted at the
cursor. Everything runs offline — no cloud, no API keys, no audio leaves the machine.

The cleanup pass fixes grammar and punctuation; say "as a list" and it formats a
markdown list. English and Ukrainian are supported, and a take can go straight to
Apple Reminders instead of the cursor.

## Requirements

- Apple Silicon Mac (built on M4 Pro / 24 GB)
- Python 3.10+
- [Ollama](https://ollama.com) (`brew install ollama`) — the app runs
  `ollama serve` itself if nothing is already listening.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Models (~3 GB total, resumable):
python -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')"
ollama pull gemma3:12b

python dictate.py
```

Hold **right-Option (⌥)**, speak, release. macOS will ask for **Microphone** and
**Accessibility** — grant both, or it records but can't type.

## Usage

While holding the hotkey:

| Gesture | Action |
|---|---|
| speak, release | transcribe → clean → paste |
| release within `MIN_HOLD_SECONDS` | discard (accidental tap / language peek) |
| tap **right-Shift** | switch language (English ⇄ Ukrainian) |
| tap **Delete** | cancel the take |
| tap **R** | send the take to Apple Reminders (due today at noon) |

The mic opens only while you hold the key, so the macOS recording indicator
shows just during dictation.

## Menu-bar app

`python app.py` runs the same pipeline as a menu-bar item — **blank when idle**,
the language flag (🇬🇧 / 🇺🇦) while recording, ⏳ while processing, 📅 for a
reminder, 🔴 on error. Language is also switchable from its **Language** menu and
remembered across restarts (`~/.config/local-whisper-dictate/settings.json`).

### Run at login

`./build_app.sh` packages `app.py` into a menu-bar-only `Dictate.app` (py2app,
alias mode) in `~/Applications`. Because the app's identity is *Dictate*, macOS
attaches the permissions to it and they stick.

1. Launch it once and grant **Microphone**, **Accessibility**, and **Input
   Monitoring** to *Dictate* (Privacy & Security). The first reminder also asks
   to allow controlling **Reminders** (Automation).
2. Add it to **Login Items** (System Settings → General → Login Items).

It's an alias build referencing this repo/venv by path, so re-run `./build_app.sh`
after moving the repo or recreating the venv. Logs: `~/Library/Logs/Dictate.log`.

## Configuration

Constants at the top of `dictate.py`:

| Constant | Default | Notes |
|---|---|---|
| `HOTKEY` | `Key.alt_r` | push-to-talk key |
| `LANG_CYCLE_KEY` | `Key.shift_r` | tap to switch language |
| `CANCEL_KEYCODE` | `51` | Delete: cancel the take |
| `REMINDER_KEYCODE` | `15` | R: send to Reminders |
| `REMINDER_HOUR` | `12` | reminders are due today at this hour (24h) |
| `MIN_HOLD_SECONDS` | `1.5` | shorter holds are discarded |
| `WHISPER_MODEL` | `whisper-large-v3-turbo` | MLX, runs on the GPU |
| `OLLAMA_MODEL` | `gemma3:12b` | cleanup model (non-thinking; avoid "reasoning" models) |
| `OLLAMA_KEEP_ALIVE` | `"30m"` | keep the model warm between utterances |
| `LANGUAGE` | `"en"` | `"en"` or `"uk"` |
| `AUTO_PASTE` | `True` | `False` = copy to clipboard only |

To add languages, edit `LANGUAGES` in `dictate.py` (any
[Whisper code](https://github.com/openai/whisper#available-models-and-languages))
and the matching `FLAGS` in `app.py`.

## License

MIT
