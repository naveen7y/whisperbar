---
name: Bug report
about: Report something that isn't working correctly
title: "[Bug]: "
labels: bug
---

## Before you file

Most WhisperBar issues turn out to be a macOS permission that isn't granted.
Please check both of these under **System Settings ▸ Privacy & Security**
before filing:

- [ ] **Input Monitoring** is enabled for WhisperBar (needed to detect the hotkey)
- [ ] **Accessibility** is enabled for WhisperBar (needed to paste the text)

## Environment

- macOS version: <!-- e.g. Sonoma 14.5 -->
- Python version (`python3 --version`): <!-- e.g. Python 3.11.4 -->
- WhisperBar install method: <!-- setup.sh + run.sh, or built .app bundle -->
- Whisper model in use: <!-- e.g. tiny.en, base.en, small.en, medium.en, large-v3 -->
- Input Monitoring granted? <!-- yes / no -->
- Accessibility granted? <!-- yes / no -->

## Steps to reproduce

1.
2.
3.

## Expected behavior

<!-- What you expected to happen -->

## Actual behavior

<!-- What actually happened -->

## Logs

<!--
Paste any relevant output here. If you ran from source (./run.sh), include the
terminal output. If you're running the built .app, check Console.app for
WhisperBar entries.
-->

```
(paste logs here)
```

## Additional context

<!-- Anything else that might be relevant: config changes, other apps running, etc. -->
