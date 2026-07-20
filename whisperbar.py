#!/usr/bin/env python3
"""
WhisperBar — a fully-local, system-wide speech-to-text dictation tool for macOS.

Press a global hotkey (default ⌃⌥Space), speak, press it again, and the
transcribed text is pasted into whatever app you're using. All transcription
runs locally on your machine via faster-whisper — nothing is sent anywhere.

Lives in the menu bar. No cloud, no account, no API key.
"""

import json
import logging
import os
import queue
import subprocess
import threading
import time
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path

import numpy as np
import rumps
import sounddevice as sd
from pynput import keyboard

APP_NAME = "WhisperBar"
CONFIG_DIR = Path.home() / ".whisperbar"
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = CONFIG_DIR / "whisperbar.log"
SAMPLE_RATE = 16000  # Whisper expects 16 kHz mono
MAX_RECORDING_SECONDS = 300  # safety cap: auto-stop a forgotten recording

log = logging.getLogger("whisperbar")


def setup_logging():
    """Send logs to a rotating file in ~/.whisperbar plus stderr.

    Called once from main() — importing this module (e.g. from tests) must NOT
    create files or configure handlers as a side effect. Safe to call twice.
    """
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
        fh.setFormatter(fmt)
        log.addHandler(fh)
    except Exception:  # noqa: BLE001 — never let logging setup crash startup
        pass
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)


DEFAULT_CONFIG = {
    "model": "small.en",        # tiny.en | base.en | small.en | medium.en | large-v3
    "language": "en",           # ISO code, or null for auto-detect
    # Hotkey is a "+"-separated combo. Modifier names are forgiving:
    #   control/ctrl, option/alt, command/cmd, shift, fn
    # plus an optional regular key (space, enter, a, f5, ...). Angle brackets
    # are optional, so all of these mean the same thing:
    #   "ctrl+option+space"  "control+option+space"  "<ctrl>+<alt>+<space>"
    # A modifier-only combo (e.g. "fn+shift") uses a Quartz tap; a combo with
    # a real key uses pynput's global hotkeys.
    "hotkey": "ctrl+option+space",
    "insert_method": "paste",   # paste | type | clipboard
    "device": "cpu",            # cpu (Apple Silicon has no CUDA)
    "compute_type": "int8",     # int8 is fast + low-memory on CPU
    # Decoding beam width. 1 (greedy) is ~1.4-1.5x faster than 5 with no
    # noticeable accuracy loss for short dictation; raise toward 5 if you
    # want maximum accuracy on longer/harder audio.
    "beam_size": 1,
    # CPU threads for inference. 0 lets CTranslate2 auto-detect the right
    # number for the current machine (recommended, and portable across Macs).
    # Pinning a high value can *hurt* on hybrid P/E-core CPUs — leave at 0
    # unless you have measured a specific machine.
    "cpu_threads": 0,
}

# Modifier aliases → canonical name.
MOD_ALIASES = {
    "control": "ctrl", "ctrl": "ctrl",
    "option": "alt", "opt": "alt", "alt": "alt",
    "command": "cmd", "cmd": "cmd", "meta": "cmd", "super": "cmd", "win": "cmd",
    "shift": "shift",
    "fn": "fn", "function": "fn",
}

# Regular-key aliases → pynput key name.
KEY_ALIASES = {"return": "enter", "escape": "esc", "del": "delete",
               "pageup": "page_up", "pagedown": "page_down"}

# Keys that pynput expects inside <...> (named keys, not literal characters).
SPECIAL_KEYS = {
    "space", "enter", "tab", "esc", "backspace", "delete", "up", "down",
    "left", "right", "home", "end", "page_up", "page_down", "caps_lock",
    "insert", "menu", "num_lock", "print_screen", "scroll_lock", "pause",
} | {f"f{i}" for i in range(1, 21)}

# Nice display names for the menu.
DISPLAY_NAMES = {"ctrl": "Control", "alt": "Option", "cmd": "Command",
                 "shift": "Shift", "fn": "Fn"}

MODEL_CHOICES = ["tiny.en", "base.en", "small.en", "medium.en",
                 "large-v3", "distil-large-v3"]

