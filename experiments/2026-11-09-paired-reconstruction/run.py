"""Paired reconstruction, spending half: outlines of real openings, then four writers that rewrite them.

  python run.py select               choose targets, examples and background titles (no calls)
  python run.py skeleton [--limit N] outline each target and example opening (chat model)
  python run.py A|B|C|D [--limit N]  A: outline only; B: outline + real openings; C: local continuation;
                                     D: C's draft repaired by the chat model
Everything is resumable: a finished file is never redrawn. Real openings reach the chat model's provider in
the skeleton, B and D prompts; nothing from the corpus is written inside the tree.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from litharness import files, serial, transport  # noqa: E402
import score  # noqa: E402

DATA, SEED, WORKERS = score.DATA, 20261109, 2
LOCAL, OLLAMA, CHUNK, REST, PAUSE_C, RESUME_C = "gemma3:12b", "http://127.0.0.1:11434/api/generate", 300, 3.0, 70, 64
BREAK = "* * * * *"
SYSTEM = "You write web serial fiction."
SKELETON = """Below is the opening of a web serial chapter. Write an outline of what it contains, so that a writer who never sees it could write the same opening.

- First two lines: `Narration: first person` or `Narration: third person`, then `Tense: past` or `Tense: present`.
- Then one numbered line for each thing that happens, is said, is learned or is shown, in order: between 15 and 30 lines.
- Use plain present tense and your own flat words. Never reuse four or more words in a row from the text, and never quote dialogue: say what was said.
- Keep every name and number, and what any System message, stat or skill says, as facts.
- Say nothing about style, tone, length or how it is written.

Output only the outline.

=== TEXT ===
{text}"""
ARM_A = """Write the opening of chapter 1 of a LitRPG web serial, as published on Royal Road, from this outline. Cover its lines in order. About {words} words. Output only the chapter text.

=== OUTLINE ===
{outline}"""
ARM_B = """Below are three openings of published LitRPG web serials, each after its outline, and then a new outline. Write the new outline's opening the way these authors write: their kind of prose, pacing, paragraphing and voice, not your own. Do not reuse their sentences, names or events. Cover the outline's lines in order. About {words} words. Output only the chapter text.

{examples}

=== NEW OUTLINE ===
{outline}"""
ARM_D = """Below are an outline and a draft written from it. The draft may drift from the outline, loop, or stop mid-sentence. Return the draft with only these repairs: it covers the outline's lines in order, repeated passages are gone, and a cut-off ending is finished. Leave every other sentence exactly as it is written; do not polish it or change its style. About {words} words. Output only the repaired text.

=== OUTLINE ===
{outline}

