"""Unit tests for the bridge's message routing and reply chunking (no network)."""
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    path = os.path.join(HERE, "..", name)
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["PIPELINE_BRIDGE_DIR"] = self.tmp
        self.poll = load("tg-poll")

    def test_short_text_is_inlined(self):
        line = self.poll.render({"message_id": 7, "text": "status?"})
        self.assertTrue(line.startswith("[TG msg_id=7] status?"))
        self.assertIn("tg-reply", line)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "inbox", "7.txt")))

    def test_multiline_spec_goes_to_file_intact(self):
        spec = "# App\nscreen one\n\nscreen two"
        line = self.poll.render({"message_id": 8, "text": spec})
        path = os.path.join(self.tmp, "inbox", "8.txt")
        self.assertIn(path, line)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), spec)        # line breaks preserved

    def test_long_single_line_goes_to_file(self):
        line = self.poll.render({"message_id": 9, "text": "x" * 400})
        self.assertIn("full text:", line)

    def test_document_with_caption(self):
        fetched = []

        def fake_fetch(tok, file_id, name):
            fetched.append((file_id, name))
            return "/inbox/" + name
        line = self.poll.render({"message_id": 10, "caption": "spec attached",
                                 "document": {"file_id": "F1", "file_name": "tz.pdf"}},
                                fetch=fake_fetch)
        self.assertEqual(fetched, [("F1", "10_tz.pdf")])
        self.assertIn("file: /inbox/10_tz.pdf", line)
        self.assertIn("spec attached", line)

    def test_largest_photo_is_taken(self):
        got = []
        self.poll.render({"message_id": 11, "photo": [
            {"file_id": "small", "file_size": 10}, {"file_id": "big", "file_size": 999}]},
            fetch=lambda t, fid, n: got.append(fid) or "/p")
        self.assertEqual(got, ["big"])

    def test_empty_message_is_explained_not_dropped(self):
        line = self.poll.render({"message_id": 12})
        self.assertIn("not supported", line)


class ReplyTests(unittest.TestCase):
    def test_chunking_respects_telegram_limit(self):
        reply = load("tg-reply")
        parts = reply.chunks("a" * 8000)
        self.assertEqual([len(p) for p in parts], [3900, 3900, 200])
        self.assertEqual("".join(parts), "a" * 8000)


if __name__ == "__main__":
    unittest.main()