# Allowlists for values that flow into the faster-whisper backend. A model name
# is passed to WhisperModel(), where an arbitrary path or Hugging Face repo id
# would cause it to load/download that instead — so we constrain config.json
# (which a user could hand-edit) to known-good values and fall back otherwise.
VALID_DEVICES = ["cpu", "cuda", "auto"]
VALID_COMPUTE_TYPES = [
    "int8", "int8_float16", "int8_float32", "int16",
    "float16", "bfloat16", "float32",
]

# Menu-bar glyphs per state
ICONS = {
    "idle": "🎙️",
    "loading": "⏳",
    "recording": "🔴",
    "transcribing": "✍️",
    "error": "⚠️",
}


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        if CONFIG_PATH.exists():
            cfg.update(json.loads(CONFIG_PATH.read_text()))
    except Exception as exc:  # noqa: BLE001
        log.warning(f"[config] failed to load, using defaults: {exc}")
    return _sanitize_config(cfg)


def _sanitize_config(cfg):
    """Constrain backend-facing values to allowlists, falling back to defaults.

    Prevents a hand-edited config.json from redirecting the model loader to an
    arbitrary path/repo or handing junk to CTranslate2. UI-driven changes only
    ever write known-good values, so this is defense-in-depth.
    """
    for key, allowed in (
        ("model", MODEL_CHOICES),
        ("device", VALID_DEVICES),
        ("compute_type", VALID_COMPUTE_TYPES),
        ("insert_method", ["paste", "type", "clipboard"]),
    ):
        if cfg.get(key) not in allowed:
            log.warning(f"[config] invalid {key}={cfg.get(key)!r}; using "
                        f"{DEFAULT_CONFIG[key]!r}")
            cfg[key] = DEFAULT_CONFIG[key]
    # beam_size: a small positive int.
    if (not isinstance(cfg.get("beam_size"), int) or isinstance(cfg["beam_size"], bool)
            or not 1 <= cfg["beam_size"] <= 10):
        log.warning(f"[config] invalid beam_size={cfg.get('beam_size')!r}; using "
                    f"{DEFAULT_CONFIG['beam_size']}")
        cfg["beam_size"] = DEFAULT_CONFIG["beam_size"]
    # cpu_threads: non-negative int (0 = auto-detect).
    if (not isinstance(cfg.get("cpu_threads"), int) or isinstance(cfg["cpu_threads"], bool)
            or cfg["cpu_threads"] < 0):
        log.warning(f"[config] invalid cpu_threads={cfg.get('cpu_threads')!r}; using "
                    f"{DEFAULT_CONFIG['cpu_threads']}")
        cfg["cpu_threads"] = DEFAULT_CONFIG["cpu_threads"]
    return cfg


# --------------------------------------------------------------------------- #
# Hotkey parsing
# --------------------------------------------------------------------------- #
def parse_hotkey(hk):
    """Return (modifiers, key) from a combo string.

    modifiers: list of canonical names in {ctrl, alt, cmd, shift, fn}
    key:       canonical pynput key name, or None for a modifier-only combo.
    Accepts angle brackets and aliases (option->alt, control->ctrl, ...).
    """
    mods, key = [], None
    for raw in hk.split("+"):
        tok = raw.strip().strip("<>").strip().lower()
        if not tok:
            continue
        if tok in MOD_ALIASES:
            canon = MOD_ALIASES[tok]
            if canon not in mods:
                mods.append(canon)
        else:
            key = KEY_ALIASES.get(tok, tok)
    return mods, key


def build_pynput_combo(mods, key):
    """Build a pynput GlobalHotKeys string, e.g. '<ctrl>+<alt>+<space>'."""
    parts = [f"<{m}>" for m in mods]
    parts.append(f"<{key}>" if key in SPECIAL_KEYS else key)
    return "+".join(parts)


def hotkey_label(hk):
    """Human-readable label, e.g. 'ctrl+option+space' -> 'Control + Option + Space'."""
    mods, key = parse_hotkey(hk)
    parts = [DISPLAY_NAMES.get(m, m.capitalize()) for m in mods]
    if key:
        parts.append(key.replace("_", " ").title())
    return " + ".join(parts) if parts else hk


