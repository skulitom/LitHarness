"""Budgets that keep the rebuild small. No allowlists and no exception dicts."""
import ast
from fnmatch import fnmatch
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from litharness import checks, files, prompts, tells

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "tests" / "fixtures.json").read_bytes())
RUNTIME = sorted((ROOT / "litharness").glob("*.py"))
SCRIPTS = RUNTIME + sorted(ROOT.glob("bench.py"))
DOCS = {"README.md": 80, "AGENTS.md": 80, "CLAUDE.md": 40, "LEARNINGS.md": 150, "DECISIONS.md": 80,
        "reads/CHECKLIST.md": 40}
EXEMPLARS = Path(r"C:\DEV\LitHarness-archive\tree\book-library")
WORDS = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def lines(path):
    return len(path.read_bytes().splitlines())


def imports(path):
    for node in ast.walk(ast.parse(path.read_bytes())):
        if isinstance(node, ast.Import):
            yield from (alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module.split(".")[0]


def runs(text, n):
    tokens = WORDS.findall(text.lower())
    return {hash(" ".join(tokens[i:i + n])) for i in range(len(tokens) - n + 1)}


class Guards(unittest.TestCase):
    def test_size(self):
        runtime = sum(lines(p) for p in RUNTIME)
        self.assertLessEqual(runtime, 1350)
        for path in [*ROOT.glob("*.py"), *RUNTIME, *(ROOT / "tests").glob("*.py"), *ROOT.glob("experiments/**/*.py")]:
            self.assertLessEqual(lines(path), 300 if path.name == "bench.py" else 350, path)
            self.assertNotIn("\u00a7", path.read_text(encoding="utf-8"), path)
        self.assertLessEqual(sum(lines(p) for p in (ROOT / "tests").glob("*.py")), runtime)

    def test_stdlib(self):
        for path in SCRIPTS:
            for name in imports(path):
                self.assertTrue(name in sys.stdlib_module_names or name == "litharness", f"{path.name}: {name}")

    def test_transport(self):
        for path in SCRIPTS:
            if path.name != "transport.py":
                self.assertNotIn("subprocess", set(imports(path)), path.name)

    def test_tracked(self):
        listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True)
        if listed.returncode:
            self.skipTest("not a git checkout")
        tracked = [p for p in listed.stdout.decode("utf-8").split("\0") if p]
        for name in tracked:
            self.assertLessEqual((ROOT / name).stat().st_size, 512 * 1024, name)
            self.assertNotIn(name.split("/")[0], {"runs", "serials", "shelf", "book-library", "research"})
            self.assertFalse(fnmatch(Path(name).name, "*.db*"), name)
        shelf = [*(files.home() / "shelf").glob("**/*.txt")]
        for folder in ("PrimalHunter", "DefianceOfTheFall", "RandidlyGhosthound", "TheGam3"):
            shelf += (EXEMPLARS / folder).glob("**/*.txt")
        if not shelf:
            return  # CI and fresh machines hold no shelf text
        third = set().union(*(runs(files.read(p), 12) for p in shelf))
        for name in tracked:
            if name.endswith((".md", ".txt", ".json")):
                self.assertFalse(runs((ROOT / name).read_bytes().decode("utf-8", "replace"), 12) & third, name)

    def test_prompts(self):
        texts = [v for k, v in vars(prompts).items() if k.isupper() and isinstance(v, str)]
        texts += [s for k, v in vars(prompts).items() if k.isupper() and isinstance(v, dict) for s in v.values()]
        joined = "\n".join(texts)
        self.assertLessEqual(tells.words(joined), 700)
        self.assertEqual(checks.money(joined, "pitch") + checks.hits(checks.ADMIN, joined), [])
        self.assertFalse(runs(joined, 6) & set().union(*(runs(case["text"], 6) for case in FIXTURES)))

    def test_fixtures(self):
        self.assertLessEqual(len(FIXTURES), 60)
        for case in FIXTURES:
            self.assertLessEqual(len(case["text"].split()), 40, case["text"])

    def test_docs(self):
        for name, cap in DOCS.items():
            self.assertLessEqual(lines(ROOT / name), cap, name)
        for path in (ROOT / "reads").glob("[0-9][0-9].md"):
            self.assertLessEqual(lines(path), 60, path.name)
