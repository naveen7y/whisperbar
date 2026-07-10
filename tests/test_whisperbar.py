"""Unit tests for WhisperBar's pure logic (no audio/model/UI needed).

Run from the repo root inside the virtualenv:

    ./.venv/bin/python -m unittest discover -s tests -v

These cover config sanitization and hotkey parsing — the parts most likely to
break on a refactor and the ones that guard the config trust boundary.
"""

import unittest

import whisperbar as wb


class SanitizeConfigTests(unittest.TestCase):
    def _san(self, **overrides):
        return wb._sanitize_config(dict(wb.DEFAULT_CONFIG, **overrides))

    def test_defaults_pass_through(self):
        out = self._san()
        for key in ("model", "device", "compute_type", "insert_method",
                    "beam_size", "cpu_threads"):
            self.assertEqual(out[key], wb.DEFAULT_CONFIG[key])

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


if __name__ == "__main__":
    unittest.main()