def save_config(cfg):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except Exception as exc:  # noqa: BLE001
        log.error(f"[config] failed to save: {exc}")


# --------------------------------------------------------------------------- #
# Transcript history
# --------------------------------------------------------------------------- #
def preview_label(text, limit=40):
    """Single-line, length-capped label for menus/status (… if truncated)."""
    text = " ".join(text.split())  # collapse newlines / runs of whitespace
    return text if len(text) <= limit else text[: limit - 1] + "…"


class TranscriptHistory:
    """The last N successful transcriptions, in memory only.

    Thread-safe: the writer is a background transcription thread and the reader
    is the main (UI) thread. Never persisted — cleared when the app quits, which
    keeps WhisperBar's "leaves no trace" promise intact.
    """

    def __init__(self, maxlen=3):
        self._items = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, text):
        with self._lock:
            self._items.append(text)

    def recent(self):
        """Full transcripts, newest first."""
        with self._lock:
            return list(reversed(self._items))


# --------------------------------------------------------------------------- #
# Clipboard / text insertion helpers
# --------------------------------------------------------------------------- #
def set_clipboard(text: str):
    """Put text on the macOS clipboard via pbcopy."""
    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    p.communicate(text.encode("utf-8"))


_kbd = keyboard.Controller()


def paste_from_clipboard():
    """Simulate ⌘V to paste clipboard contents into the focused app."""
    _kbd.press(keyboard.Key.cmd)
    _kbd.press("v")
    _kbd.release("v")
    _kbd.release(keyboard.Key.cmd)


def insert_text(text: str, method: str):
    text = text.strip()
    if not text:
        return
    if method == "type":
        _kbd.type(text)
    elif method == "clipboard":
        set_clipboard(text)  # copy only, user pastes manually
    else:  # paste (default)
        set_clipboard(text)
        time.sleep(0.5)
        paste_from_clipboard()


# --------------------------------------------------------------------------- #
# Audio recorder
# --------------------------------------------------------------------------- #
class Recorder:
    def __init__(self):
        self._frames = []
        self._lock = threading.Lock()
        self._stream = None

    def _callback(self, indata, frames, time_info, status):  # noqa: D401
        if status:
            log.warning(f"[audio] {status}")
        with self._lock:
            self._frames.append(indata.copy())

    def start(self):
        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            if not self._frames:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._frames, axis=0).flatten()
            self._frames = []
        return audio


