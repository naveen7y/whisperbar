# Third-Party Licenses

WhisperBar is released under the [MIT License](LICENSE). It depends on the
open-source packages below. When installed via `./setup.sh`, these are fetched
from PyPI into a local virtualenv — WhisperBar does not redistribute them, and
each package ships its own license text inside its wheel. This file is provided
for transparency and as a checklist should the project ever bundle dependencies.

## Direct dependencies

| Package | License | Notes |
|---|---|---|
| [rumps](https://github.com/jaredks/rumps) | BSD-3-Clause | macOS menu-bar UI |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) | MIT | audio capture; bundles PortAudio (MIT) |
| [numpy](https://github.com/numpy/numpy) | BSD-3-Clause | array handling |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | Whisper transcription |
| [ctranslate2](https://github.com/OpenNMT/CTranslate2) | MIT | inference backend for faster-whisper |
| [onnxruntime](https://github.com/microsoft/onnxruntime) | MIT | transitive, via ctranslate2 |
| [pyobjc-framework-Cocoa](https://github.com/ronaldoussoren/pyobjc) | MIT | macOS bindings |
| [pyobjc-framework-Quartz](https://github.com/ronaldoussoren/pyobjc) | MIT | Quartz event taps |
| **[pynput](https://github.com/moses-palmer/pynput)** | **LGPL-3.0** | global hotkey listener — see note below |

Everything else in the dependency tree resolves to permissive licenses
(MIT / BSD / Apache-2.0 / ISC / MPL-2.0 / Unlicense).

## pynput (LGPL-3.0) — the one copyleft dependency

Using pynput as a normal pip-installed dependency (which is how `./setup.sh`
installs it) places **no obligation** on WhisperBar's own MIT license — this is
ordinary dynamic use via a package manager.

The obligations only change if WhisperBar is ever **redistributed with pynput
bundled inside it** — e.g. a full (non–alias-mode) `py2app` build shipped as a
`.app`/DMG/Homebrew cask. `build-app.sh` uses **alias mode** (`-A`), which does
*not* bundle dependencies, so today's build artifacts contain no LGPL code.

If you distribute a bundled build, LGPL-3.0 requires (see `setup_app.py`):
include pynput's license and copyright notice, keep it dynamically linked (or
supply object files so a user can relink a modified pynput), and provide access
to pynput's source. pynput's source is public on PyPI and GitHub.

## Models

The Whisper models downloaded at runtime (`Systran/faster-whisper-*` on Hugging
Face) are MIT-licensed conversions of OpenAI's MIT-licensed Whisper weights.
WhisperBar downloads them to each user's machine on demand and never
redistributes them, so no additional obligation applies.

## Acknowledgements

- [OpenAI Whisper](https://github.com/openai/whisper) — the speech-recognition model and research.
- [SYSTRAN faster-whisper](https://github.com/SYSTRAN/faster-whisper) + [CTranslate2](https://github.com/OpenNMT/CTranslate2) — the fast local inference engine.