=== DRAFT ===
{draft}"""


def plan() -> dict:
    return json.loads(files.read(DATA / "pairs.json"))


def select() -> str:
    chosen = files.load(score.CORPUS / "selection.json")["fictions"]
    usable = {}
    for fiction in chosen:
        path = score.CORPUS / str(fiction["fiction_id"]) / "ch01.txt"
        if fiction["litrpg"] and fiction["era"] != "other" and path.is_file() and len(
                score.norm(path.read_text(encoding="utf-8", errors="replace")).split()) >= 1300:
            usable[str(fiction["fiction_id"])] = fiction["era"]
    dice, targets = random.Random(SEED), []
    for era in ("2021-22", "2024-25"):
        targets += dice.sample(sorted(t for t, e in usable.items() if e == era), 30)
    rest = sorted(set(usable) - set(targets))
    examples = dice.sample(rest, 20)
    files.save(DATA / "pairs.json", {
        "seed": SEED, "targets": targets, "examples": examples, "era": usable,
        "background": sorted(set(rest) - set(examples)),
        "exemplars_for": {t: dice.sample(examples, 3) for t in targets}})
    return f"{len(targets)} targets, {len(examples)} examples, {len(rest) - len(examples)} background titles"


def chat(stage: str, title: str, prompt: str, agent: str) -> str:
    for attempt in range(1, 4):
        try:
            answer, _ = transport.send(prompt, DATA / "calls" / stage / title / f"a{attempt}-{files.utc()}",
                                       system=SYSTEM, agent=agent)
            return answer.strip()
        except transport.Fault as fault:
            print(f"{stage} {title}: attempt {attempt} faulted: {fault}", file=sys.stderr, flush=True)
    raise transport.Fault(f"{stage} {title}: three attempts faulted")


def outline(title: str) -> str:
    return files.read(DATA / "skeleton" / f"{title}.txt")


def skeleton(title: str, agent: str) -> str:
    text = score.real(title)
    for _ in range(2):
        answer = chat("skeleton", title, SKELETON.format(text=text), agent)
        numbered = sum(line[:1].isdigit() for line in answer.splitlines())
        if answer.startswith("Narration:") and 12 <= numbered <= 34 and score.shared(answer, text, 5) < 0.12:
            return answer
        print(f"skeleton {title}: redrawn ({numbered} lines, {score.shared(answer, text, 5):.3f} copied)",
              file=sys.stderr, flush=True)
    raise ValueError(f"skeleton {title}: two outlines broke the rules")


def words(title: str) -> int:
    return round(len(score.real(title).split()), -2)


def arm_a(title: str, agent: str) -> str:
    return chat("A", title, ARM_A.format(words=words(title), outline=outline(title)), agent)


def arm_b(title: str, agent: str) -> str:
    examples = "\n\n".join(f"=== OUTLINE {i} ===\n{outline(e)}\n\n=== OPENING {i} ===\n{score.real(e)}"
                           for i, e in enumerate(plan()["exemplars_for"][title], 1))
    return chat("B", title, ARM_B.format(words=words(title), examples=examples, outline=outline(title)), agent)


def temperature() -> int:
    try:
        found = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                               capture_output=True, timeout=20)
        return int(found.stdout.split()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return PAUSE_C  # an unreadable sensor is treated as hot


def rest(seconds: float, calls: int) -> None:
    """A quarter duty cycle, a hold above PAUSE_C until RESUME_C, and a 90 s soak break every 40 calls."""
    time.sleep(REST * seconds + (90 if calls % 40 == 0 else 0))
    if temperature() >= PAUSE_C:
        while temperature() > RESUME_C:
            time.sleep(15)


CALLS = [0]


def arm_c(title: str, agent: str) -> str:
    """A plain document of outline-then-opening entries, continued by the local model with no chat template."""
    document = "".join(f"OUTLINE\n{outline(e)}\n\nCHAPTER 1\n\n{score.real(e)}\n\n{BREAK}\n\n"
                       for e in plan()["exemplars_for"][title]) + f"OUTLINE\n{outline(title)}\n\nCHAPTER 1\n\n"
    text, goal = "", words(title)
    for _ in range(14):
        body = {"model": LOCAL, "prompt": document + text, "raw": True, "stream": False, "keep_alive": "10m",
                "options": {"num_predict": CHUNK, "temperature": 0.9, "top_p": 0.95, "num_ctx": 12288,
                            "stop": [BREAK, "\nOUTLINE\n"]}}
        start = time.monotonic()
        request = urllib.request.Request(OLLAMA, json.dumps(body).encode("utf-8"), {"content-type": "application/json"})
        with urllib.request.urlopen(request, timeout=600) as response:
            reply = json.loads(response.read())
        CALLS[0] += 1
        rest(time.monotonic() - start, CALLS[0])
        text += reply.get("response", "")
        if reply.get("done_reason") != "length" or len(text.split()) >= goal:
            break
    if reply.get("done_reason") == "length":  # cut mid-sentence by the word goal: end on the last full sentence
        text = text[:max(text.rfind(mark) for mark in ('. ', '.\n', '."', '!"', '?"', '!\n', '?\n')) + 1]
    if len(text.split()) < 0.5 * goal:
        raise ValueError(f"C {title}: the local model stopped at {len(text.split())} of {goal} words")
    return text.strip()


def arm_d(title: str, agent: str) -> str:
    draft = files.read(DATA / "arms" / "C" / f"{title}.txt")
    return chat("D", title, ARM_D.format(words=words(title), outline=outline(title), draft=draft), agent)


STAGES = {"skeleton": (skeleton, WORKERS), "A": (arm_a, WORKERS), "B": (arm_b, WORKERS), "C": (arm_c, 1),
          "D": (arm_d, WORKERS)}


def stage(name: str, limit: int | None, agent: str) -> str:
    make, workers = STAGES[name]
    titles = plan()["targets"][:limit] + (plan()["examples"] if name == "skeleton" else [])
    folder = DATA / ("skeleton" if name == "skeleton" else f"arms/{name}")
    todo = [t for t in titles if not (folder / f"{t}.txt").is_file()]
    if name == "D":
        todo = [t for t in todo if (DATA / "arms" / "C" / f"{t}.txt").is_file()]

    def one(title: str) -> str | None:
        try:
            files.write(folder / f"{title}.txt", make(title, agent) + "\n")
            print(f"{name} {title}: done", flush=True)
        except (ValueError, OSError) as error:  # a Fault is a ValueError; one title never stops the stage
            print(f"{name} {title}: FAILED {error}", file=sys.stderr, flush=True)
            return title
        return None

    with ThreadPoolExecutor(workers) as pool:
        failed = [t for t in pool.map(one, todo) if t]
    return f"{name}: {len(todo) - len(failed)} written, {len(failed)} failed, {len(titles) - len(todo)} already there"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("verbs", nargs="+", choices=["select", *STAGES])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--agent", help="codex or claude[:MODEL[:EFFORT]]; default: the project's agent")
    args = parser.parse_args()
    for verb in args.verbs:
        if verb == "select":
            print(select())
            continue
        agent = ":".join(transport.resolve(args.agent or serial.writer()))
        box = files.box_lock()
        files.lock(box, f"paired-reconstruction {verb}")
        try:
            if verb != "C":
                transport.preflight(transport.resolve(agent)[0])
                serial.pinned(agent)
            print(stage(verb, args.limit, agent), flush=True)
        finally:
            files.unlock(box)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
