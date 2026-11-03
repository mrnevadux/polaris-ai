import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.gemini_client import parse_plan
from config.settings import Settings
from core import router
from core.textutil import clean_for_speech, normalize
from files import manager, search
from security import secrets
from security.permissions import Permissions
from voice.wakeword import find_wake


class WakeWord(unittest.TestCase):
    def test_wake_with_command(self):
        self.assertEqual(find_wake("hey polaris ouvre le bloc notes"), (True, "ouvre le bloc notes"))

    def test_wake_alone(self):
        self.assertEqual(find_wake("et polaris"), (True, ""))

    def test_split_word(self):
        self.assertTrue(find_wake("hé pola ris quelle heure est il")[0])

    def test_no_wake(self):
        for t in ("bonjour tout le monde", "la police arrive", ""):
            self.assertFalse(find_wake(t)[0], t)


class Router(unittest.TestCase):
    def test_open_app(self):
        self.assertEqual(router.parse("Ouvre le Bloc-notes"), [("open_app", {"name": "bloc notes"})])

    def test_polite_open(self):
        self.assertEqual(router.parse("Polaris, peux-tu ouvrir la calculatrice ?"), [("open_app", {"name": "calculatrice"})])

    def test_close(self):
        self.assertEqual(router.parse("ferme la calculatrice"), [("close_app", {"name": "calculatrice"})])

    def test_url(self):
        self.assertEqual(router.parse("ouvre youtube")[0][0], "open_url")

    def test_settings(self):
        self.assertEqual(router.parse("ouvre les paramètres wifi"), [("open_settings", {"page": "wifi"})])

    def test_time(self):
        self.assertEqual(router.parse("Quelle heure est-il ?"), [("time_now", {})])

    def test_stop_and_mic(self):
        self.assertEqual(router.parse("stop"), [("stop_speaking", {})])
        self.assertEqual(router.parse("arrête d'écouter"), [("mic_off", {})])

    def test_result_index(self):
        self.assertEqual(router.parse("ouvre le premier résultat"), [("open_file", {"path": "result:1"})])
        self.assertEqual(router.parse("ouvre le dernier fichier"), [("open_file", {"path": "result:last"})])

    def test_file_search(self):
        t, a = router.parse("Polaris, trouve mon fichier PDF sur Apollo 11")[0]
        self.assertEqual((t, a["ext"], a["query"]), ("search_files", "pdf", "apollo 11"))
        t, a = router.parse("trouve tous mes fichiers python")[0]
        self.assertEqual(a["ext"], "python")
        t, a = router.parse("cherche une image dans mes téléchargements")[0]
        self.assertEqual((a["ext"], a["folder"]), ("image", "telechargements"))
        t, a = router.parse("cherche un fichier qui contient le mot facture")[0]
        self.assertEqual(a["content"], "facture")

    def test_defer_to_ai(self):
        self.assertIsNone(router.parse("explique-moi la relativité"))
        self.assertIsNone(router.parse("ouvre mon document"))
        self.assertIsNone(router.parse("cherche sur internet la météo"))


class Planner(unittest.TestCase):
    def test_json(self):
        p = parse_plan('```json\n{"say":"ok","calls":[{"tool":"time_now","args":{}}]}\n```')
        self.assertEqual(p["calls"][0]["tool"], "time_now")

    def test_plain_text(self):
        self.assertEqual(parse_plan("bonjour"), {"say": "bonjour", "calls": []})

    def test_max_calls(self):
        calls = [{"tool": "time_now", "args": {}}] * 6
        import json
        self.assertEqual(len(parse_plan(json.dumps({"say": "", "calls": calls}))["calls"]), 3)


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "Apollo 11 rapport.pdf").write_bytes(b"%PDF-1.4")
        (self.root / "notes.txt").write_text("Voici ma Facture d'électricité", encoding="utf-8")
        (self.root / "script.py").write_text("print(1)", encoding="utf-8")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "photo.JPG").write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_name_and_ext(self):
        r = search.search([self.root], "apollo 11", search.exts_from("pdf"))
        self.assertEqual([x.name for x in r], ["Apollo 11 rapport.pdf"])

    def test_ext_group_recursive(self):
        self.assertEqual([x.name for x in search.search([self.root], "", search.exts_from("image"))], ["photo.JPG"])

    def test_content(self):
        self.assertEqual([x.name for x in search.search([self.root], "", None, "facture")], ["notes.txt"])

    def test_empty_search_refused(self):
        self.assertEqual(search.search([self.root]), [])

    def test_rename_never_overwrites(self):
        with self.assertRaises(manager.FileError):
            manager.rename(self.root / "script.py", "notes.txt")

    def test_classify(self):
        plan = manager.plan_classify(self.root)
        self.assertIn("PDF", plan)
        self.assertEqual(manager.apply_classify(self.root, plan), 2)
        self.assertTrue((self.root / "PDF" / "Apollo 11 rapport.pdf").exists())


class Misc(unittest.TestCase):
    def test_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            s = Settings(Path(d) / "s.json")
            s.set("extra_folders", [d])
            p = Permissions(s)
            self.assertTrue(p.is_allowed(Path(d) / "a.txt"))
            self.assertFalse(p.is_allowed(Path(d).parent / "autre" / "x.txt"))
            s.set("perm_files_modify", False)
            self.assertFalse(Permissions(s).category_enabled("files_modify"))

    def test_api_key_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            s = Settings(Path(d) / "s.json")
            s.set_api_key("AIza-test-123")
            self.assertNotIn("AIza-test-123", (Path(d) / "s.json").read_text())
            self.assertEqual(Settings(Path(d) / "s.json").get_api_key(), "AIza-test-123")

    def test_speech_cleanup(self):
        out = clean_for_speech("Voici :\n```python\nprint(1)\n```\nVoir https://x.fr **gras**")
        self.assertNotIn("print", out)
        self.assertNotIn("https", out)

    def test_normalize(self):
        self.assertEqual(normalize("Téléchargements l'été"), "telechargements l ete")


if __name__ == "__main__":
    unittest.main()
