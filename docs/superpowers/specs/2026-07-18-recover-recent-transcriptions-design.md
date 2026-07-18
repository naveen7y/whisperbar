# Recover Recent Transcriptions — Design

## Problem

When a dictation finishes, WhisperBar inserts the transcribed text at the
cursor and then discards it. The text only ever lives in the local variable
`text` inside `_transcribe_and_insert` (`whisperbar.py`). If insertion fails —
nothing was highlighted, the paste didn't land, the wrong app/tab had focus, or
the user simply missed it — there is currently no way to recover the transcript.
The only recourse is to dictate the whole thing again.

## Goal

Let the user re-grab a recent transcript from the menu bar and copy it to the
clipboard, so a failed insertion never means re-dictating.

## Scope

- Keep the **last 3** successful transcriptions.
- **In-memory only** — never written to disk, cleared on quit. This preserves
  WhisperBar's core promise that nothing you say leaves your Mac and it leaves
  no trace.
- Expose them in a **`Recent Transcriptions ▸` submenu**; clicking an entry
  copies its full text to the clipboard.

### Out of scope (YAGNI)

- Disk persistence / history across restarts.
- Configurable history size.
- Editing or deleting individual entries.
- Re-pasting into the focused app (we only copy; the user pastes where they
  want). Copy is safer and avoids re-triggering the same focus problem.

## Design

### Storage

- A `collections.deque(maxlen=3)` on the `WhisperBarApp` instance holds the full
  text of the last 3 successful transcriptions, newest appended last.
- Access is guarded by a `threading.Lock` because the writer is a background
  transcription thread and the reader is the main (UI) thread.

### Capturing transcripts

In `_transcribe_and_insert`, after the final `text` is computed and confirmed
non-empty (and before `insert_text` runs), append it to the history under the
lock, then mark the history dirty so the UI rebuilds. Capturing *before*
insertion means the transcript is retained even if `insert_text` raises.

### Menu

- A new `Recent Transcriptions` submenu is added just after
  `Start / Stop Dictation`.
- Each entry's title is a truncated preview (see `preview_label` below); newest
  entry at the top. Clicking an entry copies its **full** text to the clipboard
  via the existing `set_clipboard()` and updates the status line to confirm
  (e.g. `Copied to clipboard`).
- When the history is empty, the submenu contains a single disabled item:
  `No transcriptions yet`.

### Thread safety

rumps menu mutation must happen on the main thread, but transcription runs on a
background daemon thread. The app already solves this class of problem: state
updates are enqueued via `_set_state` onto `self._ui_queue` and drained by the
main-thread `rumps.Timer` callback `_tick`.

Reuse that mechanism. The background thread only appends to the deque (under the
lock) and sets a `self._history_dirty` flag. `_tick` checks the flag on the main
thread and, when set, rebuilds the submenu from a locked snapshot of the deque.
No new threading model is introduced.

### Small refactor: `preview_label`

The 40-char preview is currently computed inline where the status line is set
(`preview = text if len(text) <= 40 else text[:37] + "…"`). Extract it to a pure
helper:

```python
def preview_label(text, limit=40):
    """Single-line, length-capped label for menus/status (… if truncated)."""
    text = " ".join(text.split())  # collapse newlines/runs of whitespace
    return text if len(text) <= limit else text[: limit - 1] + "…"
```

Used by both the status line and the menu entries. Collapsing whitespace keeps
multi-line dictations readable as a single menu title.

## Testing

Pure-logic unit tests only (matching the existing `test_whisperbar.py`
conventions — no audio/model/UI):

- `preview_label`: short text passes through unchanged; long text is truncated
  to `limit` chars ending in `…`; internal newlines/whitespace runs collapse to
  single spaces.
- History container behavior: appending keeps only the last 3; order is
  newest-first when read for display; oldest is dropped past the cap.

## Documentation

Add a short note to the README (Features and/or How it works) explaining that if
a paste doesn't land, recent transcriptions can be copied from the menu bar.
