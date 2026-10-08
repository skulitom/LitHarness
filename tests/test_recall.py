"""Recall over plain chapter files with a fake embedder: no test reaches Ollama."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from litharness import files, recall


def vectors(texts, seen):
    """Two topics and a constant, so every vector has a length."""
    seen.extend(texts)
    return [[t.count("dragon"), t.count("river"), 0.1] for t in texts]


class RecallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root, self.seen = Path(self.tmp.name), []
        for k, topic in enumerate(["dragon", "river", "dragon"], 1):
            files.write(self.root / f"ch{k:02d}" / "chapter.md", "\n\n".join(f"Day {k}, {topic} {i}. " * 30 for i in range(3)))
        patcher = patch.object(recall, "embed", lambda texts: vectors(texts, self.seen))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_passages_end_at_scene_breaks_and_join_paragraphs_up_to_their_size(self):
        short, long = "a" * 400, "b" * 1200
        self.assertEqual(recall.passages(f"{short}\n\n{short}\n\n{short}"), [f"{short}\n\n{short}", short])
        self.assertEqual(recall.passages(f"{short}\n\n***\n\n{short}\n\n{long}\n\n***"), [short, short, long])

    def test_the_closest_passages_before_the_previous_chapter_in_story_order_within_room(self):
        query = "## Open\n- the dragon came back to the valley\n- short"
        self.assertEqual(recall.recall(self.root, 2, query, 6000), "")
        self.assertEqual(recall.recall(self.root, 4, query, recall.PASSAGE - 1), "")
        found = recall.recall(self.root, 4, query, 2000)  # chapter 3 is the previous one: its dragon stays out
        self.assertEqual(found, "\n\n***\n\n".join(recall.passages(files.read(self.root / "ch01" / "chapter.md"))))
        self.assertEqual(self.seen[-1], "task: search result | query: the dragon came back to the valley")
        self.assertTrue(self.seen[0].startswith("title: none | text: Day 1, dragon 0."))
        self.assertFalse((self.root / "ch03" / "vectors.json").exists())

    def test_vectors_are_kept_until_the_chapter_or_the_model_changes(self):
        recall.recall(self.root, 4, "the dragon came back to the valley", 2000)
        asked = len(self.seen)
        recall.recall(self.root, 4, "the dragon came back to the valley", 2000)
        self.assertEqual(len(self.seen), asked + 1)  # only the query is embedded again
        files.write(self.root / "ch02" / "chapter.md", "A river again, and the dragon over it.")
        with patch.object(recall, "MODEL", "another:1m"):
            found = recall.recall(self.root, 4, "the dragon came back to the valley", 6000)
        self.assertEqual(len(self.seen), asked + 1 + 3 + 1 + 1)  # ch01's 3 passages, ch02's one, the query
        self.assertTrue(found.endswith("A river again, and the dragon over it."))
        self.assertEqual(files.load(self.root / "ch01" / "vectors.json")["model"], "another:1m")


class EmbedTests(unittest.TestCase):
    def test_cuts_to_the_matryoshka_size_renormalizes_and_names_ollama_when_it_fails(self):
        reply = json.dumps({"embeddings": [[3.0, 4.0] + [0.0] * 766]}).encode()
        with patch.object(recall.urllib.request, "urlopen", return_value=io.BytesIO(reply)) as opened:
            [vector] = recall.embed(["text"])
        self.assertEqual((len(vector), vector[:2]), (recall.DIMS, [0.6, 0.8]))
        self.assertEqual(json.loads(opened.call_args[0][0].data), {"model": recall.MODEL, "input": ["text"]})
        for failure in (urllib.error.URLError("refused"), io.BytesIO(b'{"error": "model not found"}'),
                        io.BytesIO(b'{"embeddings": []}')):
            with self.subTest(failure=failure), self.assertRaisesRegex(ValueError, "Ollama"), patch.object(
                    recall.urllib.request, "urlopen", side_effect=[failure] if isinstance(failure, Exception) else None,
                    return_value=failure):
                recall.embed(["text"])
