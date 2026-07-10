# WhisperBar 🎙️

**Fully-local, private speech-to-text dictation for macOS.**

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform: macOS](https://img.shields.io/badge/Platform-macOS-lightgrey.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Local & Private](https://img.shields.io/badge/Local%20%26%20Private-no%20cloud-brightgreen.svg)

Press a global hotkey, speak, press it again, and your words are pasted into whatever app you're using — an editor, a browser, Slack, anything. WhisperBar is a lightweight, private alternative to cloud dictation tools. Transcription runs entirely on your machine via [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper). No cloud, no account, no API key — nothing you say ever leaves your Mac.

<!-- TODO: add a screenshot or demo GIF of the menu bar icon in action -->

## Features

- **Local transcription** — audio and transcribed text never leave your Mac; speech-to-text runs entirely on-device with `faster-whisper`. No telemetry, no accounts, nothing sent anywhere. (The Whisper *model* is downloaded once from Hugging Face on first run — see [Installation](#installation) — after which it works fully offline.)
- **Lives in the menu bar** — a small 🎙️ icon, no Dock clutter
- **Global hotkey** — press once to start recording, again to transcribe and paste, from any app
- **Multiple Whisper models** — pick the size/accuracy tradeoff that fits your machine, switchable from the menu
- **Configurable text insertion** — paste (⌘V), simulate typing, or copy-only
- **No telemetry** — WhisperBar doesn't phone home, ever

## How it works

WhisperBar sits in your menu bar as a 🎙️ icon. With the default hotkey **Control+Option+Space**:

- Press it once → 🔴 recording starts
- Press it again → ✍️ audio is transcribed locally, then the text is pasted at your cursor

You can also start/stop dictation from the menu bar without touching the hotkey.

## Requirements

- macOS
- Python 3.9+
- A working microphone

## Installation

```bash
git clone https://github.com/naveen7y/whisperbar.git
cd whisperbar
./setup.sh      # creates a .venv and installs dependencies
./run.sh        # launches the menu bar app
```

`setup.sh` creates a local virtual environment and installs everything in `requirements.txt` (this pulls in `faster-whisper` and its CTranslate2 backend). On first launch, WhisperBar downloads the default model (`small.en`, ~470 MB) and caches it in `~/.cache/huggingface`; subsequent launches are instant. While the model is loading, the menu bar icon shows ⏳.

## Granting macOS permissions

WhisperBar needs a couple of privacy-sensitive permissions to work, all under **System Settings ▸ Privacy & Security**:

| Permission | Why it's needed |
|---|---|
| **Input Monitoring** | to *detect* the global hotkey system-wide, even when WhisperBar isn't the focused app |
| **Accessibility** | to *paste* (or type) the transcribed text into whatever app you're using |
| **Microphone** | to record your voice — macOS will normally prompt for this automatically the first time you start recording |

> **Note:** If you customize the hotkey to a *modifier-only* combo (e.g. `fn+shift`), WhisperBar detects it with a Quartz event tap that relies on **Accessibility** rather than Input Monitoring. With the default hotkey (`ctrl+option+space`), Input Monitoring is what matters. Granting both covers every case.

Grant **Input Monitoring** and **Accessibility** to whichever app actually runs WhisperBar — your **Terminal** (or **iTerm**) if you're running it with `./run.sh`, or **WhisperBar** itself if you've built the standalone `.app` (see below).

**After granting permissions, quit and relaunch WhisperBar.** macOS doesn't always pick up newly granted permissions on a running process. This is the single most common cause of "I press the hotkey and nothing happens" — if your hotkey seems dead, check both Input Monitoring and Accessibility before anything else.

## Usage

1. Make sure the 🎙️ icon is visible in your menu bar (launch with `./run.sh`, or see auto-start below).
2. Press the hotkey (default **Control+Option+Space**) to start recording — the icon turns 🔴.
3. Speak.
4. Press the hotkey again — the icon turns ✍️ while it transcribes, then the text is pasted at your cursor.

You can also click the menu bar icon and choose **Start / Stop Dictation** instead of using the hotkey.

## Configuration

Settings live in `~/.whisperbar/config.json` and are created with sensible defaults on first run. Some are also changeable live from the menu bar (Model, Insert method).

| Key | Description | Default |
|---|---|---|
| `model` | Whisper model to use — see [Models](#models) below | `small.en` |
| `language` | ISO language code (e.g. `en`), or `null` to auto-detect | `en` |
| `hotkey` | Global hotkey combo (see below) | `ctrl+option+space` |
| `insert_method` | How transcribed text is inserted: `paste`, `type`, or `clipboard` | `paste` |
| `device` | Inference device — `cpu` (Apple Silicon has no CUDA) | `cpu` |
| `compute_type` | Inference precision — `int8`, `int8_float16`, `float16`, or `float32` | `int8` |
| `beam_size` | Decoding beam width (1–10). `1` (greedy) is ~1.5× faster with no noticeable accuracy loss for dictation; raise toward `5` for maximum accuracy on harder audio | `1` |
| `cpu_threads` | Inference threads. `0` auto-detects the right number for your CPU (recommended). Pinning a high value can *slow things down* on hybrid performance/efficiency-core chips | `0` |

**`insert_method` options:**
- `paste` — copies the text to the clipboard, then simulates ⌘V (default)
- `type` — simulates individual keystrokes instead of using the clipboard
- `clipboard` — copies the text only; you paste it manually

**`hotkey` format** is forgiving. It's a `+`-separated combo of modifiers and, optionally, a regular key:

- Modifier aliases: `control`/`ctrl`, `option`/`opt`/`alt`, `command`/`cmd`/`meta`/`super`/`win`, `shift`, `fn`/`function`
- Angle brackets are optional — `ctrl+option+space`, `control+option+space`, and `<ctrl>+<alt>+<space>` all mean the same thing
- **Key + modifiers** (e.g. `ctrl+option+space`, `cmd+shift+d`) is handled by [pynput](https://github.com/moses-palmer/pynput)'s global hotkey listener
- **Modifier-only combos** (e.g. `fn+shift`, `ctrl+shift`) have no regular key — hold them together to toggle. These are handled by a low-level Quartz event tap, since the `Fn` key in particular isn't visible to normal key listeners

Edit `hotkey` in `config.json` and relaunch WhisperBar to apply a change.

## Models

Set via `model` in `config.json`, or pick one from the menu bar ▸ Model:

| Model | Size | Notes |
|---|---|---|
| `tiny.en` | ~75 MB | Fastest, English-only, lower accuracy |
| `base.en` | ~145 MB | Fast, English-only |
| `small.en` | ~470 MB | **Default.** Good balance of speed and accuracy for English |
| `medium.en` | ~1.5 GB | Slower, more accurate — a solid alternative for English dictation |
| `large-v3` | ~3 GB | Most accurate, multilingual, but **slow on CPU** (several seconds per utterance) |
| `distil-large-v3` | ~1.5 GB | Distilled large-v3 — **near-large accuracy at roughly 2× the speed** and half the size; a great high-accuracy pick for CPU |

`.en` models are English-only and tend to be faster and more accurate than their multilingual counterparts for English speech. `large-v3` is multilingual and the most accurate overall, but noticeably slower on CPU — expect several seconds of latency per utterance. `distil-large-v3` is a distilled version that keeps most of large-v3's accuracy while running about twice as fast — a good middle ground. For everyday English dictation on CPU, `small.en` (the default) or `medium.en` are recommended.

WhisperBar adapts to the machine it runs on: inference thread count is auto-detected per CPU (`cpu_threads: 0`), models load from the local cache when already downloaded, and greedy decoding (`beam_size: 1`) keeps latency low on slower hardware. Nothing here is tuned to a specific machine.

## Auto-start at login

Pick **one** of the following:

**Option A — Login Items (if you've built the `.app`):**
Build the standalone app (see below), then add `WhisperBar.app` under **System Settings ▸ General ▸ Login Items**.

**Option B — launchd service:**

```bash
./install-service.sh
```

Installs a `launchd` LaunchAgent (`com.whisperbar.app`) that starts WhisperBar at login and restarts it automatically if it ever crashes (a clean Quit from the menu is respected and won't be relaunched). Logs go to `~/.whisperbar/whisperbar.log`. To remove it:

```bash
./uninstall-service.sh
```

Don't run both at once — if you switch from the service to the `.app` (or vice versa), uninstall the other method first so you don't end up with two menu-bar icons.

## Building a standalone .app

```bash
./build-app.sh
```

This uses `py2app` in **alias mode** to build `WhisperBar.app` and installs it to `/Applications`. Building your own app bundle gives WhisperBar its own Microphone/Input Monitoring/Accessibility permission entries (cleaner than granting them to your Terminal) and lets you launch it from Spotlight.

> **Important:** because this is an alias-mode build, the app *links back* to this source folder and its `.venv` rather than bundling them — don't move or delete either. If you relocate the project, re-run `./build-app.sh` to rebuild.

## Troubleshooting

- **Hotkey does nothing** → Check that WhisperBar (or your Terminal/iTerm, if running via `./run.sh`) has **both** Input Monitoring and Accessibility granted under System Settings ▸ Privacy & Security. Then **quit and relaunch** — permission changes don't always apply to an already-running process.
- **Menu bar icon is stuck on ⏳** → It's downloading or loading the model, not frozen. `large-v3` is ~3 GB and can take a while on a slow connection — let it finish rather than force-quitting.
- **You moved or renamed the project folder** → Alias-mode `.app` builds link back to the source folder and `.venv`; re-run `./build-app.sh` after relocating.
- **It records but doesn't paste** → This is almost always missing Accessibility permission. Grant it and relaunch, or set `insert_method` to `clipboard` in `config.json` and paste manually as a workaround.
- **Need logs?** → WhisperBar writes a rotating log to `~/.whisperbar/whisperbar.log` (handy when filing a bug report).

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started.

## Acknowledgements

- [OpenAI Whisper](https://github.com/openai/whisper) — the speech-recognition model and research this is built on.
- [SYSTRAN faster-whisper](https://github.com/SYSTRAN/faster-whisper) and [CTranslate2](https://github.com/OpenNMT/CTranslate2) — the fast, local inference engine.

> WhisperBar is an independent, unofficial project. It is **not affiliated with, endorsed by, or sponsored by OpenAI**. "Whisper" refers to OpenAI's open-source speech-recognition model.

## License

MIT — see [LICENSE](LICENSE). © 2026 Naveen.

Third-party dependency licenses are listed in [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md). Note that **pynput is LGPL-3.0**; this is fine for the normal pip install, but read that file before distributing a bundled `.app`.
