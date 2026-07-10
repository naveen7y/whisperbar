"""
py2app build script for WhisperBar.

Build a macOS .app bundle so WhisperBar launches from Spotlight/Applications
and gets its OWN Microphone + Accessibility permission entries.

Usage (handled for you by ./build-app.sh):
    python setup_app.py py2app -A     # alias mode (recommended, fast)
    python setup_app.py py2app        # full standalone bundle

Alias mode links back to this source directory and the .venv site-packages,
which sidesteps the pain of bundling ctranslate2 / onnxruntime native
libraries. The trade-off: the .app must stay on this machine and the source
folder + .venv must not be moved. That's exactly what we want for personal use.

LICENSING NOTE: pynput is LGPLv3 (the only copyleft dependency). Alias-mode
builds do NOT copy it into the .app, so there is no bundling/redistribution
obligation today. If you ever switch to a full standalone build (drop `-A`)
AND redistribute the resulting .app (Releases, a DMG, Homebrew, etc.), LGPL
compliance must be handled first: include pynput's license + copyright notice,
ensure it's dynamically linked (or provide object files so users can relink),
and offer its source. See THIRD-PARTY-LICENSES.md before redistributing bundles.
"""

from setuptools import setup

APP = ["whisperbar.py"]

OPTIONS = {
    "argv_emulation": False,  # True needs Carbon and breaks on modern macOS
    "plist": {
        "CFBundleName": "WhisperBar",
        "CFBundleDisplayName": "WhisperBar",
        "CFBundleIdentifier": "com.whisperbar.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0",
        # Menu-bar-only: no Dock icon, no app-switcher entry.
        "LSUIElement": True,
        # Shown in the macOS permission prompt for the microphone.
        "NSMicrophoneUsageDescription": (
            "WhisperBar records your voice so it can transcribe it to text "
            "locally on your Mac."
        ),
    },
    # Help py2app find the runtime deps in alias mode.
    "packages": ["rumps", "faster_whisper", "sounddevice", "pynput", "numpy"],
}

setup(
    name="WhisperBar",
    app=APP,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
