# Live Dictation — Design

## Problem

Today WhisperBar records the whole utterance, then transcribes and inserts it
once when you stop. For longer dictation you get nothing on screen until the
end. Users want text to appear "as they talk."

## Constraints & feasibility

Whisper is a chunk model, not a token-stream model, and its output is
non-monotonic — it revises earlier words as more audio arrives. Two consequences
shape this design:

1. **No revision / no backspacing.** Correcting text already sent into another
   app means emitting backspaces blind (we can't read the target app back). If
   focus shifted or a selection changed, that deletes the user's other content.
   This is the same insertion-unreliability that motivated Recent
   Transcriptions. Live mode therefore only ever **appends**.
2. **Cost.** Sliding-window re-decoding (the usual "streaming Whisper" approach)
   re-transcribes overlapping audio every tick — multiplying CPU on a CPU/int8
   Apple-Silicon target. We avoid it: each committed region is transcribed
   exactly once.

The chosen approach is **commit-on-pause**: segment on natural silence, decode
each segment once, type it, never revise.

## Scope

- Opt-in, off by default. New config flag `live_dictation` (bool), toggled by a
  menu checkbox labeled as beta.
- While live mode is on, recording streams text phrase-by-phrase as the user
  pauses; each phrase is inserted by **simulated typing** (append-only). The
  `insert_method` setting is ignored in live mode (copy-only can't stream).
- Non-live behavior is unchanged.

### Out of scope (YAGNI)

- Word-by-word live paste; any backspacing/correction of already-typed text.
- Configurable pause/energy thresholds (use sensible constants).
- A live "interim/partial" on-screen preview before a phrase is finalized.

## Design

### Segmentation core (pure, testable)

A pure function decides, from the pending (uncommitted) audio, how many samples
to commit now:

```python
def find_commit_point(audio, sample_rate,
                      pause_seconds=0.7,
                      energy_threshold=0.01,   # RMS amplitude, float32 [-1,1]
                      max_segment_seconds=15.0):
    """Return the number of leading samples to commit, or 0 to wait.

    Commit the whole pending region when it contains speech followed by at least
    `pause_seconds` of trailing near-silence (a natural pause), OR when the
    region is longer than `max_segment_seconds` (force-commit to bound latency).
    Return 0 when the region is empty, all silence, or still mid-phrase.
    """
```

- "Speech vs silence" is per-window RMS energy vs `energy_threshold` — no extra
  dependency.
- Force-commit bounds worst-case latency and memory when someone talks without
  pausing.
- Returning the whole region (not a sub-range) keeps commits aligned to pause
  boundaries, so each decoded segment is a clean phrase.

### Recorder change

`Recorder` already appends frames continuously in its stream callback. Add a
non-destructive snapshot:

```python
def snapshot(self):
    """Return all buffered audio so far as a float32 array, without stopping
    the stream or clearing frames."""
```

`start`/`stop` are unchanged. Live mode reads via `snapshot()` and tracks its
own committed index; non-live mode keeps using `stop()`.

### LiveDictation consumer

A small object owning the tick loop, created when a live recording starts:

- Every ~0.3s: `audio = recorder.snapshot()`; consider `audio[committed:]`.
- `n = find_commit_point(pending, SAMPLE_RATE, ...)`. If `n > 0`: transcribe
  `pending[:n]` once (reusing the app's model + current transcribe params),
  type the result via `insert_text(text, "type")`, append it to a running
  combined-transcript buffer, and advance `committed += n`.
- On stop: flush — commit any remaining pending audio the same way.
- Transcription runs off the UI thread (this consumer is itself a background
  thread); it uses the app's `_model` under the existing `_model_lock`.

The app wires state transitions so that, when `live_dictation` is on,
`_start_recording` also starts the consumer and `_stop_recording` stops/flushes
it instead of doing the single end-of-utterance transcription.

### Insertion

Always `insert_text(text, "type")` in live mode, with a trailing space between
phrases so words don't run together. No clipboard use, so the user's clipboard
is untouched throughout.

### History integration

On stop, the combined transcript (all committed phrases joined) is added as a
single entry to the existing `TranscriptHistory`, so live dictations are
recoverable from the Recent Transcriptions submenu just like normal ones.

### Menu / status

- A `Live dictation` checkbox item (beta) reflecting and toggling
  `cfg["live_dictation"]`, persisted via `save_config`.
- Status line shows a live indicator while streaming (e.g. `Live… (hotkey to
  stop)`), and the normal states otherwise.

## Accuracy & performance notes

Per-phrase decoding drops cross-phrase context and Whisper is weaker on very
short segments — the accepted trade-off for low latency. Live mode is
CPU-heavier than one-shot; README should recommend `small.en` or smaller. No
hard block on larger models.

## Testing

Pure-logic unit tests (matching existing conventions — no audio/model/UI):

- `find_commit_point`:
  - empty region → 0.
  - all-silence region → 0.
  - speech followed by < `pause_seconds` silence (mid-phrase) → 0.
  - speech followed by ≥ `pause_seconds` silence → commit whole region.
  - region longer than `max_segment_seconds` with no pause → force-commit.
- (Existing `preview_label` / `TranscriptHistory` / config / hotkey tests keep
  passing.)

The `Recorder.snapshot`, `LiveDictation` loop, and menu wiring are exercised
the way the rest of the rumps/audio code is — not unit-tested — but built on the
tested pure core.

## Documentation

README: add a `Live dictation (beta)` note under Features / How it works —
opt-in menu toggle, text appears as you pause, append-only (no corrections),
best with a small/fast model.