# --------------------------------------------------------------------------- #
# Modifier-combo global hotkey (Quartz event tap)
#
# The Fn key is not delivered as a normal key event, so pynput can't see it.
# A CGEventTap watching kCGEventFlagsChanged can, because it reads the raw
# modifier-flag bitmask. This also cleanly handles pure-modifier combos like
# Fn+Shift (no letter key needed). Requires Accessibility permission — the same
# permission WhisperBar already needs to paste.
# --------------------------------------------------------------------------- #
class ModifierHotkey(threading.Thread):
    def __init__(self, modifier_names, callback):
        super().__init__(daemon=True)
        # Normalize aliases (option->alt, control->ctrl, ...).
        self._names = []
        for n in modifier_names:
            canon = MOD_ALIASES.get(n.strip().lower())
            if canon and canon not in self._names:
                self._names.append(canon)
        if not self._names:
            raise ValueError(f"invalid modifier hotkey: {modifier_names}")
        self._callback = callback
        self._was_active = False
        self._runloop = None
        self._tap = None

    def _masks(self, Quartz):
        table = {
            "fn": Quartz.kCGEventFlagMaskSecondaryFn,
            "shift": Quartz.kCGEventFlagMaskShift,
            "ctrl": Quartz.kCGEventFlagMaskControl,
            "alt": Quartz.kCGEventFlagMaskAlternate,
            "cmd": Quartz.kCGEventFlagMaskCommand,
        }
        return [table[n] for n in self._names]

    def run(self):
        import Quartz  # macOS-only; imported lazily

        masks = self._masks(Quartz)

        def handler(proxy, type_, event, refcon):
            # Re-enable the tap if macOS disabled it.
            if type_ in (
                Quartz.kCGEventTapDisabledByTimeout,
                Quartz.kCGEventTapDisabledByUserInput,
            ):
                if self._tap is not None:
                    Quartz.CGEventTapEnable(self._tap, True)
                return event
            flags = Quartz.CGEventGetFlags(event)
            active = all(flags & m for m in masks)
            if active and not self._was_active:
                self._was_active = True
                try:
                    self._callback()
                except Exception as exc:  # noqa: BLE001
                    log.error(f"[hotkey] callback error: {exc}")
            elif not active:
                self._was_active = False
            return event

        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged),
            handler,
            None,
        )
        if not self._tap:
            log.error(
                "[hotkey] could not create event tap — grant Accessibility "
                "permission to WhisperBar and relaunch."
            )
            return
        src = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        self._runloop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(
            self._runloop, src, Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(self._tap, True)
        Quartz.CFRunLoopRun()

    def stop(self):
        if self._runloop is not None:
            import Quartz

            Quartz.CFRunLoopStop(self._runloop)


# --------------------------------------------------------------------------- #
# Menu bar app
# --------------------------------------------------------------------------- #
class WhisperBarApp(rumps.App):
    def __init__(self):
        self.cfg = load_config()
        super().__init__(APP_NAME, title=ICONS["loading"], quit_button=None)

        self.state = "loading"
        self.status_line = "Loading model…"
        self._model = None
        self._model_lock = threading.Lock()
        self._recorder = Recorder()
        self._recording = False
        self._record_started = 0.0
        self._ui_queue = queue.Queue()
        self._history = TranscriptHistory(maxlen=3)
        self._history_dirty = False

        self._build_menu()

        # Load the model in the background so the menu bar appears instantly.
        threading.Thread(target=self._load_model, daemon=True).start()

        # Global hotkey listener.
        self._hotkey_listener = None
        self._install_hotkey()

        # Poll for UI updates on the main thread (rumps run loop).
        self._timer = rumps.Timer(self._tick, 0.2)
        self._timer.start()

    # ---- menu construction ------------------------------------------------ #
    def _build_menu(self):
        self.status_item = rumps.MenuItem("Loading model…")
        self.status_item.set_callback(None)

        self.toggle_item = rumps.MenuItem(
            "Start / Stop Dictation", callback=self.toggle_recording
        )

        # Recover recent transcriptions if an insertion didn't land. Populated
        # on the main thread by _rebuild_recent_menu (see _tick).
        self.recent_menu = rumps.MenuItem("Recent Transcriptions")
        self._rebuild_recent_menu()

        model_menu = rumps.MenuItem("Model")
        for name in MODEL_CHOICES:
            item = rumps.MenuItem(name, callback=self._make_model_setter(name))
            item.state = 1 if name == self.cfg["model"] else 0
            model_menu.add(item)

        method_menu = rumps.MenuItem("Insert method")
        for name in ["paste", "type", "clipboard"]:
            item = rumps.MenuItem(name, callback=self._make_method_setter(name))
            item.state = 1 if name == self.cfg["insert_method"] else 0
            method_menu.add(item)

        self.hotkey_item = rumps.MenuItem(
            f"Hotkey: {hotkey_label(self.cfg['hotkey'])}"
        )
        self.hotkey_item.set_callback(None)

        self.menu = [
            self.status_item,
            None,
            self.toggle_item,
            self.recent_menu,
            None,
            model_menu,
            method_menu,
            self.hotkey_item,
            None,
            rumps.MenuItem("Quit", callback=self._quit),
        ]

    def _make_model_setter(self, name):
        def setter(_):
            if name == self.cfg["model"]:
                return
            self.cfg["model"] = name
            save_config(self.cfg)
            # Update checkmarks
            for key, item in self.menu["Model"].items():
                item.state = 1 if key == name else 0
            self._set_state("loading", f"Loading {name}…")
            threading.Thread(target=self._load_model, daemon=True).start()

        return setter

    def _make_method_setter(self, name):
        def setter(_):
            self.cfg["insert_method"] = name
            save_config(self.cfg)
            for key, item in self.menu["Insert method"].items():
                item.state = 1 if key == name else 0

        return setter

    # ---- recent transcriptions ------------------------------------------- #
    def _rebuild_recent_menu(self):
        """Repopulate the Recent Transcriptions submenu. Main thread only.

        rumps menu mutation isn't thread-safe, so this is only ever called from
        _build_menu (__init__) and _tick (the rumps.Timer callback).
        """
        # clear() calls removeAllItems() on the submenu's NSMenu, which rumps
        # only creates lazily on the first add() — so guard the empty first pass.
        if len(self.recent_menu):
            self.recent_menu.clear()
        recent = self._history.recent()
        if not recent:
            empty = rumps.MenuItem("No transcriptions yet")
            empty.set_callback(None)  # disabled/greyed
            self.recent_menu.add(empty)
            return
        # Number the rows (newest = 1). Besides reading naturally as a recency
        # list, this keeps each title unique — rumps keys submenu items by title,
        # so two transcripts sharing a preview would otherwise collide.
        for i, text in enumerate(recent, start=1):
            item = rumps.MenuItem(
                f"{i}. {preview_label(text)}",
                callback=self._make_recent_copier(text),
            )
            self.recent_menu.add(item)

    def _make_recent_copier(self, text):
        def copier(_):
            set_clipboard(text)
            self._set_state(self.state, "Copied to clipboard")

        return copier

    # ---- model ------------------------------------------------------------ #
    def _load_model(self):
        try:
            from faster_whisper import WhisperModel

            name = self.cfg["model"]
            self._set_state("loading", f"Loading {name}…")

            def _make(local_only):
                return WhisperModel(
                    name,
                    device=self.cfg["device"],
                    compute_type=self.cfg["compute_type"],
                    cpu_threads=self.cfg["cpu_threads"],  # 0 = auto-detect
                    local_files_only=local_only,
                )

            # Fast path: if the model is already cached, load straight from disk
            # and skip the Hugging Face network revalidation (~0.35s/launch, and
            # it works fully offline). Fall back to a downloading load otherwise.
            try:
                model = _make(local_only=True)
            except Exception:  # not cached yet → download
                self._set_state("loading", f"Downloading {name}… (first run)")
                model = _make(local_only=False)

            with self._model_lock:
                self._model = model
            self._set_state("idle", "Ready")
        except Exception as exc:  # noqa: BLE001
            self._set_state("error", f"Model load failed: {exc}")
            log.error(f"[model] {exc}")

    # ---- hotkey ----------------------------------------------------------- #
    def _install_hotkey(self):
        hk = self.cfg["hotkey"]
        try:
            if self._hotkey_listener is not None:
                self._hotkey_listener.stop()
                self._hotkey_listener = None

            mods, key = parse_hotkey(hk)

            if key is None:
                # Modifier-only combo (e.g. fn+shift) → Quartz event tap.
                self._hotkey_listener = ModifierHotkey(mods, self._hotkey_fired)
            elif "fn" in mods:
                # pynput can't express Fn together with a regular key.
                self._set_hotkey_status(
                    f"⚠️ Hotkey unavailable: {hotkey_label(hk)} mixes Fn with a "
                    "key (unsupported)"
                )
                log.warning(
                    f"[hotkey] '{hk}' combines Fn with a key, which isn't "
                    "supported. Use a modifier-only Fn combo (e.g. fn+shift) "
                    "or drop Fn."
                )
                return
            else:
                # Real key + modifiers → pynput global hotkey, normalized.
                combo = build_pynput_combo(mods, key)
                self._hotkey_listener = keyboard.GlobalHotKeys(
                    {combo: self._hotkey_fired}
                )

            self._hotkey_listener.start()
            self._set_hotkey_status(f"Hotkey: {hotkey_label(hk)}")
            log.info(f"[hotkey] registered: {hotkey_label(hk)}  (raw='{hk}')")
        except Exception as exc:  # noqa: BLE001
            self._set_hotkey_status(f"⚠️ Hotkey failed: {hotkey_label(hk)} — see logs")
            log.error(f"[hotkey] failed to register '{hk}': {exc}")

    def _set_hotkey_status(self, text):
        """Reflect hotkey registration state in the menu (thread-safe-ish).

        Called from __init__ (main thread) and, on re-install, potentially from
        a setter; updating a rumps MenuItem title is a cheap attribute set.
        """
        try:
            self.hotkey_item.title = text
        except Exception:  # noqa: BLE001 — menu not built yet / rumps quirk
            pass

    def _hotkey_fired(self):
        # Runs on the pynput listener thread — safe to touch recorder.
        self._toggle()

    # ---- recording -------------------------------------------------------- #
    def toggle_recording(self, _=None):
        self._toggle()

    def _toggle(self):
        if self.state == "loading":
            self._set_state("loading", "Still loading model…")
            return
        if not self._recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        try:
            self._recorder.start()
            self._recording = True
            self._record_started = time.monotonic()
            self._set_state("recording", "Recording… (hotkey again to stop)")
        except Exception as exc:  # noqa: BLE001
            self._set_state("error", f"Mic error: {exc}")
            log.error(f"[audio] {exc}")

    def _stop_recording(self):
        self._recording = False
        audio = self._recorder.stop()
        self._set_state("transcribing", "Transcribing…")
        threading.Thread(
            target=self._transcribe_and_insert, args=(audio,), daemon=True
        ).start()

    def _transcribe_and_insert(self, audio):
        try:
            if audio.size < SAMPLE_RATE * 0.3:  # < 0.3s of audio
                self._set_state("idle", "Too short — nothing captured")
                return
            with self._model_lock:
                model = self._model
            if model is None:
                self._set_state("error", "Model not ready")
                return

            language = self.cfg.get("language") or None
            segments, _info = model.transcribe(
                audio,
                language=language,
                beam_size=self.cfg["beam_size"],
                vad_filter=True,          # skip silence → less to decode
                without_timestamps=True,  # dictation doesn't need timestamps
                condition_on_previous_text=False,  # faster; avoids repeat loops
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()

            if not text:
                self._set_state("idle", "No speech detected")
                return

            # Retain the transcript *before* inserting, so it's recoverable from
            # the menu even if insertion raises or the paste doesn't land.
            self._history.add(text)
            self._history_dirty = True
            insert_text(text, self.cfg["insert_method"])
            self._set_state("idle", f"Inserted: {preview_label(text)}")
        except Exception as exc:  # noqa: BLE001
            self._set_state("error", f"Transcription failed: {exc}")
            log.error(f"[transcribe] {exc}")

    # ---- thread-safe UI updates ------------------------------------------ #
    def _set_state(self, state, status_line):
        self._ui_queue.put((state, status_line))

    def _tick(self, _timer):
        # Safety net: auto-stop a recording that's run past the cap (e.g. the
        # user forgot to stop, or a stray hotkey event left it running) so the
        # audio buffer can't grow without bound.
        if (
            self._recording
            and time.monotonic() - self._record_started > MAX_RECORDING_SECONDS
        ):
            log.info(f"[audio] auto-stopped after {MAX_RECORDING_SECONDS}s cap")
            self._stop_recording()

        updated = False
        while True:
            try:
                self.state, self.status_line = self._ui_queue.get_nowait()
                updated = True
            except queue.Empty:
                break
        if updated:
            self.title = ICONS.get(self.state, ICONS["idle"])
            self.status_item.title = self.status_line

        # Rebuild the Recent Transcriptions submenu here, on the main thread,
        # after a background transcription appended to the history.
        if self._history_dirty:
            self._history_dirty = False
            self._rebuild_recent_menu()

    # ---- quit ------------------------------------------------------------- #
    def _quit(self, _):
        try:
            if self._hotkey_listener is not None:
                self._hotkey_listener.stop()
            if self._recording:
                self._recorder.stop()
        finally:
            rumps.quit_application()


def main():
    setup_logging()
    log.info(f"[startup] {APP_NAME} starting")
    WhisperBarApp().run()


if __name__ == "__main__":
    main()
