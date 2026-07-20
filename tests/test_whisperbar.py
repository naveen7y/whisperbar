"""Unit tests for WhisperBar's pure logic (no audio/model/UI needed).

Run from the repo root inside the virtualenv:

    ./.venv/bin/python -m unittest discover -s tests -v

These cover config sanitization and hotkey parsing — the parts most likely to
break on a refactor and the ones that guard the config trust boundary.
"""

import unittest

import numpy as np

import whisperbar as wb


class SanitizeConfigTests(unittest.TestCase):
    def _san(self, **overrides):
        return wb._sanitize_config(dict(wb.DEFAULT_CONFIG, **overrides))

    def test_defaults_pass_through(self):
        out = self._san()
        for key in ("model", "device", "compute_type", "insert_method",
                    "beam_size", "cpu_threads", "live_dictation"):
            self.assertEqual(out[key], wb.DEFAULT_CONFIG[key])

    def test_live_dictation_must_be_bool(self):
        self.assertTrue(self._san(live_dictation=True)["live_dictation"])
        for bad in ("yes", 1, None):
            with self.subTest(bad=bad):
                self.assertEqual(self._san(live_dictation=bad)["live_dictation"],
                                 wb.DEFAULT_CONFIG["live_dictation"])

    def test_malicious_model_falls_back(self):
        # An arbitrary path/repo id must not reach the model loader.
        out = self._san(model="../../etc/evil")
        self.assertEqual(out["model"], wb.DEFAULT_CONFIG["model"])

    def test_valid_alternate_values_kept(self):
        out = self._san(model="distil-large-v3", compute_type="float32",
                        insert_method="clipboard", beam_size=5)
        self.assertEqual(out["model"], "distil-large-v3")
        self.assertEqual(out["compute_type"], "float32")
        self.assertEqual(out["insert_method"], "clipboard")
        self.assertEqual(out["beam_size"], 5)

    def test_bad_device_and_compute_type_fall_back(self):
        out = self._san(device="gpu", compute_type="pwn")
        self.assertEqual(out["device"], wb.DEFAULT_CONFIG["device"])
        self.assertEqual(out["compute_type"], wb.DEFAULT_CONFIG["compute_type"])

    def test_beam_size_bounds_and_types(self):
        for bad in ("huge", 0, 99, -1, 2.5, True):
            with self.subTest(bad=bad):
                self.assertEqual(self._san(beam_size=bad)["beam_size"],
                                 wb.DEFAULT_CONFIG["beam_size"])

    def test_cpu_threads_nonnegative_int(self):
        self.assertEqual(self._san(cpu_threads=4)["cpu_threads"], 4)
        for bad in (-1, "auto", 1.5, True):
            with self.subTest(bad=bad):
                self.assertEqual(self._san(cpu_threads=bad)["cpu_threads"],
                                 wb.DEFAULT_CONFIG["cpu_threads"])


class HotkeyParsingTests(unittest.TestCase):
    def test_aliases_and_angle_brackets_equivalent(self):
        for raw in ("ctrl+option+space", "control+option+space",
                    "<ctrl>+<alt>+<space>"):
            mods, key = wb.parse_hotkey(raw)
            self.assertEqual(mods, ["ctrl", "alt"])
            self.assertEqual(key, "space")

    def test_modifier_only_combo_has_no_key(self):
        mods, key = wb.parse_hotkey("fn+shift")
        self.assertEqual(mods, ["fn", "shift"])
        self.assertIsNone(key)

    def test_duplicate_modifiers_collapse(self):
        mods, _ = wb.parse_hotkey("ctrl+control+alt")
        self.assertEqual(mods, ["ctrl", "alt"])

    def test_build_pynput_combo_wraps_special_keys(self):
        self.assertEqual(
            wb.build_pynput_combo(["ctrl", "alt"], "space"),
            "<ctrl>+<alt>+<space>",
        )

    def test_build_pynput_combo_leaves_literal_char(self):
        self.assertEqual(
            wb.build_pynput_combo(["cmd"], "k"),
            "<cmd>+k",
        )

    def test_hotkey_label_is_human_readable(self):
        self.assertEqual(
            wb.hotkey_label("ctrl+option+space"),
            "Control + Option + Space",
        )


