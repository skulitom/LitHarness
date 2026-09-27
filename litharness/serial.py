"""Stages over plain files under $LITHARNESS_HOME. Resuming means re-running the same command."""
from __future__ import annotations

from pathlib import Path
import re

from . import files, prompts, transport

MODEL, EFFORT = "gpt-6-astra", "medium"
WORD = re.compile(r"\b\w+(?:['’\-]\w+)*\b")


def words(text: str) -> int:
    return len(WORD.findall(text))


def source() -> str:
    return files.sha(b"".join(p.read_bytes() for p in sorted(Path(__file__).parent.glob("*.py"))))


def totals(rows: list[dict]) -> dict:
    usage = {name: sum(r["usage"].get(name, 0) for r in rows if r.get("usage") is not None)
             for name in ("input_tokens", "cached_input_tokens", "output_tokens")}
    return {"calls": len(rows), "seconds": round(sum(r.get("seconds", 0) for r in rows), 3),
            "unknown_usage_calls": sum(r.get("usage") is None for r in rows), **usage,
            "uncached_input_tokens": usage["input_tokens"] - usage["cached_input_tokens"]}


def opening(brief_file: Path, target: int, binary: Path, resume: bool = False,
            call=transport.codex) -> tuple[Path, dict]:
    """Lite's two calls (plan, then draft) for one opening chapter, bound to its inputs by hash."""
    brief = files.read(brief_file)
    if not brief.strip() or not 500 <= target <= 10000:
        raise ValueError("Supply a non-empty brief and a target from 500 to 10000 words")
    root = files.home() / "openings" / f"{brief_file.stem}-{target}"
    config = {"brief": brief, "target_words": target, "model": MODEL, "effort": EFFORT,
              "source_sha256": source(), "binary": str(binary), "binary_sha256": files.digest(binary)}
    if resume:
        manifest = files.load(root / "run.json")
        if manifest["config"] != config:
            raise ValueError("Saved inputs, code, model or binary changed; start a new opening")
        for name, expected in manifest["artifacts"].items():
            if files.digest(root / name) != expected:
                raise ValueError(f"Saved artifact changed: {name}")
    else:
        root.mkdir(parents=True, exist_ok=False)
        manifest = {"config": config, "status": "ready", "attempts": [],
                    "artifacts": {"brief.txt": files.write(root / "brief.txt", brief)}}
        files.save(root / "run.json", manifest)
    files.lock(root / "lock", f"opening {root.name}")
    try:
        for stage, name in (("plan", "plan.md"), ("draft", "chapter.md")):
            if name in manifest["artifacts"]:
                continue
            plan = files.read(root / "plan.md") if stage == "draft" else ""
            prompt = (prompts.PLAN if stage == "plan" else prompts.DRAFT).format(
                brief=brief, context="", words=target, plan=plan)
            attempt = f"calls/{len(manifest['attempts']) + 1:02d}-{stage}"
            manifest["attempts"].append(attempt)
            manifest["status"] = stage
            files.save(root / "run.json", manifest)
            print(f"{stage}: requesting {MODEL} ({EFFORT})", flush=True)
            text, _ = call(prompt, root / attempt, system=prompts.SYSTEM, model=MODEL,
                           effort=EFFORT, binary=binary)
            manifest["artifacts"][name] = files.write(root / name, text)
            files.save(root / "run.json", manifest)
        count = words(files.read(root / "chapter.md"))
        manifest.update(status="complete", word_count=count,
                        length_warning=not 0.85 * target <= count <= 1.15 * target)
        files.save(root / "run.json", manifest)
        return root, manifest
    except Exception as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        files.save(root / "run.json", manifest)
        raise
    finally:
        files.unlock(root / "lock")
