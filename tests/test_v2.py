import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.gemini_client import parse_obj, profile_text, rank_models
from config.settings import Settings
from windows import inputctl


class Models(unittest.TestCase):
    def test_rank(self):
        names = ["models/gemini-2.5-flash", "models/gemini-3.5-flash", "models/gemini-3.5-flash-lite",
                 "models/gemini-3.1-flash-image", "models/gemini-3.1-flash-live-preview", "models/gemini-3.1-pro-preview",
                 "models/gemini-3.5-flash-preview-tts", "models/embedding-001"]
        self.assertEqual(rank_models(names), "gemini-3.5-flash")

    def test_rank_stable_over_preview(self):
        self.assertEqual(rank_models(["models/gemini-3-flash-preview", "models/gemini-3-flash"]), "gemini-3-flash")

    def test_rank_none(self):
        self.assertIsNone(rank_models(["models/embedding-001"]))

    def test_migration_retired_model(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.json"
            p.write_text(json.dumps({"gemini_model": "gemini-2.5-flash", "voice_on_start": False}))
            s = Settings(p)
            self.assertEqual(s.get("gemini_model"), "auto")
            self.assertTrue(s.get("voice_on_start"))      # migration v1 -> v2
            self.assertEqual(s.get("profile")["assistant_name"], "Polaris")

    def test_profile_text(self):
        t = profile_text({"first_name": "Léo", "age": "14", "address_form": "tu", "style": "court", "assistant_name": "Polaris"})
        self.assertIn("Léo", t)
        self.assertIn("14 ans", t)
        self.assertIn("Tutoie", t)


class Keys(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(inputctl.parse_keys("ctrl+l"), [0x11, 0x4C])
        self.assertEqual(inputctl.parse_keys("Alt + Tab"), [0x12, 0x09])
        self.assertEqual(inputctl.parse_keys("f5"), [0x74])

    def test_unknown(self):
        with self.assertRaises(ValueError):
            inputctl.parse_keys("ctrl+bidule")

    def test_delete_detected(self):
        self.assertTrue(inputctl.is_delete_combo("shift+delete"))
        self.assertTrue(inputctl.is_delete_combo("suppr"))
        self.assertFalse(inputctl.is_delete_combo("ctrl+c"))

    def test_agent_json(self):
        self.assertEqual(parse_obj('```json\n{"action":"done"}\n```')["action"], "done")
        self.assertEqual(parse_obj("n'importe quoi"), {})


if __name__ == "__main__":
    unittest.main()