class PreviewLabelTests(unittest.TestCase):
    def test_short_text_passes_through(self):
        self.assertEqual(wb.preview_label("hello there"), "hello there")

    def test_long_text_truncated_with_ellipsis(self):
        text = "x" * 100
        out = wb.preview_label(text, limit=40)
        self.assertEqual(len(out), 40)
        self.assertTrue(out.endswith("…"))
        self.assertEqual(out, "x" * 39 + "…")

    def test_exact_limit_not_truncated(self):
        text = "y" * 40
        self.assertEqual(wb.preview_label(text, limit=40), text)

    def test_whitespace_and_newlines_collapse(self):
        self.assertEqual(
            wb.preview_label("one\n  two\t\tthree   four"),
            "one two three four",
        )


class TranscriptHistoryTests(unittest.TestCase):
    def test_empty_history_returns_nothing(self):
        h = wb.TranscriptHistory(maxlen=3)
        self.assertEqual(h.recent(), [])

    def test_recent_is_newest_first(self):
        h = wb.TranscriptHistory(maxlen=3)
        h.add("first")
        h.add("second")
        self.assertEqual(h.recent(), ["second", "first"])

    def test_keeps_only_last_n_dropping_oldest(self):
        h = wb.TranscriptHistory(maxlen=3)
        for t in ("a", "b", "c", "d"):
            h.add(t)
        self.assertEqual(h.recent(), ["d", "c", "b"])


class FindCommitPointTests(unittest.TestCase):
    SR = 16000

    def _speech(self, seconds, amp=0.1):
        return np.full(int(self.SR * seconds), amp, dtype=np.float32)

    def _silence(self, seconds):
        return np.zeros(int(self.SR * seconds), dtype=np.float32)

    def _find(self, audio, **kw):
        return wb.find_commit_point(audio, self.SR, **kw)

    def test_empty_region_waits(self):
        self.assertEqual(self._find(np.zeros(0, dtype=np.float32)), 0)

    def test_all_silence_waits(self):
        self.assertEqual(self._find(self._silence(1.0)), 0)

    def test_speech_then_short_silence_waits(self):
        # 0.3s of trailing silence < 0.7s pause → still mid-phrase.
        audio = np.concatenate([self._speech(0.5), self._silence(0.3)])
        self.assertEqual(self._find(audio, pause_seconds=0.7), 0)

    def test_speech_then_long_silence_commits_whole_region(self):
        audio = np.concatenate([self._speech(0.5), self._silence(0.8)])
        self.assertEqual(self._find(audio, pause_seconds=0.7), audio.size)

    def test_long_continuous_speech_force_commits(self):
        # No pause, but past the max-segment cap → force commit.
        audio = self._speech(16.0)
        self.assertEqual(
            self._find(audio, pause_seconds=0.7, max_segment_seconds=15.0),
            audio.size,
        )

    def test_zero_thresholds_commit_iff_speech(self):
        # Flush uses this: zero pause + zero cap => commit the region only when
        # it contains speech, skip a pure-silence tail.
        speech = self._speech(0.5)
        self.assertEqual(
            self._find(speech, pause_seconds=0.0, max_segment_seconds=0.0),
            speech.size,
        )
        self.assertEqual(
            self._find(self._silence(0.5), pause_seconds=0.0, max_segment_seconds=0.0),
            0,
        )

    def test_long_silence_never_force_commits(self):
        # A big block of pure silence must not trigger the length cap (we don't
        # want to run the model on nothing).
        self.assertEqual(
            self._find(self._silence(20.0), max_segment_seconds=15.0), 0
        )


if __name__ == "__main__":
    unittest.main()
