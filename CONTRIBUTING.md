# Contributing to WhisperBar

Thanks for your interest in improving WhisperBar. It's a small, focused menu-bar
app, and contributions of all sizes are welcome — bug fixes, permission-handling
improvements, new hotkey options, docs fixes, whatever.

## Before you start

**macOS is required for development.** WhisperBar leans directly on macOS APIs
(Quartz event taps for the global hotkey, Accessibility for pasting), so there's
no way to build or test it on Linux/Windows, even in a VM.

## Getting set up

```bash
git clone https://github.com/naveen7y/whisperbar.git
cd whisperbar
./setup.sh   # creates .venv and installs requirements.txt
./run.sh     # launches the app from source
```

On first launch, macOS will prompt for two permissions — grant both, or the app
won't work at all:

- **Input Monitoring** (System Settings ▸ Privacy & Security ▸ Input Monitoring)
  — needed to detect the global hotkey.
- **Accessibility** (System Settings ▸ Privacy & Security ▸ Accessibility) —
  needed to paste the transcribed text at your cursor.

If you grant these to your terminal or IDE while running from source, and later
grant them again to the built `.app`, that's expected — macOS tracks permissions
per executable.

## How the code is organized

Almost everything lives in `whisperbar.py`, organized top-to-bottom into
sections (look for the `# ---` banners):

- **Config** — loading/saving `~/.whisperbar/config.json`.
- **Hotkey parsing** — turning the config's hotkey string into pynput/Quartz
  primitives.
- **Clipboard / text insertion helpers** — how transcribed text gets pasted.
- **Audio recorder** — `sounddevice`-based mic capture.
- **Modifier-combo global hotkey** — the `CGEventTap`-based listener that
  detects modifier-only combos (like Fn) that pynput can't see on its own.
- **Menu bar app** — the `rumps.App` subclass that ties it all together:
  menu state, transcription (via `faster-whisper`), and the app lifecycle.

If you're fixing a bug, it's usually fastest to `grep` for the relevant menu
label or config key and follow the flow from there — the file is small enough
(~500 lines) to read end-to-end if needed.

## Coding style

The existing code is a clean, fairly plain PEP 8 style: small functions, plain
control flow, comments used sparingly and mostly to explain *why* (especially
around the macOS-specific quirks). When adding to it:

- Keep functions small and single-purpose, matching what's already there.
- Match the existing section-banner style if you're adding a new logical
  section.
- [`ruff`](https://docs.astral.sh/ruff/) is a good fit for this codebase if you
  want to lint locally, but it's optional — there's no enforced CI lint step
  today.

## Testing your changes

**Automated tests.** The pure logic (config sanitization, hotkey parsing) has a
small unit-test suite using the standard library — no extra dependencies. Run it
from the repo root inside the virtualenv:

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

Please add or update tests when you change that logic.

**Manual testing.** Most of the surface area is macOS system integration
(microphone, global hotkey, pasting) that can't be unit-tested meaningfully, so
also verify by hand:

1. Make sure Input Monitoring and Accessibility permissions are granted.
2. Run `./run.sh` and confirm the app launches and the menu bar icon appears.
3. Exercise the hotkey: press it, speak, press it again, and confirm the text
   gets pasted wherever your cursor is (try a couple of different apps —
   pasting behavior can vary).
4. If you touched config handling, delete or edit `~/.whisperbar/config.json`
   and confirm the app still starts cleanly with sane defaults.
5. If you touched model loading, be patient the first time — larger models
   (e.g. `large-v3`) are multi-gigabyte downloads and can look "stuck" while
   they fetch.

## Branching and PRs

- Branch off `main`, use a short descriptive branch name.
- Keep PRs focused — one change per PR is easier to review and revert if
  needed.
- In the PR description, say what macOS version you tested on (see the PR
  template) — this matters a lot given how permission-sensitive the app is.
- Reference any related issue in the PR description.

If you're planning something larger (a new feature, a UI change), it's worth
opening an issue first to discuss the approach before investing a lot of time.

## Reporting bugs / requesting features

Please use the issue templates — for bugs, the permissions section is not
optional filler. Input Monitoring and Accessibility misconfiguration is the
cause of the vast majority of reported issues, so confirming both are granted
before filing (or noting that you checked) saves everyone time.
